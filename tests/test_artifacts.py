from pathlib import Path
import hashlib
import io
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diary'))
try:
    from hermes_diary.artifacts import receive_stream, copy_artifact, MAX_BYTES, INBOX
except ImportError:
    receive_stream = copy_artifact = None
    MAX_BYTES = 32 * 1024 * 1024
    INBOX = '/var/lib/hermes-rea/inbox'


class ArtifactReceiverTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(receive_stream, 'artifact transport is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = b'\x7fELF synthetic analysis artifact'
        self.sha = hashlib.sha256(self.data).hexdigest()

    def receive(self, data=None, sha=None, size=None):
        return receive_stream(io.BytesIO(self.data if data is None else data), self.root,
                              sha or self.sha, len(self.data) if size is None else size)

    def test_verified_atomic_delivery_is_idempotent(self):
        first = self.receive()
        second = self.receive()
        self.assertEqual(first, second)
        target = self.root / (self.sha + '.bin')
        self.assertEqual(target.read_bytes(), self.data)
        self.assertEqual(target.stat().st_mode & 0o777, 0o400)
        self.assertEqual(list(self.root.iterdir()), [target])

    def test_bad_digest_truncated_and_oversize_bodies_leave_no_file(self):
        for data, sha, size in [(self.data, '0'*64, len(self.data)),
                                (self.data[:-1], self.sha, len(self.data)),
                                (self.data+b'x', self.sha, len(self.data))]:
            with self.assertRaises((ValueError, OSError)):
                self.receive(data, sha, size)
            self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_metadata_is_rejected_before_writing(self):
        for sha, size in [('../escape', 1), ('f'*64, MAX_BYTES+1), ('f'*64, -1), ('f'*64, True)]:
            with self.assertRaises(ValueError):
                self.receive(sha=sha, size=size)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_symlink_is_never_followed_or_overwritten(self):
        outside = self.root / 'operator-file'
        outside.write_bytes(b'unchanged')
        (self.root / (self.sha+'.bin')).symlink_to(outside)
        with self.assertRaises((ValueError, OSError)):
            self.receive()
        self.assertEqual(outside.read_bytes(), b'unchanged')

    def test_existing_different_content_is_not_replaced(self):
        target = self.root / (self.sha+'.bin')
        target.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.receive()
        self.assertEqual(target.read_bytes(), b'changed')


class ArtifactClientTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(copy_artifact, 'artifact client is not implemented')
        self.closed = False
        self.data = b'sandbox-generated artifact'
        outer = self
        class Files:
            def read_bytes_stream(self, path, **kwargs):
                self.path = path
                yield outer.data
        class Sandbox:
            files = Files()
            def close(self): outer.closed = True
        self.sandbox = Sandbox()
        self.factory_calls = []
        def factory(sandbox_id):
            self.factory_calls.append(sandbox_id)
            return self.sandbox
        self.factory = factory
        self.sent = []
        def sender(file, sha, size):
            self.sent.append(file.read())
            return {'protocol':'artifact-v1','sha256':sha,'size':size,'path':f'{INBOX}/{sha}.bin'}
        self.sender = sender

    def test_native_stream_is_forwarded_without_exposing_data_or_credentials(self):
        receipt = copy_artifact({'sandbox_id':'sandbox-1','remote_path':'/work/file'}, self.factory, self.sender)
        self.assertEqual(self.sent, [self.data])
        self.assertEqual(receipt['sha256'], hashlib.sha256(self.data).hexdigest())
        self.assertTrue(self.closed)
        self.assertEqual(set(receipt), {'protocol','sha256','size','path'})

    def test_oversize_stream_fails_without_sending_and_closes_clients(self):
        self.data = b'x'*(MAX_BYTES+1)
        with self.assertRaises(ValueError):
            copy_artifact({'sandbox_id':'sandbox-1','remote_path':'/work/file'},self.factory,self.sender)
        self.assertEqual(self.sent, [])
        self.assertTrue(self.closed)

    def test_no_local_paths_or_shell_commands_are_accepted_as_sandbox_ids(self):
        for arguments in ({'sandbox_id':'../../etc','remote_path':'/work/file'},
                          {'sandbox_id':'box;id','remote_path':'/work/file'},
                          {'sandbox_id':'box','remote_path':'relative'},
                          {'sandbox_id':'box','remote_path':'/work','local_path':'/etc/passwd'}):
            with self.assertRaises(ValueError):
                copy_artifact(arguments,self.factory,self.sender)
        self.assertEqual(self.factory_calls, [])

    def test_mismatched_peer_receipt_is_rejected(self):
        def lying(file, sha, size):
            return {'protocol':'artifact-v1','sha256':'0'*64,'size':size,'path':'/etc/passwd'}
        with self.assertRaises(ValueError):
            copy_artifact({'sandbox_id':'box','remote_path':'/file'},self.factory,lying)
        self.assertTrue(self.closed)

    def test_stalled_download_has_wall_clock_limit_and_closes_resources(self):
        from hermes_diary.artifacts import bounded_copy
        closed_stream = []
        def stalled(*args, **kwargs):
            try:
                time.sleep(5)
                yield b'x'
            finally:
                closed_stream.append(True)
        self.sandbox.files.read_bytes_stream = stalled
        started = time.monotonic()
        opened = []
        real_temporary_file = tempfile.TemporaryFile
        def temporary():
            file = real_temporary_file()
            opened.append(file)
            return file
        with patch('hermes_diary.artifacts.tempfile.TemporaryFile', side_effect=temporary):
            with self.assertRaises(TimeoutError):
                bounded_copy({'sandbox_id':'box','remote_path':'/file'},self.factory,self.sender,seconds=0.05)
        self.assertLess(time.monotonic()-started,1)
        self.assertTrue(self.closed)
        self.assertEqual(closed_stream,[True])
        self.assertEqual(self.sent,[])
        self.assertEqual(len(opened),1)
        self.assertTrue(opened[0].closed)
