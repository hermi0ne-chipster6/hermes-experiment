#!/usr/bin/env python3
"""Probe whether restricted SSH sources worker-controlled startup files.

Run prepare as rea, run the real SSH transport checks from the host, then run
verify as rea. Verify always attempts cleanup. Cleanup can also be run explicitly
after an interrupted transport run. No key files are opened or enumerated.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import shlex
import stat
import sys
import uuid


def identity(path):
    value = path.lstat()
    return {"device": value.st_dev, "inode": value.st_ino, "uid": value.st_uid,
            "mode": stat.S_IMODE(value.st_mode), "type": stat.S_IFMT(value.st_mode)}


def save(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    temporary.replace(path)


def contract(validate_startup=True):
    account = pwd.getpwuid(os.getuid())
    assert account.pw_name == 'rea' and os.getuid() != 0, 'Run as the unprivileged rea account'
    home = Path(account.pw_dir)
    assert home == Path('/var/lib/hermes-rea'), 'Unexpected REA account home'
    if not validate_startup:
        return home
    assert os.environ.get('HOME') == str(home), 'Run with HOME set to the REA account home'
    metadata = identity(home)
    assert metadata['type'] == stat.S_IFDIR, 'HOME must be a directory, not a symlink'
    assert metadata['uid'] == os.getuid() and metadata['mode'] == 0o700, 'HOME must be owned by rea with mode 0700'
    assert account.pw_shell == '/bin/sh', 'REA login shell must be /bin/sh to avoid Bash SSH startup-file sourcing'
    return home


def cleanup(home, manifest):
    errors = []
    allowed = {str(home / '.bashrc'), str(home / '.ssh/rc')}
    for entry in reversed(manifest['files']):
        path = Path(entry['path'])
        if str(path) not in allowed:
            errors.append('Refusing manifest path outside the two startup files')
            continue
        # Never follow a replacement .ssh directory when cleaning its child.
        if path.parent == home / '.ssh':
            try:
                if identity(path.parent) != manifest['ssh_directory']:
                    errors.append('Refusing cleanup through a changed .ssh directory')
                    continue
            except FileNotFoundError:
                continue
        try:
            current = identity(path)
        except FileNotFoundError:
            continue
        if current != entry['identity']:
            errors.append(f'Refusing to remove replaced startup file: {path}')
            continue
        path.unlink()
    if manifest.get('created_ssh_directory'):
        directory = home / '.ssh'
        try:
            if identity(directory) != manifest['ssh_directory']:
                errors.append('Refusing to remove replaced .ssh directory')
            else:
                # rmdir never removes keys or any other files added meanwhile.
                directory.rmdir()
        except FileNotFoundError:
            pass
        except OSError as error:
            errors.append(f'Created .ssh directory retained: {error}')
    assert not errors, '; '.join(errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'verify', 'cleanup'))
    parser.add_argument('--state', required=True, type=Path, help='New private output directory for prepare; reuse for verify/cleanup')
    args = parser.parse_args()
    home = contract(validate_startup=False)
    state = args.state.resolve()
    if args.phase == 'prepare':
        state.mkdir(mode=0o700, parents=True, exist_ok=False)
    assert state.is_dir() and state.stat().st_uid == os.getuid(), 'Probe state must belong to rea'
    manifest_path = state / 'manifest.json'
    manifest = {'home': str(home), 'uid': os.getuid(), 'files': [], 'markers': [],
                'created_ssh_directory': False, 'ssh_directory': None}
    result = {'test': 'ssh-home-' + args.phase, 'status': 'fail'}
    try:
        if args.phase != 'prepare':
            manifest = json.loads(manifest_path.read_text())
            assert manifest['home'] == str(home) and manifest['uid'] == os.getuid(), 'Probe identity changed'
        if args.phase != 'cleanup':
            contract()
        if args.phase == 'prepare':
            # Preflight both names before creating either; lexists rejects dangling links.
            for path in (home / '.bashrc', home / '.ssh/rc'):
                assert not os.path.lexists(path), f'Refusing to overwrite existing startup file: {path}'
            directory = home / '.ssh'
            try:
                directory.mkdir(mode=0o700)
                manifest['created_ssh_directory'] = True
            except FileExistsError:
                pass
            manifest['ssh_directory'] = identity(directory)
            info = manifest['ssh_directory']
            assert info['type'] == stat.S_IFDIR and info['uid'] == os.getuid() and not info['mode'] & 0o022, 'Existing .ssh must be a private rea-owned directory, not a symlink'
            save(manifest_path, manifest)
            for name, path in (('bashrc', home / '.bashrc'), ('ssh-rc', directory / 'rc')):
                marker = state / (name + '-sourced')
                assert not os.path.lexists(marker)
                script = "# Harmless owned SSH startup regression probe.\nprintf '%s\\n' " + shlex.quote(uuid.uuid4().hex) + ' > ' + shlex.quote(str(marker)) + '\n'
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                manifest['files'].append({'path': str(path), 'identity': identity(path)})
                manifest['markers'].append(str(marker))
                try:
                    save(manifest_path, manifest)
                    with os.fdopen(descriptor, 'w') as stream:
                        descriptor = None
                        stream.write(script)
                finally:
                    if descriptor is not None:
                        os.close(descriptor)
            result.update(status='pass', detail={'home_mode': '0700', 'login_shell': '/bin/sh', 'startup_files_created': 2,
                                                'next_step': 'Run actual authenticated SSH transport checks, then verify; cleanup if interrupted'})
        else:
            if args.phase == 'verify':
                assert len(manifest['files']) == 2 and len(manifest['markers']) == 2, 'Preparation incomplete'
                for entry in manifest['files']:
                    assert identity(Path(entry['path'])) == entry['identity'], 'Startup probe was replaced before verification'
                assert identity(home / '.ssh') == manifest['ssh_directory'], '.ssh changed before verification'
                for marker in manifest['markers']:
                    assert Path(marker).parent == state, 'Marker outside probe state'
                    assert not os.path.lexists(marker), f'SSH sourced a worker startup file: {Path(marker).name}'
                result.update(status='pass', detail={'home_mode': '0700', 'login_shell': '/bin/sh',
                                                    'bashrc_not_sourced': True, 'ssh_rc_not_sourced': True,
                                                    'scope': 'Requires separately retained successful authenticated SSH run between phases'})
            else:
                result.update(status='pass', detail={'cleanup_requested': True})
    except Exception as error:
        result.update(status='fail', reason=f'{type(error).__name__}: {error}')
    finally:
        if args.phase != 'prepare' or result['status'] != 'pass':
            try:
                cleanup(home, manifest)
                result['cleanup'] = 'complete'
            except Exception as error:
                result.update(status='fail', cleanup=f'{type(error).__name__}: {error}')
        save(state / (args.phase + '-results.json'), [result])
        print(json.dumps(result), flush=True)
    return 0 if result['status'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
