from pathlib import Path
import json
import os
import socket
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diary'))
from test_diary import summary

try:
    from hermes_diary.server import DiaryServer
    from hermes_diary.client import Client
except ImportError:
    DiaryServer = Client = None


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(DiaryServer, 'Diary transport is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'socket'
        self.server = DiaryServer(self.path, Path(self.temp.name) / 'db')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.thread.join, 2)
        self.addCleanup(self.server.shutdown)
        self.client = Client(self.path)

    def raw(self, value):
        with socket.socket(socket.AF_UNIX) as conn:
            conn.settimeout(2)
            conn.connect(str(self.path))
            conn.sendall(value + b'\n')
            return json.loads(conn.makefile('rb').readline())

    def test_real_append_read_and_search(self):
        receipt = self.client.call('append', request_id='first', payload=summary())
        self.assertEqual(receipt['sequence'], 1)
        self.assertEqual(self.client.call('read')[0]['payload'], summary())
        self.assertEqual(len(self.client.call('search', query='document')), 1)

    def test_unsupported_and_filesystem_operations_rejected(self):
        for method in ['delete', 'update', 'execute', 'open', 'eval']:
            result = self.raw(json.dumps({'method': method, 'path': '/etc/passwd'}).encode())
            self.assertFalse(result['ok'])

    def test_malformed_and_oversize_requests_fail_without_appending(self):
        for value in [b'not json', b'[]', b'{"method":"read","method":"append"}', b'x' * 70000]:
            self.assertFalse(self.raw(value)['ok'])
        self.assertEqual(self.client.call('read'), [])

    def test_retry_after_unread_response_is_idempotent(self):
        request = {'method': 'append', 'request_id': 'lost', 'payload': summary()}
        with socket.socket(socket.AF_UNIX) as conn:
            conn.connect(str(self.path))
            conn.sendall(json.dumps(request).encode() + b'\n')
            conn.shutdown(socket.SHUT_WR)
            # Wait for the server to commit, but deliberately discard the response.
            conn.recv(4096)
        receipt = self.client.call(**request)
        self.assertEqual(receipt['sequence'], 1)
        self.assertEqual(len(self.client.call('read')), 1)

    def test_client_cannot_inject_database_path(self):
        response = self.raw(b'{"method":"read","database":"/tmp/other"}')
        self.assertFalse(response['ok'])

    def test_unprivileged_client_cannot_forge_runner_lifecycle(self):
        response = self.raw(json.dumps({'method': 'append', 'request_id': 'forged',
                                       'payload': {'type': 'run_started', 'run_id': 'wake-1'}}).encode())
        self.assertFalse(response['ok'])

    def test_forwarded_root_peer_cannot_gain_operator_authority(self):
        # A Workshop tunnel is proxied by a privileged host process. The agent
        # listener must reject lifecycle records even when SO_PEERCRED is root.
        from hermes_diary.store import DiaryError
        with self.assertRaises(DiaryError):
            self.server.dispatch({'method':'append', 'request_id':'proxy-forged',
                                  'payload':{'type':'run_started','run_id':'fake'}}, uid=0)

    def test_agent_cannot_reserve_operator_lifecycle_request_ids(self):
        self.client.call('append', request_id='first', payload=summary())
        for request_id in ('start:wake-1', 'incomplete:wake-1'):
            response = self.raw(json.dumps({'method':'append', 'request_id':request_id,
                'payload':{'type':'correction', 'supersedes_request_id':'first', 'text':'collision'}}).encode())
            self.assertFalse(response['ok'])
        self.assertEqual(len(self.client.call('read')), 1)

    def test_operator_lifecycle_id_must_match_payload_type_and_run(self):
        from hermes_diary.store import DiaryError
        self.server.operator_uid = os.getuid()
        for request_id in ('start:other', 'incomplete:wake-1'):
            with self.assertRaises(DiaryError):
                self.server.dispatch({'method':'append', 'request_id':request_id,
                    'payload':{'type':'run_started', 'run_id':'wake-1'}}, uid=os.getuid())


if __name__ == '__main__':
    unittest.main()
