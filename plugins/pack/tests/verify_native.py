"""Exercise the upstream pack resolver and installer with a disposable Git plugin."""

import io
import json
import os
from pathlib import Path
import subprocess
import tempfile


PACK = Path(__file__).resolve().parents[1]
NAME = 'pack-state-fixture'


def git(repository, *args):
    return subprocess.check_output(
        ['git', '-C', str(repository), *args], text=True, timeout=15,
    ).strip()


def main():
    with tempfile.TemporaryDirectory(prefix='hermes-pack-fixture-') as directory:
        root = Path(directory)
        profile = root / 'profile'
        home = root / 'home'
        home.mkdir()
        os.environ.pop('HERMES_RUNTIME_DIR', None)
        os.environ.update({
            'HOME': str(home),
            'HERMES_HOME': str(profile),
            'XDG_CONFIG_HOME': str(home / '.config'),
            'XDG_DATA_HOME': str(home / '.local/share'),
            'XDG_CACHE_HOME': str(home / '.cache'),
            'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_TERMINAL_PROMPT': '0',
        })
        verify(profile, root)


def verify(profile, root):
    from hermes_cli import plugin_packs, plugins_cmd
    from rich.console import Console

    def resolve(path):
        pack = plugin_packs.load_pack(str(path))
        records = plugin_packs.resolve_pack_plugins(pack)
        assert all(record.identifier and not record.resolve_error for record in records)
        return pack, records

    _, first = resolve(PACK / 'hermes-pack.yaml')
    _, second = resolve(PACK / 'hermes-pack.yaml')
    assert first == second
    print(json.dumps({'pack': [[record.identifier, record.entry.ref] for record in first]}))

    source = root / 'plugin'
    source.mkdir()
    git(source, 'init', '-q')
    git(source, 'config', 'user.name', 'Hermes fixture')
    git(source, 'config', 'user.email', 'fixture@example.invalid')
    (source / 'plugin.yaml').write_text(
        f'name: {NAME}\nversion: "0.1.0"\ndescription: Disposable pack fixture\n',
    )
    (source / '__init__.py').write_text('def register(ctx):\n    pass\n')
    git(source, 'add', 'plugin.yaml', '__init__.py')
    git(source, 'commit', '-qm', 'Pin fixture')
    pin = git(source, 'rev-parse', 'HEAD')
    (source / 'newer-marker').write_text('The moving tip is outside the pack pin.\n')
    git(source, 'add', 'newer-marker')
    git(source, 'commit', '-qm', 'Advance fixture source')
    assert git(source, 'rev-parse', 'HEAD') != pin

    fixture_pack = root / 'hermes-pack.yaml'
    fixture_pack.write_text(
        f'name: fixture\nplugins:\n  - repo: {source.as_uri()}\n    ref: {pin}\n',
    )
    console = Console(file=io.StringIO(), force_terminal=False)
    profile.mkdir()
    config = profile / 'config.yaml'
    config.write_text(f'plugins:\n  enabled: []\n  disabled: [{NAME}]\n')
    before = config.read_bytes()
    plugins_cmd.cmd_install(source.as_uri(), ref=pin, enable=False)
    installed = profile / 'plugins' / NAME
    assert installed.is_dir()
    assert not (installed / 'newer-marker').exists()
    assert config.read_bytes() == before
    metadata = profile / 'plugins' / '.install-metadata.json'
    original = metadata.read_bytes()
    entry = json.loads(original)[NAME]
    assert entry['pinned'] is True and entry['revision'] == pin

    _, records = resolve(fixture_pack)
    for attempt in range(1, 3):
        pack, repeated_records = resolve(fixture_pack)
        assert repeated_records == records
        repeated = plugin_packs.install_pack_plugins(pack, repeated_records, console)
        assert not repeated[0].ok and 'already exists' in repeated[0].error
        assert metadata.read_bytes() == original
        assert config.read_bytes() == before
        assert not (installed / 'newer-marker').exists()
        print(json.dumps({'attempt': attempt, 'fixture_revision': pin, 'moving_tip_ignored': True,
                          'repeat': 'native installer reported already exists',
                          'disabled_state_preserved': True}))


if __name__ == '__main__':
    main()
