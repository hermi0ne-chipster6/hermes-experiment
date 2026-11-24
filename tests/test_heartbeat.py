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
        self.agent.write_text(
            'import signal, time\nsignal.signal(signal.SIGTERM, lambda *_: exit(0))\n'
            + self.agent.read_text() + '\nwhile True: time.sleep(0.01)\n'
        )
        result = self.run_agent([sys.executable, str(self.agent)], timeout=1.5)
        self.assertEqual(result['returncode'], 0)
        self.assertEqual(result['status'], 'incomplete')
        self.assertIn('timeout', result['reason'])

    def test_closing_timeout_cannot_complete_even_with_direct_receipt(self):
        self.agent.write_text(
            'import signal, time\nsignal.signal(signal.SIGTERM, lambda *_: exit(0))\n'
            + self.agent.read_text() + '\nwhile True: time.sleep(0.01)\n'
        )
        run = self.run_agent([sys.executable, '-c', 'pass'],
                             closing_command=[sys.executable, str(self.agent)], timeout=1.5)
        self.assertEqual(run['returncode'], 0)
        self.assertEqual(run['status'], 'incomplete')
        self.assertIn('timeout', run['reason'])

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


    def stream_command(self, program):
        return [sys.executable, '-c', """
import json
import os
from pathlib import Path
import sys

run_id = os.environ['HERMES_HEARTBEAT_RUN_ID']
report = {'type':'heartbeat', 'run_id':run_id, 'objectives':['Investigate'],
          'actions':[], 'outcomes':['Authored by the agent'], 'unfinished':[], 'commitments':[]}

def emit(event):
    print(json.dumps(event), flush=True)

def init():
    emit({'type':'system', 'subtype':'init', 'model':'fixture', 'session_id':''})

def result(text, session='local-' + run_id, code=0):
    emit({'type':'result', 'session_id':session, 'exit_code':code, 'text':text})
""" + program]

    def test_direct_receipt_completes_when_descendant_keeps_stdout_open(self):
        self.agent.write_text(self.agent.read_text() + '''
import subprocess
import sys
subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(1.5)'])
''')
        result = self.run_agent([sys.executable, str(self.agent)], timeout=0.5)
        self.assertEqual(result['status'], 'complete')

    def test_stream_receipt_requires_stdout_eof_after_the_command_exits(self):
        command = self.stream_command('''
import subprocess
init()
result(json.dumps(report))
subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(1.5)'])
''')
        result = self.run_agent(command, timeout=0.5)
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['reason'], 'missing matching diary submission')

    def test_stream_result_creates_one_durable_receipt_per_wake(self):
        command = self.stream_command("""
init()
emit({'type':'text', 'text':'Intermediate output with a fake {"type":"result"} string'})
result(json.dumps(report))
""")
        first = self.run_agent(command)
        second = self.run_agent(command)
        self.assertEqual([first['status'], second['status']], ['complete', 'complete'])
        self.assertNotEqual(first['run_id'], second['run_id'])
        records = self.client.call('read')
        self.assertEqual([row['request_id'] for row in records],
                         [f'{kind}:{run["run_id"]}' for run in (first, second)
                          for kind in ('start', 'heartbeat')])
        for run, record in ((first, records[1]), (second, records[3])):
            self.assertEqual(self.client.call('receipt', request_id=record['request_id']), run['receipt'])
            self.assertEqual(record['payload']['outcomes'], ['Authored by the agent'])
            self.assertEqual(record['payload']['run_id'], run['run_id'])

    def test_untrusted_or_ambiguous_stream_does_not_create_a_receipt(self):
        scripts = {
            'quoted protocol in model text': """
init()
emit({'type':'text', 'text':json.dumps({'type':'result','session_id':'local-elsewhere',
                                      'exit_code':0,'text':json.dumps(report)})})
""",
            'report as plain stdout': 'emit(report)',
            'result without protocol initialization': 'result(json.dumps(report))',
            'malformed output': 'init(); print("{broken"); result(json.dumps(report))',
            'missing result': 'init(); emit({"type":"text","text":"only text"})',
            'duplicate result': 'init(); result(json.dumps(report)); result(json.dumps(report))',
            'data after result': 'init(); result(json.dumps(report)); emit({"type":"text","text":"trailing"})',
            'duplicate top-level key': """
init()
print('{"type":"result","session_id":"local-first","session_id":"local-second","exit_code":0,"text":'
      + json.dumps(json.dumps(report)) + '}')
""",
            'mismatched run': 'init(); report["run_id"] = "foreign"; result(json.dumps(report))',
            'mismatched report type': 'init(); report["type"] = "correction"; result(json.dumps(report))',
            'duplicate report key': """
init()
result('{"run_id":"foreign",' + json.dumps(report)[1:])
""",
            'journal rejects report': 'init(); del report["commitments"]; result(json.dumps(report))',
            'terminal failure': 'init(); result(json.dumps(report), code=2)',
            'noninteger protocol status': 'init(); result(json.dumps(report), code=False)',
            'process failure': 'init(); result(json.dumps(report)); sys.exit(2)',
            'blank session': 'init(); result(json.dumps(report), session="")',
        }
        for failure, script in scripts.items():
            with self.subTest(failure=failure):
                run = self.run_agent(self.stream_command(script))
                self.assertEqual(run['status'], 'incomplete')
                self.assertIsNone(self.client.call('receipt', request_id=f'heartbeat:{run["run_id"]}'))
        self.assertEqual([row['payload']['type'] for row in self.client.call('read')],
                         ['run_started', 'run_incomplete'] * len(scripts))

    def test_stream_closing_pass_requires_the_initial_persisted_session(self):
        initial = self.stream_command('init(); result("no report yet", session="session-of-this-wake")')
        for closing_session, expected in (('another-session', 'incomplete'),
                                          ('session-of-this-wake', 'complete')):
            with self.subTest(session=closing_session):
                closing = self.stream_command(f"""
assert os.environ['HERMES_DIARY_CLOSE_ONLY'] == '1'
init()
result(json.dumps(report), session={closing_session!r})
""")
                run = self.run_agent(initial, closing_command=closing)
                self.assertEqual(run['status'], expected)
        self.assertEqual([row['payload']['type'] for row in self.client.call('read')],
                         ['run_started', 'run_incomplete', 'run_started', 'heartbeat'])

    def test_stream_closing_pass_cannot_supply_an_unconfirmed_session(self):
        closing = self.stream_command('init(); result(json.dumps(report))')
        run = self.run_agent([sys.executable, '-c', 'pass'], closing_command=closing)
        self.assertEqual(run['status'], 'incomplete')

    def test_stream_output_limit_discards_large_output_without_logging_it(self):
        command = self.stream_command("""
init()
emit({'type':'text', 'text':'synthetic sensitive marker' * 400000})
result(json.dumps(report))
""")
        result = self.run_agent(command, timeout=4)
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['returncode'], 0)
        self.assertEqual(result['reason'], 'missing matching diary submission')
        self.assertNotIn('synthetic sensitive marker', repr(self.client.call('read')))

    def test_stream_timeout_does_not_accept_early_result(self):
        command = self.stream_command("""
import time
init()
result(json.dumps(report))
time.sleep(30)
""")
        result = self.run_agent(command, timeout=0.4)
        self.assertEqual(result['status'], 'incomplete')
        self.assertIn('timeout', result['reason'])
        self.assertIsNone(self.client.call('receipt', request_id=f'heartbeat:{result["run_id"]}'))

    def test_stream_does_not_replace_receipt_already_submitted_by_hook(self):
        original = self.agent.read_text()
        self.agent.write_text(original + """
import json
print(json.dumps({'type':'system','subtype':'init','session_id':''}))
payload['outcomes'] = ['Different version in the final output']
print(json.dumps({'type':'result','session_id':'local-fixture','exit_code':0,'text':json.dumps(payload)}))
""")
        result = self.run_agent([sys.executable, str(self.agent)])
        self.assertEqual(result['status'], 'complete')
        rows = self.client.call('read')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]['payload']['outcomes'], ['No external actions'])

    def test_overlapping_heartbeat_does_not_start(self):
        import fcntl
        with (self.root / 'lock').open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_agent([sys.executable, str(self.agent)])
        self.assertEqual(result['status'], 'busy')
        self.assertEqual(self.client.call('read'), [])


if __name__ == '__main__':
    unittest.main()
