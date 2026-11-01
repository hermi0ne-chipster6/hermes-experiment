"""Agent-side client; it never opens or chooses the journal database."""

import json
import socket

from .store import DiaryError

MAX_RESPONSE = 8 * 1024 * 1024


class Client:
    def __init__(self, socket_path, timeout=10):
        self.socket_path = str(socket_path)
        self.timeout = timeout

    def call(self, method, **arguments):
        data = json.dumps({'method': method, **arguments}, allow_nan=False).encode() + b'\n'
        with socket.socket(socket.AF_UNIX) as conn:
            conn.settimeout(self.timeout)
            conn.connect(self.socket_path)
            conn.sendall(data)
            with conn.makefile('rb') as stream:
                raw = stream.readline(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE or not raw.endswith(b'\n'):
            raise DiaryError('invalid or oversized writer response')
        result = json.loads(raw)
        if not result.get('ok'):
            raise DiaryError(result.get('error', 'writer rejected request'))
        return result['result']
