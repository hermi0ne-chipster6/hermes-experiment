"""Discover the declared software without installing it or changing any pin."""
import json
import hashlib
from pathlib import Path
import re
import tomllib

import yaml
from packaging.markers import Marker, default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {'.git', '.superpowers', '__pycache__', 'node_modules', 'reports',
           'parts', 'stage', 'prime', '.venv', '.workshop'}


def files(root):
    return [p for p in root.rglob('*') if p.is_file()
            and not any(part in IGNORED for part in p.relative_to(root).parts)
            and p.suffix not in ('.sdk', '.zip', '.log', '.pyc', '.pem', '.key', '.db', '.jsonl')
            and p.name not in ('.env', 'id_rsa', 'id_ed25519')
            and not (p.name.startswith('.env.') and not p.name.endswith('.example'))]


def provenance(root):
    path = root/'release/upstream-locks/provenance.json'
    return json.loads(path.read_text()) if path.exists() else []


def javascript_lock(path, root):
    for parent in (path.parent, *path.parents):
        if not parent.is_relative_to(root):
            break
        candidates = [parent/name for name in ('package-lock.json', 'pnpm-lock.yaml')]
        locks = [candidate for candidate in candidates if candidate.is_file()]
        if len(locks) > 1:
            raise ValueError(f'ambiguous JavaScript locks in {parent.relative_to(root)}')
        if locks:
            return locks[0]
    return None


def read_pnpm(path):
    lock = yaml.load(path.read_text(), Loader=getattr(yaml, 'CSafeLoader', yaml.SafeLoader))
    if (not isinstance(lock, dict) or lock.get('lockfileVersion') != '9.0'
            or not isinstance(lock.get('importers'), dict) or not isinstance(lock.get('packages'), dict)):
        raise ValueError(f'unsupported pnpm lock in {path}')
    return lock


def validate_javascript_manifest(path, lock_path, lock, relative):
    manifest = json.loads(path.read_text())
    location = path.parent.relative_to(lock_path.parent).as_posix()
    if lock_path.name == 'pnpm-lock.yaml':
        importer = lock['importers'].get(location)
        if importer is None:
            raise ValueError(f'pnpm manifest has no lock importer: {relative}')
        peers = manifest.get('peerDependencies', {})
        for field in ('dependencies', 'devDependencies', 'optionalDependencies'):
            declared = manifest.get(field, {})
            specifiers = {name: entry['specifier'] for name, entry in importer.get(field, {}).items()
                          if name in declared or name not in peers or peers[name] != entry['specifier']}
            if declared != specifiers:
                raise ValueError(f'pnpm manifest disagrees with lock: {relative}')
    else:
        importer = lock['packages']['' if location == '.' else location]
        for field in ('dependencies', 'devDependencies', 'optionalDependencies'):
            if manifest.get(field, {}) != importer.get(field, {}):
                raise ValueError(f'npm manifest disagrees with lock: {relative}')


