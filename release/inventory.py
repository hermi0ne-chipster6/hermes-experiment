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


def npm_lock(path, root):
    for parent in (path.parent, *path.parents):
        if not parent.is_relative_to(root):
            break
        candidate = parent/'package-lock.json'
        if candidate.is_file():
            return candidate
    return None


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
    for path in files(root):
        relative = str(path.relative_to(root))
        if path.name.endswith('.lock') and path.name not in ('.workshop.lock', 'uv.lock'):
            raise ValueError(f'unclassified dependency lock: {path.relative_to(root)}')
        if path.name in ('pyproject.toml', 'setup.py', 'setup.cfg', 'Pipfile',
                         'pnpm-lock.yaml', 'npm-shrinkwrap.json', 'pnpm-workspace.yaml',
                         'Cargo.toml', 'go.mod', 'go.sum', 'uv.lock') and relative not in captured:
            raise ValueError(f'unclassified dependency input: {relative}')
        lock_path = npm_lock(path, root) if path.name == 'package.json' else None
        if path.name == 'package.json' and lock_path is None:
            raise ValueError(f'unlocked npm manifest: {path.relative_to(root)}')
        if path.name == 'package.json':
            manifest = json.loads(path.read_text())
            location = path.parent.relative_to(lock_path.parent).as_posix()
            lock_root = json.loads(lock_path.read_text())['packages']['' if location == '.' else location]
            for field in ('dependencies', 'devDependencies', 'optionalDependencies'):
                if manifest.get(field, {}) != lock_root.get(field, {}):
                    raise ValueError(f'npm manifest disagrees with lock: {path.relative_to(root)}')
    if not (root/'release/platform-packages.json').is_file():
        raise ValueError('missing observed Ubuntu package baseline')
    sources = json.loads((root/'sources.json').read_text())
    expected = {'NousResearch/hermes-agent':sources['hermes_commit'],
                'opensandbox-group/OpenSandbox':sources['opensandbox']['commit'],
                'morluto/rea':sources['rea']['commit']}
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
    rea = yaml.safe_load((root/'sdks/hermes-rea/sdkcraft.yaml').read_text())['parts']
    baseline = json.loads((root/'sdks/hermes-rea/SOURCE.json').read_text())
    if (baseline['commit'] != sources['rea']['commit'] or
            baseline['packageVersion'] != sources['rea']['version'] or
            baseline['sourceSha256'] != sources['rea']['sha256'] or
            rea['rea']['source'] != sources['rea']['source'] or
            rea['rea']['source'] != 'https://codeload.github.com/morluto/rea/tar.gz/'+baseline['commit'] or
            rea['rea']['source-checksum'] != 'sha256/'+baseline['sourceSha256']):
        raise ValueError('pin mismatch: hermes-rea source baseline')
    captured_manifest = json.loads((root/'release/upstream-locks/rea/package.json').read_text())
    if captured_manifest['version'] != baseline['packageVersion']:
        raise ValueError('pin mismatch: hermes-rea upstream package version')
    if (rea['upstream-source']['source'] != baseline['upstream']+'.git' or
            rea['upstream-source']['source-commit'] != baseline['commit']):
        raise ValueError('pin mismatch: hermes-rea complete source checkout')
    for component in policy['components']:
        for part, pins in component.get('sdk_sources', {}).items():
            observed = {key:rea[part][key] for key in ('source', 'source-checksum', 'source-commit')
                        if key in rea[part]}
            if observed != pins:
                raise ValueError(f'pin mismatch: hermes-rea/{part} maintenance metadata')
        if component['name'] == 'nativeaot-extension':
            if ('origin '+component['current']) not in rea['nativeaot']['override-build']:
                raise ValueError('pin mismatch: hermes-rea NativeAOT extension')
            source_pin = next(entry['commit'] for entry in baseline['completeSource']['submodules']
                              if entry['path'] == 'third_party/ghidra-nativeaot')
            if source_pin != component['current']:
                raise ValueError('pin mismatch: hermes-rea NativeAOT source submodule')
    assets = json.loads((root/'sdks/hermes-rea/dependencies/assets.json').read_text())
    if assets['rea_source_revision'] != baseline['commit']:
        raise ValueError('pin mismatch: hermes-rea provider asset baseline')
    for asset in assets['assets']:
        if asset.get('dependency_lock'):
            filename = asset['dependency_lock']
            if Path(filename).name != filename:
                raise ValueError('invalid provider dependency lock path')
            lock = (root/'sdks/hermes-rea/dependencies'/filename).read_text().replace('\\\n', ' ')
            pinned = [line for line in lock.splitlines()
                      if (match := re.match(r'^([\w.-]+)(?:\[[^]]+\])?==([^\s;\\]+)', line))
                      and canonicalize_name(match[1]) == canonicalize_name(asset['name'])
                      and match[2] == asset['version']]
            if len(pinned) != 1 or '--hash=sha256:'+asset['sha256'] not in pinned[0].split():
                raise ValueError('pin mismatch: hermes-rea locked provider asset '+asset['name'])
            continue
        matches = [part for part in rea.values() if part.get('source') == asset['url']]
        if not matches or any(part.get('source-checksum') != 'sha256/'+asset['sha256'] for part in matches):
            raise ValueError('pin mismatch: hermes-rea provider asset '+asset['name'])
    if (rea['node-runtime']['source'] != sources['rea_node']['source'] or
            rea['node-runtime']['source-checksum'] != 'sha256/'+sources['rea_node']['sha256'] or
            '/'+sources['rea_node']['version']+'/' not in rea['node-runtime']['source']):
        raise ValueError('pin mismatch: hermes-rea Node runtime')
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
        if path.name == 'uv.lock':
            lock = tomllib.loads(path.read_text())
            for entry in lock['package']:
                source = entry['source']
                if 'registry' in source:
                    if source['registry'].rstrip('/') != 'https://pypi.org/simple':
                        raise ValueError('unclassified Python registry in '+str(relative))
                    dependency('pypi', entry['name'], entry['version'], relative)
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
