"""Regenerate the SDK core lock inputs for one official, resolved stable release."""
from argparse import ArgumentParser
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
from urllib.request import urlopen

import yaml

REPOSITORY = 'NousResearch/hermes-agent'
SDK = Path('sdks/hermes-experiment')
PROVENANCE = Path('release/upstream-locks/provenance.json')
CAPTURE = PROVENANCE.parent / 'hermes'
VERSION = '0.13.5'
UV_ARCHIVE = 'uv-x86_64-unknown-linux-gnu'
UV_URL = f'https://github.com/astral-sh/uv/releases/download/{VERSION}/{UV_ARCHIVE}.tar.gz'
UV_SHA256 = 'f68d291c75783122dad58ab77def0e13f3233f358731db5d6d7e8715603b928f'


def run(args, cwd):
    result = subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE, timeout=300)
    return result.stdout


def use_uv(scratch, supplied):
    if supplied is None:
        archive = scratch / 'uv.tar.gz'
        with urlopen(UV_URL, timeout=60) as response, archive.open('wb') as output:
            shutil.copyfileobj(response, output)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != UV_SHA256:
            raise ValueError('uv release archive SHA-256 mismatch')
        supplied = scratch / 'uv'
        with tarfile.open(archive) as tar, tar.extractfile(f'{UV_ARCHIVE}/uv') as executable:
            with supplied.open('wb') as output:
                shutil.copyfileobj(executable, output)
        supplied.chmod(0o755)
    supplied = supplied.resolve()
    if run([supplied, '--version'], scratch).decode().split()[:2] != ['uv', VERSION]:
        raise ValueError(f'expected lock-generation uv {VERSION}')
    return supplied


def upstream_inputs(checkout, commit):
    def read(path):
        return run(['git', 'show', f'{commit}:{path}'], checkout)

    lock = read('pnpm-lock.yaml')
    pnpm = yaml.safe_load(lock)
    if pnpm['lockfileVersion'] != '9.0' or not {'web', 'ui-tui'} <= pnpm['importers'].keys():
        raise ValueError('unsupported upstream pnpm workspace layout')
    names = {'pnpm-workspace.yaml', 'pm/lock.json', 'pyproject.toml', 'uv.lock'}
    for importer in pnpm['importers']:
        path = Path(importer)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError(f'invalid upstream importer location: {importer}')
        names.add((path / 'package.json').as_posix())
    files = {name: read(name) for name in sorted(names)}
    files['pnpm-lock.yaml'] = lock
    return files


def json_text(value):
    return json.dumps(value, indent=2) + '\n'


def update_hermes_core(tag, commit, release_id, published_at, checkout, root, uv=None):
    if not re.fullmatch(r'v(?:0|[1-9]\d{0,2})\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)', tag):
        raise ValueError(f'unsupported Hermes stable tag: {tag}')
    if not re.fullmatch('[0-9a-f]{40}', commit) or release_id <= 0:
        raise ValueError('invalid release identity')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', published_at):
        raise ValueError('expected a UTC release timestamp')
    datetime.fromisoformat(published_at)
    actual = run(['git', 'rev-parse', 'HEAD'], checkout).decode().strip()
    if actual != commit or run(['git', 'status', '--porcelain', '--untracked-files=no'], checkout):
        raise ValueError('upstream checkout is dirty or does not match the requested commit')

    source_path = root / 'sources.json'
    sources = json.loads(source_path.read_text())
    recipe_path = root / SDK / 'sdkcraft.yaml'
    recipe = recipe_path.read_text()
    previous = sources['hermes_commit']
    if recipe.count(previous) != 1:
        raise ValueError('SDKcraft scheme must declare the current Hermes commit once')
    recipe = recipe.replace(previous, commit)
    files = upstream_inputs(checkout, commit)
    tools = json.loads(files['pm/lock.json'])['packages']
    sources['hermes_commit'] = commit
    sources['hermes'].update(
        tag=tag, release_id=release_id, published_at=published_at,
        source=f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag}',
        assets=[], package_manager=tools['pnpm']['version'],
        plugin_dependency_cutoff=published_at,
    )
    sources.pop('hermes_role_a_dependency_exclusions', None)
    captured = []
    for path, data in sorted(files.items()):
        captured.append({
            'file': str(CAPTURE / path), 'path': path, 'repository': REPOSITORY,
            'revision': commit, 'sha256': hashlib.sha256(data).hexdigest(),
            'roles': ['hermes-experiment'],
        })
    provenance_path = root / PROVENANCE
    previous_captures = json.loads(provenance_path.read_text())
    retained = [item for item in previous_captures if item['repository'] != REPOSITORY]

    # Generate both locks before changing the repository. Export from the
    # official uv lock and resolve only the bundled integration dependency input.
    with tempfile.TemporaryDirectory(prefix='hermes-core-') as directory:
        scratch = Path(directory)
        uv = use_uv(scratch, uv)
        core = run([uv, 'export', '--frozen', '--no-dev', '--extra', 'web', '--extra', 'mcp',
                    '--no-emit-project', '--no-emit-workspace', '--no-emit-local',
                    '--no-header', '--no-annotate'], checkout)
        (scratch / 'core-requirements.txt').write_bytes(core)
        shutil.copyfile(root / SDK / 'plugin-requirements.in', scratch / 'plugin-requirements.in')
        integration_lock = scratch / 'plugin-requirements.txt'
        shutil.copyfile(root / SDK / integration_lock.name, integration_lock)
        # Prefer already-resolved versions that remain compatible with the new
        # core. In particular, a Hermes-only update does not silently upgrade
        # unrelated bundled integration dependencies.
        run([uv, 'pip', 'compile', '--no-config', 'plugin-requirements.in',
             '-c', 'core-requirements.txt', '--python-version', sources['hindsight_runtime']['python'],
             '--python-platform', 'x86_64-unknown-linux-gnu', '--exclude-newer', published_at,
             '--only-binary', ':all:', '--generate-hashes', '--no-header', '--no-annotate',
             '--output-file', integration_lock.name], scratch)
        plugins = integration_lock.read_bytes()
    (root / SDK / 'core-requirements.txt').write_bytes(
        b'# Frozen upstream uv export for the SDK web and mcp extras.\n' + core)
    (root / SDK / 'plugin-requirements.txt').write_bytes(
        b'# Hash-locked bundled integration dependencies, constrained by core-requirements.txt.\n' + plugins)
    for item in previous_captures:
        if item['repository'] == REPOSITORY and item['path'] not in files:
            (root / item['file']).unlink()
    for name, data in files.items():
        path = root / CAPTURE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    provenance_path.write_text(json_text(captured + retained))
    recipe_path.write_text(recipe)
    (root / SDK / 'VERSION').write_text(tag.removeprefix('v') + '\n')
    source_path.write_text(json_text(sources))


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--release-id', type=int, required=True)
    parser.add_argument('--published-at', required=True)
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--uv', type=Path)
    update_hermes_core(**vars(parser.parse_args()))