def validate_coverage(root=ROOT):
    root = Path(root)
    policy = json.loads((root/'release/components.json').read_text())
    upstream = provenance(root)
    captured = {entry['file']:entry for entry in upstream}
    known = set(policy['local_parts'] + policy['lock_parts'])
    for component in policy['components']:
        known.update(component.get('parts', []))
    actual = set()
    for path in root.glob('sdks/*/sdkcraft.yaml'):
        definition = yaml.safe_load(path.read_text())
        if definition.get('base') != 'ubuntu@26.04' or set(definition['platforms']) != {'amd64'}:
            raise ValueError(f'{path}: expected Ubuntu 26.04 AMD64')
        actual.update(f'{path.parent.name}/{part}' for part in definition['parts'])
    if actual-known:
        raise ValueError(f'untracked SDK parts: {sorted(actual-known)}')
    if known-actual:
        raise ValueError(f'stale SDK part coverage: {sorted(known-actual)}')
    locks = {}
    for path in files(root):
        relative = str(path.relative_to(root))
        if relative.startswith('release/upstream-locks/') and path.name != 'provenance.json' and relative not in captured:
            raise ValueError(f'unclassified dependency input: {relative}')
        if path.name.endswith('.lock') and path.name not in ('.workshop.lock', 'uv.lock'):
            raise ValueError(f'unclassified dependency lock: {path.relative_to(root)}')
        if path.name in ('pyproject.toml', 'setup.py', 'setup.cfg', 'Pipfile',
                         'pnpm-lock.yaml', 'npm-shrinkwrap.json', 'pnpm-workspace.yaml',
                         'Cargo.toml', 'go.mod', 'go.sum', 'uv.lock') and relative not in captured:
            raise ValueError(f'unclassified dependency input: {relative}')
        if path.name == 'package.json':
            lock_path = javascript_lock(path, root)
            if lock_path is None:
                raise ValueError(f'unlocked npm manifest: {relative}')
            if lock_path not in locks:
                locks[lock_path] = (read_pnpm(lock_path) if lock_path.name == 'pnpm-lock.yaml'
                                    else json.loads(lock_path.read_text()))
            validate_javascript_manifest(path, lock_path, locks[lock_path], relative)
    if not (root/'release/platform-packages.json').is_file():
        raise ValueError('missing observed Ubuntu package baseline')
    sources = json.loads((root/'sources.json').read_text())
    pm_path = root/'release/upstream-locks/hermes/pm/lock.json'
    if pm_path.is_file():
        pm = json.loads(pm_path.read_text())['packages']
        if pm['pnpm']['version'] != sources['hermes']['package_manager']:
            raise ValueError('pnpm version disagrees with the Hermes toolchain lock')
    expected = {'NousResearch/hermes-agent':sources['hermes_commit'],
                'opensandbox-group/OpenSandbox':sources['opensandbox']['commit']}
    for entry in upstream:
        path = root/entry['file']
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('invalid captured dependency path')
        if entry['repository'] not in expected or entry['revision'] != expected[entry['repository']]:
            raise ValueError('captured lock revision disagrees with source pin')
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('captured lock digest disagrees with provenance')
    for role, expected in [('hermes-experiment', sources['hermes']['tag'].removeprefix('v')),
                           ('hermes-execution', sources['opensandbox']['tag'].removeprefix('release-')),
                           ('hermes-rea', sources['rea']['version'])]:
        if (root/f'sdks/{role}/VERSION').read_text().strip() != expected:
            raise ValueError(f'pin mismatch: {role}/VERSION and sources.json')
    for role, expected in [('hermes-experiment', sources['hermes_commit']),
                           ('hermes-execution', sources['opensandbox']['commit'])]:
        if expected not in (root/f'sdks/{role}/sdkcraft.yaml').read_text():
            raise ValueError(f'pin mismatch: {role} source revision')
    for path in root.glob('sdks/*/*requirements.in'):
        lock = path.with_suffix('.txt')
        pinned = {}
        for line in lock.read_text().splitlines():
            match = re.match(r'^([\w.-]+)(?:\[[^]]+\])?==([^\s;\\]+)', line)
            if match:
                pinned.setdefault(canonicalize_name(match[1]), set()).add(match[2])
        for line in path.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            requirement = Requirement(line)
            versions = pinned.get(canonicalize_name(requirement.name), set())
            if not versions or not all(value in requirement.specifier for value in versions):
                raise ValueError(f'Python input disagrees with frozen lock: {path.relative_to(root)}')


