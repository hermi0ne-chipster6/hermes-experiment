from pathlib import Path
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diary'))
from hermes_diary.client import Client
from hermes_diary.server import DiaryServer

try:
    from hermes_diary.heartbeat import run_once
except ImportError:
    run_once = None


class HeartbeatTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(run_once, 'Heartbeat runner is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.socket = self.root / 'socket'
        self.server = DiaryServer(self.socket, self.root / 'db', operator_uid=os.getuid())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.thread.join, 2)
        self.addCleanup(self.server.shutdown)
        self.client = Client(self.socket)
        self.environment = {'PATH': os.environ.get('PATH', ''),
                            'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'diary'),
                            'HERMES_DIARY_SOCKET': str(self.socket)}
        self.agent = self.root / 'agent.py'
        self.agent.write_text('''import os
from hermes_diary.client import Client
payload = {'type':'heartbeat', 'run_id':os.environ['HERMES_HEARTBEAT_RUN_ID'],
           'objectives':['Investigate'], 'actions':[], 'outcomes':['No external actions'],
           'unfinished':[], 'commitments':[]}
Client(os.environ['HERMES_DIARY_SOCKET']).call('append', request_id=os.environ['HERMES_DIARY_REQUEST_ID'], payload=payload)
''')

    def run_agent(self, command, **kwargs):
        return run_once(self.client, command, self.root / 'lock', env=self.environment, **kwargs)

    def test_completed_only_after_durable_matching_receipt(self):
        result = self.run_agent([sys.executable, str(self.agent)])
        self.assertEqual(result['status'], 'complete')
        self.assertIsNotNone(result['receipt'])
        records = self.client.call('read')
        self.assertEqual([r['payload']['type'] for r in records], ['run_started', 'heartbeat'])

    def test_zero_exit_without_submission_is_incomplete(self):
        result = self.run_agent([sys.executable, '-c', 'pass'])
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(self.client.call('read')[-1]['payload']['type'], 'run_incomplete')

    def test_socket_is_supplied_to_the_agent_without_ambient_secrets(self):
        agent = self.root / 'environment.py'
        agent.write_text('import os\nassert os.environ.get("HERMES_DIARY_SOCKET")\nassert "UNRELATED_SECRET" not in os.environ\n' + self.agent.read_text())
        from unittest.mock import patch
        with patch.dict(os.environ, {'UNRELATED_SECRET':'synthetic'}):
            result = run_once(self.client, [sys.executable, str(agent)], self.root / 'lock',
                              env={'PATH':os.environ.get('PATH',''), 'PYTHONPATH':self.environment['PYTHONPATH']})
        self.assertEqual(result['status'], 'complete')

    def test_failure_is_not_hidden_by_a_receipt(self):
        self.agent.write_text(self.agent.read_text() + '\nraise SystemExit(2)\n')
        result = self.run_agent([sys.executable, str(self.agent)])
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['returncode'], 2)

    def test_timeout_kills_child_and_records_interruption(self):
        result = self.run_agent([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=0.1)
        self.assertEqual(result['status'], 'incomplete')
        self.assertIn('timeout', result['reason'])

    def test_timeout_stays_incomplete_when_sigterm_handler_exits_zero(self):
        self.agent.write_text(self.agent.read_text() + '\nimport signal,time\nsignal.signal(signal.SIGTERM, lambda *_: exit(0))\nwhile True: time.sleep(0.01)\n')
        result = self.run_agent([sys.executable, str(self.agent)], timeout=0.5)
        self.assertEqual(result['returncode'], 0)
        self.assertEqual(result['status'], 'incomplete')
        self.assertIn('timeout', result['reason'])

    def test_only_one_bounded_closing_attempt(self):
        closing = self.root / 'close.py'
        counter = self.root / 'counter'
        closing.write_text(f'from pathlib import Path\np=Path({str(counter)!r})\np.write_text(p.read_text()+"x" if p.exists() else "x")\n')
        result = self.run_agent([sys.executable, '-c', 'pass'], closing_command=[sys.executable, str(closing)])
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(counter.read_text(), 'x')

    def test_closing_attempt_can_submit_missing_report(self):
        result = self.run_agent([sys.executable, '-c', 'pass'], closing_command=[sys.executable, str(self.agent)])
        self.assertEqual(result['status'], 'complete')

    def test_overlapping_heartbeat_does_not_start(self):
        import fcntl
        with (self.root / 'lock').open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_agent([sys.executable, str(self.agent)])
        self.assertEqual(result['status'], 'busy')
        self.assertEqual(self.client.call('read'), [])


if __name__ == '__main__':
    unittest.main()
