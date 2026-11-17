#!/usr/bin/env python3
"""Exercise real ADB initialization and REA enumeration without a device target.

Run as rea with its installed HOME. The owned foreground server uses a private
loopback port; cleanup never kills a shared/default ADB server. Key files are
stat'ed only: no key contents or digests are read, printed or copied.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import shlex
import shutil
import socket
import stat
import subprocess
import tempfile
import time

CASE_ID = "adb-initialization"
# Force default HOME-based key storage, and exclude caller auth tracing/keys.
UNSET = ("ANDROID_USER_HOME", "ANDROID_SDK_HOME", "ADB_VENDOR_KEYS", "ADB_TRACE")


def metadata(path, *, directory=False):
    info = path.lstat()
    assert not stat.S_ISLNK(info.st_mode), f"Unexpected symlink: {path}"
    assert (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)), str(path)
    assert info.st_uid == os.geteuid(), f"Wrong owner for {path}: {info.st_uid}"
    return {"path": str(path), "uid": info.st_uid, "owner": pwd.getpwuid(info.st_uid).pw_name,
            "mode": oct(stat.S_IMODE(info.st_mode)), "bytes": info.st_size}


def owned_listener(pid, port):
    """Linux socket ownership check; refuse a port occupied by any other process."""
    inodes = set()
    for fd in (Path('/proc') / str(pid) / 'fd').iterdir():
        try:
            link = os.readlink(fd)
        except FileNotFoundError:
            continue
        if link.startswith('socket:['):
            inodes.add(link[8:-1])
    wanted = f"0100007F:{port:04X}"
    for line in Path('/proc/net/tcp').read_text().splitlines()[1:]:
        fields = line.split()
        if fields[1] == wanted and fields[3] == '0A' and fields[9] in inodes:
            return True
    return False


def run_adb_case(command, output):
    """command is the normal REA argv; owns a dedicated MCP child and ADB server."""
    from functional import MCP

    account = pwd.getpwuid(os.geteuid())
    assert account.pw_name == 'rea' and os.geteuid() != 0, 'Run as the installed unprivileged rea account'
    home = Path(os.environ['HOME'])
    assert home.is_absolute() and home == Path(account.pw_dir), 'Use the installed rea HOME, without a fixture HOME override'
    home_meta = metadata(home, directory=True)
    assert home_meta['mode'] == '0o700', home_meta
    # Do not precreate .android or repair HOME: the real provider must be able
    # to initialize it. This unique probe also catches other future dotdirs.
    probe = Path(tempfile.mkdtemp(prefix='.hermes-provider-home-probe-', dir=home))
    try:
        probe_meta = metadata(probe, directory=True)
        assert probe_meta['mode'] == '0o700', probe_meta
    finally:
        probe.rmdir()  # Only the empty directory this invocation created.
    assert not probe.exists()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    selected = os.environ.get('REA_ADB_PATH') or shutil.which('adb')
    assert selected and Path(selected).is_absolute(), 'Installed adb executable not found'
    adb = str(Path(selected).resolve(strict=True))
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    assert port != 5037
    # ADB 34.0.5 cannot listen on an explicit numeric hostname. Without
    # -a, its hostless TCP listener is loopback; verify that address below.
    server_socket = f'tcp:{port}'
    env = {key: value for key, value in os.environ.items() if key not in UNSET}
    env.update(ADB_SERVER_SOCKET=server_socket, REA_ADB_PATH=adb, ADB_MDNS_AUTO_CONNECT='')
    server = client = None
    shutdown = {}
    android = home / '.android'
    android_existed = android.exists()
    logs = [(output / 'adb-server.stdout').open('wb'), (output / 'adb-server.stderr').open('wb')]
    try:
        # Foreground ownership avoids orphaning a detached daemon on failure.
        # Bind races fail closed: verify this exact child's listening socket.
        server = subprocess.Popen([adb, '-L', server_socket, 'server', 'nodaemon'],
                                  stdin=subprocess.DEVNULL, stdout=logs[0], stderr=logs[1], env=env)
        deadline = time.monotonic() + 30
        while True:
            assert server.poll() is None, f'Owned adb server exited {server.returncode}; see adb-server.stderr'
            if owned_listener(server.pid, port):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Owned adb server did not listen within 30 seconds')
            time.sleep(0.1)
        direct = subprocess.run([adb, 'devices', '-l'], env=env, capture_output=True, text=True, timeout=30)
        (output / 'adb-devices.stdout').write_text(direct.stdout)
        (output / 'adb-devices.stderr').write_text(direct.stderr)
        assert direct.returncode == 0 and direct.stdout.startswith('List of devices attached'), direct.returncode
        assert owned_listener(server.pid, port), 'ADB client replaced or lost the owned listener'
        android_meta = metadata(android, directory=True)
        # Packaged ADB creates 0750; HOME0700 still excludes other users.
        assert android_meta['mode'] in ('0o700', '0o750'), android_meta
        assert stat.S_IMODE(android.lstat().st_mode) & 0o022 == 0, android_meta
        private_meta = metadata(android / 'adbkey')
        public_meta = metadata(android / 'adbkey.pub')
        assert private_meta['mode'] == '0o600' and private_meta['bytes'] > 0, private_meta
        assert public_meta['mode'] in ('0o600', '0o644') and public_meta['bytes'] > 0, public_meta
        prefix = ['env']
        for key in UNSET:
            prefix += ['-u', key]
        prefix += [f'ADB_SERVER_SOCKET={server_socket}', f'REA_ADB_PATH={adb}', 'ADB_MDNS_AUTO_CONNECT=']
        client = MCP(prefix + list(command) + ['mcp'], output)
        initialized = client.request('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
                                     'clientInfo': {'name': 'hermes-adb-initialization', 'version': '1'}})
        (output / 'initialize.json').write_text(json.dumps(initialized, indent=2) + '\n')
        client.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        value = client.call('list_adb_devices', {})
        assert value['operation'] == 'list_adb_devices' and value.get('evidence_id'), value
        result = value['normalized_result']
        assert isinstance(result['devices'], list)
        assert result['client']['binary_path'] == adb and result['client']['path_source'] == 'environment', result['client']
        assert result['client']['version'], result['client']
        assert result['may_have_started_adb_server'] is False, result
        assert owned_listener(server.pid, port), 'REA did not preserve the owned server'
        # No expectation that a device exists; compare actual serial/state pairs.
        direct_rows = [line.split() for line in direct.stdout.splitlines()[1:] if line.strip()]
        expected = {(row[0], 'no permissions' if row[1] == 'no' and len(row) > 2 and row[2].startswith('permissions') else row[1])
                    for row in direct_rows}
        actual = {(item['serial'], item['state']) for item in result['devices']}
        assert actual == expected, 'Direct adb and REA device observations differ'
        detail = {'home': home_meta, 'new_hidden_directory': probe_meta, 'probe_removed': True,
                  'android_directory_preexisted': android_existed, 'android_directory': android_meta,
                  'private_key_metadata': private_meta, 'public_key_metadata': public_meta,
                  'key_contents_read': False, 'server_socket': server_socket, 'owned_server_pid': server.pid,
                  'adb_path': adb, 'adb_version': result['client']['version'], 'device_count': len(actual),
                  'rea_evidence_id': value['evidence_id'], 'direct_and_rea_enumeration_match': True,
                  'scope': 'Real daemon/key-directory initialization and device enumeration only; no physical device, shell, package, transfer or emulator operation qualified'}
    finally:
        try:
            if client is not None:
                client.close()
        finally:
            if server is not None:
                if server.poll() is None:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                        shutdown['mode'] = 'terminated-owned-foreground-server'
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=5)
                        shutdown['mode'] = 'killed-owned-foreground-server'
                else:
                    shutdown['mode'] = 'owned-server-already-exited'
                shutdown['exit_code'] = server.returncode
                with socket.socket() as check:
                    shutdown['listener_closed'] = check.connect_ex(('127.0.0.1', port)) != 0
            for log in logs:
                log.close()
            (output / 'adb-cleanup.json').write_text(json.dumps(shutdown, indent=2) + '\n')
    assert shutdown.get('listener_closed'), shutdown
    detail['cleanup'] = shutdown
    return detail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rea', default='/usr/local/bin/rea')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    try:
        record = {'test': CASE_ID, 'status': 'pass', 'detail': run_adb_case(shlex.split(args.rea), output)}
    except Exception as error:
        record = {'test': CASE_ID, 'status': 'fail', 'reason': f'{type(error).__name__}: {error}'}
    record['duration_seconds'] = round(time.monotonic() - started, 3)
    (output / 'results.json').write_text(json.dumps([record], indent=2) + '\n')
    print(json.dumps(record), flush=True)
    return 0 if record['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