def inventory(root=ROOT):
    root = Path(root)
    validate_coverage(root)
    policy = json.loads((root/'release/components.json').read_text())
    sources = json.loads((root/'sources.json').read_text())
    records = {}
    for item in policy['components']:
        record = dict(item)
        for field, path in record.get('source_keys', {}).items():
            value = sources
            for key in path:
                value = value[key]
            record[field] = value
        records[item['name']] = record
    upstream = {entry['file']:entry for entry in provenance(root)}
    for entry in upstream.values():
        name = 'upstream-lock:'+entry['file'].removeprefix('release/upstream-locks/')
        records[name] = dict(name=name, kind='upstream-lock', current=entry['sha256'],
                             repository=entry['repository'], revision=entry['revision'], path=entry['path'],
                             roles=entry['roles'], inputs=[entry['file'],'release/upstream-locks/provenance.json'])

    def dependency(kind, name, version, path):
        key = f'{kind}:{name.lower().replace("_", "-") if kind == "pypi" else name}'
        role = upstream[str(path)]['roles'][0] if str(path) in upstream else (path.parts[1] if path.parts[0] == 'sdks' else 'ci')
        record = records.setdefault(key, dict(name=key, kind=kind, package=name,
                                             versions=[], roles=[], inputs=[]))
        for field, value in [('versions', version), ('roles', role), ('inputs', str(path))]:
            if value not in record[field]:
                record[field].append(value)
        record['current'] = ', '.join(sorted(record['versions']))

    for path in files(root):
        relative = path.relative_to(root)
        if path.name.endswith('.txt') and 'requirements' in path.name:
            text = path.read_text()
            declarations = [line for line in text.splitlines()
                            if line and not line[0].isspace() and not line.startswith('#')]
            for line in declarations:
                if ';' in line:
                    marker = line.split(';', 1)[1].rstrip('\\').strip()
                    environment = default_environment()
                    environment.update(python_version='3.14', python_full_version='3.14.7',
                                       sys_platform='linux', platform_system='Linux',
                                       platform_machine='x86_64', os_name='posix', extra='web')
                    if not Marker(marker).evaluate(environment):
                        continue
                match = re.match(r'^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?==([^\s;\\]+)', line)
                if not match:
                    raise ValueError(f'unpinned Python dependency in {relative}')
                dependency('pypi', *match.groups(), relative)
        if path.name == 'package-lock.json':
            lock = json.loads(path.read_text())
            if lock.get('lockfileVersion') not in (2, 3) or 'packages' not in lock:
                raise ValueError(f'unsupported npm lock in {relative}')
            for location, entry in lock['packages'].items():
                if not location:
                    continue
                if 'node_modules/' not in location:
                    continue  # Workspace source is covered by its immutable upstream commit.
                if entry.get('link') and entry.get('resolved') in lock['packages']:
                    continue
                if not entry.get('version') or entry.get('link'):
                    raise ValueError(f'unclassified npm dependency {location} in {relative}')
                name = entry.get('name') or location.rsplit('node_modules/', 1)[1]
                dependency('npm', name, entry['version'], relative)
        if path.name == 'pnpm-lock.yaml':
            lock = read_pnpm(path)
            for identifier, entry in lock['packages'].items():
                match = re.fullmatch(r'((?:@[^/]+/)?[^@/]+)@(\d+\.\d+\.\d+(?:[-+][\w.+-]+)?)', identifier)
                if not match or not entry.get('resolution', {}).get('integrity'):
                    raise ValueError(f'unclassified pnpm dependency {identifier} in {relative}')
                dependency('npm', *match.groups(), relative)
            if str(relative) == 'release/upstream-locks/hermes/pnpm-lock.yaml':
                dependency('npm', 'pnpm', sources['hermes']['package_manager'],
                           Path('release/upstream-locks/hermes/pm/lock.json'))
        if path.name == 'uv.lock':
            lock = tomllib.loads(path.read_text())
            for entry in lock['package']:
                source = entry['source']
                if 'registry' in source:
                    if source['registry'].rstrip('/') != 'https://pypi.org/simple':
                        raise ValueError('unclassified Python registry in '+str(relative))
                    dependency('pypi', entry['name'], entry['version'], relative)
                elif (str(relative) == 'release/upstream-locks/hermes/uv.lock' and 'git' in source
                      and re.fullmatch(r'https://github\.com/[^#]+#[a-f0-9]{40}', source['git'])):
                    continue  # Provenance tracks optional direct Git dependencies in the frozen lock.
                elif str(relative) == 'release/upstream-locks/hermes/uv.lock' and 'url' in source and any(
                    wheel.get('url') == source['url']
                    and re.fullmatch(r'sha256:[a-f0-9]{64}', wheel.get('hash', ''))
                    for wheel in entry.get('wheels', [])
                ):
                    continue  # Optional direct wheels are also covered by upstream-lock provenance.
                elif not any(kind in source for kind in ('editable', 'virtual')):
                    raise ValueError('unclassified uv dependency source in '+str(relative))

    # SDK build-snap additions need a declared channel/revision baseline.
    for path in root.glob('sdks/*/sdkcraft.yaml'):
        definition = yaml.safe_load(path.read_text())
        for part in definition['parts'].values():
            for snap in part.get('build-snaps', []):
                name = snap.split('/')[0]
                key = 'snap:'+name
                if key not in records:
                    raise ValueError(f'untracked build snap: {snap}')
                records[key]['inputs'] = sorted(set(records[key]['inputs']+[str(path.relative_to(root))]))

    # Workflow actions are software too; keep their immutable pins in discovery.
    for path in root.glob('.github/workflows/*.yml'):
        for match in re.finditer(r'uses:\s*([\w.-]+/[\w.-]+)@([0-9a-f]{40})', path.read_text()):
            repo, revision = match.groups()
            key = 'action:'+repo
            item = records.setdefault(key, dict(name=key, kind='github-action',
                                                repository=repo, current=revision,
                                                roles=['ci'], inputs=[]))
            if item['current'] != revision:
                raise ValueError(f'inconsistent action revisions: {repo}')
            item['inputs'].append(str(path.relative_to(root)))
    return sorted(records.values(), key=lambda item: item['name'])


if __name__ == '__main__':
    print(json.dumps(inventory(), indent=2))
