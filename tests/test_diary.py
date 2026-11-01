import concurrent.futures
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diary'))

try:
    from hermes_diary.store import Journal, DiaryError
except ImportError:
    Journal = None
    DiaryError = ValueError


def summary(run_id='wake-1'):
    return {'type': 'heartbeat', 'run_id': run_id, 'objectives': ['Investigate'],
            'actions': ['Read a document'], 'outcomes': ['No external action'],
            'unfinished': ['Review findings'], 'commitments': []}


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Journal, 'Diary Journal is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'journal.sqlite3'
        self.journal = Journal(self.path)

    def test_receipt_survives_reopen(self):
        receipt = self.journal.append('request-1', summary())
        self.assertEqual(receipt['sequence'], 1)
        self.assertEqual(len(receipt['sha256']), 64)
        reopened = Journal(self.path)
        self.assertEqual(reopened.receipt('request-1'), receipt)
        self.assertEqual(reopened.read()[0]['payload'], summary())

    def test_lost_ack_retry_returns_original_receipt(self):
        first = self.journal.append('request-1', summary())
        self.assertEqual(self.journal.append('request-1', summary()), first)
        self.assertEqual(len(self.journal.read()), 1)

    def test_conflicting_retry_is_rejected(self):
        self.journal.append('request-1', summary())
        changed = summary()
        changed['outcomes'] = ['Different account']
        with self.assertRaises(DiaryError):
            self.journal.append('request-1', changed)
        self.assertEqual(len(self.journal.read()), 1)

    def test_concurrent_retries_append_once(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            receipts = list(executor.map(lambda _: self.journal.append('same-request', summary()), range(24)))
        self.assertTrue(all(r == receipts[0] for r in receipts))
        self.assertEqual(len(self.journal.read()), 1)

    def test_heartbeat_requires_reconciliation(self):
        payload = summary()
        del payload['commitments']
        with self.assertRaises(DiaryError):
            self.journal.append('request-1', payload)
        self.assertEqual(self.journal.read(), [])

    def test_updates_and_deletes_are_rejected_by_database(self):
        self.journal.append('request-1', summary())
        with sqlite3.connect(self.path) as conn:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE entries SET request_id='changed'")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute('DELETE FROM entries')
        self.assertEqual(len(self.journal.read()), 1)

    def test_oversize_and_invalid_payloads_do_not_append(self):
        for request_id, payload in [('bad/id', summary()), ('x', {'type': 'heartbeat'}),
                                    ('x', {'type': 'anything'}), ('x', {'type': 'heartbeat', 'text': 'x' * 70000})]:
            with self.subTest(request_id=request_id, payload_type=payload.get('type')):
                with self.assertRaises(DiaryError):
                    self.journal.append(request_id, payload)
        self.assertEqual(self.journal.read(), [])

    def test_corrupt_database_is_not_replaced(self):
        path = Path(self.temp.name) / 'broken.sqlite3'
        path.write_bytes(b'not a database')
        with self.assertRaises((DiaryError, sqlite3.DatabaseError)):
            Journal(path)
        self.assertEqual(path.read_bytes(), b'not a database')

    def test_unknown_receipt_and_bounded_search(self):
        self.assertIsNone(self.journal.receipt('missing'))
        self.journal.append('request-1', summary())
        self.assertEqual(len(self.journal.search('document')), 1)
        self.assertEqual(self.journal.search('absent'), [])


class CommitmentTests(unittest.TestCase):
    setUp = JournalTests.setUp
    def event(self, status='open', **extra):
        return {'type': 'commitment', 'commitment_id': 'promise-1', 'status': status,
                'description': 'Deliver the report', 'counterparty': 'operator',
                'deadline': '2026-11-01T00:00:00Z', 'conditions': 'Within existing authority', **extra}

    def test_fulfillment_preserves_history_and_evidence(self):
        self.journal.append('create-1', self.event())
        self.journal.append('progress-1', self.event('in_progress'))
        self.journal.append('finish-1', self.event('fulfilled', evidence=['Report receipt 123']))
        view = self.journal.commitments('2026-11-02T00:00:00Z')
        self.assertEqual(view[0]['status'], 'fulfilled')
        self.assertFalse(view[0]['overdue'])
        self.assertEqual(view[0]['evidence'], ['Report receipt 123'])
        self.assertEqual(len(self.journal.read()), 3)

    def test_fulfillment_without_evidence_is_rejected(self):
        self.journal.append('create-1', self.event())
        with self.assertRaises(DiaryError):
            self.journal.append('finish-1', self.event('fulfilled'))
        self.assertEqual(self.journal.commitments()[0]['status'], 'open')

    def test_cancellation_requires_authorized_agreement(self):
        self.journal.append('create-1', self.event())
        with self.assertRaises(DiaryError):
            self.journal.append('cancel-1', self.event('cancelled', evidence=['Changed objective']))
        self.journal.append('cancel-2', self.event('cancelled', evidence=['Operator reply 456'], authorized_agreement='Operator reply 456'))
        self.assertEqual(self.journal.commitments()[0]['status'], 'cancelled')

    def test_unknown_commitment_cannot_be_fulfilled(self):
        with self.assertRaises(DiaryError):
            self.journal.append('finish-1', self.event('fulfilled', evidence=['claim']))

    def test_goal_change_does_not_erase_overdue_commitment(self):
        self.journal.append('create-1', self.event())
        payload = summary('wake-2')
        payload['objectives'] = ['A different goal']
        payload['commitments'] = [{'commitment_id': 'promise-1', 'status': 'open'}]
        self.journal.append('wake-2', payload)
        view = Journal(self.path).commitments('2026-11-02T00:00:00Z')
        self.assertEqual(view[0]['commitment_id'], 'promise-1')
        self.assertTrue(view[0]['overdue'])

    def test_missing_open_commitment_reconciliation_is_rejected(self):
        self.journal.append('create-1', self.event())
        with self.assertRaises(DiaryError):
            self.journal.append('wake-1', summary())

    def test_original_promise_cannot_be_rewritten_in_status_update(self):
        self.journal.append('create-1', self.event())
        with self.assertRaises(DiaryError):
            self.journal.append('change-1', self.event('in_progress', description='A different promise'))


if __name__ == '__main__':
    unittest.main()
