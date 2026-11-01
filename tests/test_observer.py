from pathlib import Path
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diary'))
from hermes_diary.client import Client
from hermes_diary.server import DiaryServer
from test_diary import summary

try:
    from hermes_diary.observer import register
except ImportError:
    register = None


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(register, 'Hermes diary hook is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.socket = Path(self.temp.name) / 'socket'
        self.server = DiaryServer(self.socket, Path(self.temp.name) / 'db')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.thread.join, 2)
        self.addCleanup(self.server.shutdown)
        self.client = Client(self.socket)
        self.hooks = {}
        self.tools = {}
        class Context:
            register_hook = lambda _, name, fn: self.hooks.__setitem__(name, fn)
            register_tool = lambda _, **kwargs: self.tools.__setitem__(kwargs['name'], kwargs)
        register(Context())
        scope = patch.dict(os.environ, {'HERMES_HEARTBEAT_RUN_ID':'wake-1',
                                      'HERMES_DIARY_REQUEST_ID':'heartbeat:wake-1',
                                      'HERMES_DIARY_SOCKET':str(self.socket)})
        scope.start()
        self.addCleanup(scope.stop)

    def test_agent_authored_final_report_is_saved_once(self):
        response = json.dumps(summary())
        self.hooks['post_llm_call'](assistant_response=response, platform='cli', session_id='session-1')
        self.hooks['post_llm_call'](assistant_response=response, platform='cli', session_id='session-1')
        self.assertEqual(len(self.client.call('read')), 1)
        self.assertEqual(self.client.call('read')[0]['payload'], summary())

    def test_missing_or_invalid_narrative_is_not_fabricated(self):
        self.hooks['post_llm_call'](assistant_response='I finished.', platform='cli')
        self.hooks['on_session_end'](completed=False, interrupted=True, platform='cli')
        self.assertEqual(self.client.call('read'), [])

    def test_gateway_tracks_commitments_without_forcing_a_heartbeat_report(self):
        with patch.dict(os.environ, {'HERMES_HEARTBEAT_RUN_ID':'', 'HERMES_DIARY_REQUEST_ID':''}):
            self.hooks['post_llm_call'](assistant_response=json.dumps(summary()), platform='email')
            result = self.hooks['pre_llm_call'](user_message='hello')
        self.assertIn('commitments', result['context'])
        self.assertNotIn('final response must be', result['context'])
        self.assertEqual(self.client.call('read'), [])

    def test_mismatched_run_is_rejected(self):
        self.hooks['post_llm_call'](assistant_response=json.dumps(summary('other-run')), platform='cli')
        self.assertEqual(self.client.call('read'), [])

    def test_closing_instruction_preserves_agent_objective_choice(self):
        result = self.hooks['pre_llm_call'](user_message='heartbeat')
        self.assertIn('wake-1', result['context'])
        self.assertIn('commitments', result['context'])
        self.assertIn('choose your own objectives', result['context'])

    def test_native_tools_support_reading_and_appending_without_storage_paths(self):
        self.assertEqual(set(self.tools), {'diary_read', 'diary_search', 'diary_commitments', 'diary_append'})
        for tool in self.tools.values():
            self.assertNotIn('socket', tool['schema']['parameters']['properties'])
            self.assertNotIn('database', tool['schema']['parameters']['properties'])
        result = json.loads(self.tools['diary_read']['handler']({}))
        self.assertEqual(result, {'result': []})
        denied = json.loads(self.tools['diary_append']['handler']({'request_id': 'fake:start', 'payload': {'type':'run_started', 'run_id':'fake'}}))
        self.assertIn('error', denied)

    def test_native_tool_storage_failure_is_explicit(self):
        with patch.dict(os.environ, {'HERMES_DIARY_SOCKET':'/does/not/exist'}):
            result = json.loads(self.tools['diary_read']['handler']({}))
        self.assertIn('error', result)


if __name__ == '__main__':
    unittest.main()
