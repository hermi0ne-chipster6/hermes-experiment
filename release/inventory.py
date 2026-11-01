"""Discover the declared software without installing it or changing any pin."""
import json
from pathlib import Path
import re

import yaml
from packaging.markers import Marker, default_environment

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {'.git', '.superpowers', '__pycache__', 'node_modules', 'reports'}


def files(root):
    return [p for p in root.rglob('*') if p.is_file()
            and not any(part in IGNORED for part in p.relative_to(root).parts)]


def validate_coverage(root=ROOT):
    root = Path(root)
    policy = json.loads((root/'release/components.json').read_text())
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
        if path.name.endswith('.lock') and path.name != '.workshop.lock':
            raise ValueError(f'unclassified dependency lock: {path.relative_to(root)}')
        if path.name == 'package.json' and not (path.parent/'package-lock.json').is_file():
            raise ValueError(f'unlocked npm manifest: {path.relative_to(root)}')
    if not (root/'release/platform-packages.json').is_file():
        raise ValueError('missing observed Ubuntu package baseline')


def inventory(root=ROOT):
    root = Path(root)
    validate_coverage(root)
    policy = json.loads((root/'release/components.json').read_text())
    records = {item['name']: dict(item) for item in policy['components']}

    def dependency(kind, name, version, path):
        key = f'{kind}:{name.lower().replace("_", "-") if kind == "pypi" else name}'
        role = path.parts[1] if path.parts[0] == 'sdks' else 'ci'
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
                if 'node_modules/' not in location or not entry.get('version') or entry.get('link'):
                    raise ValueError(f'unclassified npm dependency {location} in {relative}')
                name = location.rsplit('node_modules/', 1)[1]
                dependency('npm', name, entry['version'], relative)

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
