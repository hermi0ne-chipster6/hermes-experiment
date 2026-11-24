"""Bind a disposable Workshop attachment to the retained SDK archive."""

import argparse
import codecs
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import pwd
import re
import subprocess


SDK = 'hermes-experiment'
WORKSHOP = 'hermes-qualification'
MOUNT = f'/var/lib/workshop/sdk/{SDK}'
ARCHIVE = f'{SDK}_amd64_ubuntu@26.04.sdk'


def _require_matching(actual, expected, field):
    if any(actual.get(key) != value for key, value in expected.items()):
        raise ValueError(f'{field} does not match the retained SDK')


def registry_archive(uid, home):
    command = ['systemctl', '--user', 'show-environment'] if uid else ['systemctl', 'show-environment']
    result = subprocess.run(command, text=True, capture_output=True, check=False,
                            env={**os.environ, 'XDG_RUNTIME_DIR': f'/run/user/{uid}'})
    if result.returncode != 0:
        raise ValueError('Cannot read the qualification account manager environment')
    selected = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition('=')
        if key not in {'HOME', 'XDG_DATA_HOME'}:
            continue
        if key in selected or (value.startswith("$'") and not value.endswith("'")):
            raise ValueError(f'Invalid account manager setting: {key}')
        if value.startswith("$'"):
            value = codecs.unicode_escape_decode(value[2:-1])[0]
        selected[key] = value
    if xdg := selected.get('XDG_DATA_HOME'):
        data_home = Path(xdg)
    else:
        manager_home = Path(selected.get('HOME') or pwd.getpwuid(uid).pw_dir)
        if manager_home != home:
            raise ValueError('Workshop and SDKcraft resolve different account homes')
        data_home = home / '.local' / 'share'
    if not data_home.is_absolute():
        raise ValueError('Expected an absolute SDKcraft registry location')
    return data_home / 'workshop' / 'try' / SDK / ARCHIVE


def verify_registry(archive, expected):
    digest = expected['archive_sha3_384']
    checksum = archive.with_name(archive.name + '.sha3-384')
    metadata = archive.with_name(archive.name + '.yaml')
    if any(path.is_symlink() or not path.is_file() for path in (archive, checksum, metadata)):
        raise ValueError('Missing regular try archive or sidecar')
    with archive.open('rb') as stream:
        registered = file_digest(stream, 'sha3_384').hexdigest()
    if registered != digest or checksum.read_bytes() != (digest + '\n').encode('ascii'):
        raise ValueError('Registered SDK or checksum sidecar differs from the retained archive')
    if sha256(metadata.read_bytes()).hexdigest() != expected['metadata_sha256']:
        raise ValueError('Registered metadata sidecar differs from the retained archive')


def _lxd_query(url):
    result = subprocess.run(['sudo', '-n', 'lxc', 'query', f'local:{url}'],
                            text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise ValueError('Cannot inspect the disposable Workshop LXD attachment')
    return json.loads(result.stdout)


def verify_attachment(project, expected, mounted):
    identity = (project / '.workshop.lock').read_text().strip()
    if not re.fullmatch(r'[0-9a-f]{8}', identity):
        raise ValueError('Missing generated disposable Workshop identity')
    uid = os.geteuid()
    username = pwd.getpwuid(uid).pw_name
    owner = username if re.fullmatch(r'[a-zA-Z][-a-zA-Z0-9.]{0,31}', username) else str(uid)
    lxd_project = f'workshop.{owner}'
    instance_name = f'{WORKSHOP}-{identity}'
    instance = _lxd_query(f'/1.0/instances/{instance_name}?project={lxd_project}')
    _require_matching(instance, {'name': instance_name}, 'LXD instance')
    _require_matching(instance['config'], {'user.workshop.project-id': identity,
                                          'user.workshop.name': WORKSHOP}, 'LXD instance ownership')
    devices = instance['expanded_devices']
    devices_at_mount = [device for device in devices.values() if device.get('path') == MOUNT]
    device = instance['devices'].get(f'sdk.{SDK}')
    if device is None or devices_at_mount != [device] or devices.get(f'sdk.{SDK}') != device:
        raise ValueError('Expected a single explicit LXD SDK attachment')
    digest = expected['archive_sha3_384']
    _require_matching(device, {'type': 'disk', 'readonly': 'true', 'pool': 'workshop',
                               'user.sdk.source': 'try', 'user.sdk.sha3-384': digest}, 'LXD attachment')
    revision = device.get('user.sdk.revision', '')
    volume_name = f'{SDK}-{revision}'
    if not re.fullmatch(r'x[1-9][0-9]*', revision) or device.get('source') != volume_name:
        raise ValueError('Expected the local try SDK volume for the attached revision')
    volume = _lxd_query(f'/1.0/storage-pools/workshop/volumes/custom/{volume_name}?project={lxd_project}')
    _require_matching(volume, {'name': volume_name, 'type': 'custom', 'content_type': 'filesystem'},
                      'LXD volume')
    config = volume['config']
    _require_matching(config, {'user.kind': 'sdk', 'user.sdk.name': SDK, 'user.sdk.revision': revision,
                               'user.sha3-384': digest}, 'LXD volume provenance')
    if sha256(config.get('user.sdk.meta', '').encode()).hexdigest() != expected['metadata_sha256']:
        raise ValueError('LXD volume metadata differs from the retained archive')
    _require_matching(mounted, {key: expected[key] for key in ('entries', 'tree_sha256', 'metadata_sha256')},
                      'Mounted SDK payload')
    return {'instance': instance_name, 'volume': volume_name, 'archive_sha3_384': digest,
            'archive_sha256': expected['archive_sha256'], **mounted}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('expected', type=Path)
    parser.add_argument('--mounted', type=Path)
    parser.add_argument('--project', type=Path)
    args = parser.parse_args()
    if bool(args.mounted) != bool(args.project):
        parser.error('--mounted and --project must be supplied together')
    try:
        expected = json.loads(args.expected.read_text())
        if args.mounted:
            mounted = json.loads(args.mounted.read_text())
            print(json.dumps(verify_attachment(args.project, expected, mounted), sort_keys=True))
        else:
            verify_registry(registry_archive(os.geteuid(), Path.home()), expected)
    except (KeyError, json.JSONDecodeError, AttributeError, TypeError):
        parser.exit(1, 'SDK provenance rejected: Unexpected attachment or receipt format\n')
    except (ValueError, OSError) as error:
        parser.exit(1, f'SDK provenance rejected: {error}\n')


if __name__ == '__main__':
    main()
