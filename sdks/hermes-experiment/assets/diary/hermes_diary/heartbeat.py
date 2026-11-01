"""Operator-owned heartbeat runner. A successful process exit is not a report.

Run outside A under the configured operator identity. The agent command must
enter A as its unprivileged user. Never run model-selected commands as root.
"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import uuid

from .client import Client


def _execute(command, environment, timeout):
    if not isinstance(command, list) or not command or any(not isinstance(arg, str) for arg in command):
        raise ValueError('command must be a nonempty argv list')
    try:
        proc = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
    except OSError:
        return 127, 'agent command could not start'
    try:
        return proc.wait(timeout=timeout), ''
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        except ProcessLookupError:
            proc.wait()
        return proc.returncode, 'agent timeout'


def _matching_receipt(client, request_id, run_id):
    receipt = client.call('receipt', request_id=request_id)
    if not receipt:
        return None
    rows = client.call('read', after=receipt['sequence'] - 1, limit=1)
    if not rows:
        return None
    record = rows[0]
    if record['request_id'] != request_id or record['payload'].get('type') != 'heartbeat' or record['payload'].get('run_id') != run_id:
        return None
    return receipt


def run_once(client, command, lock_path, *, timeout=5400, closing_command=None, env=None):
    if not 0 < timeout <= 7200:
        raise ValueError('heartbeat timeout must be between 0 and 7200 seconds')
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'status': 'busy'}
        run_id = uuid.uuid4().hex
        request_id = f'heartbeat:{run_id}'
        # No provider, mailbox, Cloudflare or operator secrets inherited from
        # the host. An explicit env mapping is operator configuration, not input
        # from the model or from the submitted diary payload.
        environment = dict(env) if env is not None else {
            key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'TZ') if key in os.environ}
        environment.update(HERMES_HEARTBEAT_RUN_ID=run_id, HERMES_DIARY_REQUEST_ID=request_id,
                           HERMES_DIARY_SOCKET=client.socket_path)
        client.call('append', request_id=f'start:{run_id}', payload={'type': 'run_started', 'run_id': run_id})
        returncode, reason = _execute(command, environment, timeout)
        receipt = _matching_receipt(client, request_id, run_id)
        if returncode == 0 and not reason and not receipt and closing_command:
            environment['HERMES_DIARY_CLOSE_ONLY'] = '1'
            close_code, close_reason = _execute(closing_command, environment, min(timeout, 300))
            receipt = _matching_receipt(client, request_id, run_id)
            if close_code != 0:
                reason = close_reason or f'closing command exited {close_code}'
                returncode = close_code
        if returncode == 0 and not reason and receipt:
            return {'status': 'complete', 'run_id': run_id, 'returncode': returncode, 'receipt': receipt}
        reason = reason or (f'agent exited {returncode}' if returncode else 'missing matching diary submission')
        client.call('append', request_id=f'incomplete:{run_id}',
                    payload={'type': 'run_incomplete', 'run_id': run_id, 'reason': reason})
        return {'status': 'incomplete', 'run_id': run_id, 'returncode': returncode, 'reason': reason}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', required=True)
    parser.add_argument('--lock', required=True)
    parser.add_argument('--timeout', type=float, default=5400)
    parser.add_argument('--closing-command', help='Fixed operator-owned executable; one bounded retry in the same session')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    closing = [args.closing_command] if args.closing_command else None
    result = run_once(Client(args.socket), command, args.lock, timeout=args.timeout, closing_command=closing)
    print(json.dumps(result))
    return 0 if result['status'] == 'complete' else 75


if __name__ == '__main__':
    sys.exit(main())
