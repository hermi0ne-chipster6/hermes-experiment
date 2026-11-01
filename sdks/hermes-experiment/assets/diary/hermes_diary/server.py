"""A bounded local socket API. No SQL, path selection, update or delete API."""

import json
import os
from pathlib import Path
import socket
import socketserver
import sqlite3
import struct
import threading

from .store import DiaryError, Journal, MAX_PAYLOAD

MAX_REQUEST = MAX_PAYLOAD + 4096
MAX_RESPONSE = 8 * 1024 * 1024


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DiaryError('duplicate JSON key')
        result[key] = value
    return result


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(5)
        response = {'ok': False, 'error': 'invalid request'}
        try:
            data = self.rfile.readline(MAX_REQUEST + 1)
            if len(data) > MAX_REQUEST or not data.endswith(b'\n'):
                raise DiaryError('request exceeds size limit or lacks newline')
            request = json.loads(data, object_pairs_hook=unique_object,
                                 parse_constant=lambda _: (_ for _ in ()).throw(DiaryError('non-finite number')))
            uid = struct.unpack('3i', self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
            response = {'ok': True, 'result': self.server.dispatch(request, uid)}
        except (ValueError, TypeError, UnicodeError) as exc:
            response = {'ok': False, 'error': str(exc) if isinstance(exc, DiaryError) else 'invalid request'}
        except sqlite3.Error:
            response = {'ok': False, 'error': 'storage failure; no receipt issued'}
        except (OSError, TimeoutError):
            return
        encoded = json.dumps(response, ensure_ascii=False, allow_nan=False).encode() + b'\n'
        if len(encoded) > MAX_RESPONSE:
            encoded = b'{"ok":false,"error":"response exceeds size limit; use smaller pages"}\n'
        try:
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Client may retry the same immutable request ID.


class DiaryServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True

    def __init__(self, socket_path, database, operator_uid=None, mode=0o660):
        self.journal = Journal(database)
        self.operator_uid = operator_uid
        self.socket_path = Path(socket_path)
        # Never unlink an existing endpoint: it may belong to a live writer.
        self.socket_path.parent.mkdir(parents=True, mode=0o750, exist_ok=True)
        self._slots = threading.BoundedSemaphore(32)
        super().__init__(str(socket_path), Handler)
        os.chmod(socket_path, mode)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def server_close(self):
        super().server_close()
        self.socket_path.unlink(missing_ok=True)

    def dispatch(self, request, uid):
        if not isinstance(request, dict):
            raise DiaryError('request must be an object')
        method = request.get('method')
        fields = {
            'append': {'method', 'request_id', 'payload'},
            'read': {'method', 'after', 'limit'},
            'search': {'method', 'query', 'limit'},
            'receipt': {'method', 'request_id'},
            'commitments': {'method', 'now'},
            'health': {'method'},
        }
        if not isinstance(method, str) or method not in fields or not request.keys() <= fields[method]:
            raise DiaryError('unsupported operation or arguments')
        if method == 'append':
            payload = request.get('payload')
            request_id = request.get('request_id')
            kind = payload.get('type') if isinstance(payload, dict) else None
            reserved = isinstance(request_id, str) and request_id.startswith(('start:', 'incomplete:'))
            if reserved or kind in {'run_started', 'run_incomplete'}:
                if self.operator_uid is None or uid != self.operator_uid:
                    raise DiaryError('runner lifecycle records and IDs require operator identity')
                prefix = {'run_started':'start:', 'run_incomplete':'incomplete:'}.get(kind)
                if not prefix or request_id != prefix + str(payload.get('run_id', '')):
                    raise DiaryError('runner lifecycle ID must match payload type and run')
            return self.journal.append(request.get('request_id'), payload)
        if method == 'read':
            limit = request.get('limit', 100)
            if type(limit) is not int or not 1 <= limit <= 100:
                raise DiaryError('read limit must be between 1 and 100')
            return self.journal.read(request.get('after', 0), limit)
        if method == 'search':
            return self.journal.search(request.get('query'), request.get('limit', 100))
        if method == 'receipt':
            return self.journal.receipt(request.get('request_id'))
        if method == 'commitments':
            return self.journal.commitments(request.get('now'))
        return {'status': 'ready'}
