from pathlib import Path
import json
import subprocess
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / 'deployment/enter-heartbeat'


class HeartbeatEntryTests(unittest.TestCase):
    def invoke(self, close=False, missing=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = root / 'workshop'
            command.write_text('#!/usr/bin/python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
            command.chmod(0o755)
            runuser = root / 'runuser'
            runuser.write_text(
                '#!/bin/bash\n'
                '[[ $1 == -u && $2 == admin && $3 == -- ]] || exit 64\n'
                'shift 3\nexec "$@"\n'
            )
            runuser.chmod(0o755)
            environment = {'PATH': f'{root}:/usr/bin:/bin',
                           'HERMES_HEARTBEAT_RUN_ID': 'a' * 32,
                           'HERMES_DIARY_REQUEST_ID': 'heartbeat:' + 'a' * 32}
            if missing:
                environment.pop('HERMES_HEARTBEAT_RUN_ID')
            if close:
                environment['HERMES_DIARY_CLOSE_ONLY'] = '1'
            return subprocess.run([str(ENTRY)], env=environment, capture_output=True, text=True)

    def test_heartbeat_uses_common_operator_settings_and_native_approvals(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = json.loads(result.stdout)
        self.assertIn('systemd-run', arguments)
        self.assertIn('EnvironmentFile=/etc/hermes-experiment/gateway.env', arguments)
        self.assertIn('RuntimeMaxSec=5400', arguments)
        self.assertIn('NoNewPrivileges=yes', arguments)
        self.assertIn('--setenv=HERMES_HEARTBEAT_RUN_ID=' + 'a' * 32, arguments)
        self.assertIn('--continue', arguments)
        self.assertIn('heartbeat-' + 'a' * 32, arguments)
        self.assertNotIn('--yolo', arguments)
        self.assertNotIn('-z', arguments)

    def test_closing_pass_resumes_only_the_same_session_with_shorter_budget(self):
        result = self.invoke(close=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = json.loads(result.stdout)
        self.assertIn('RuntimeMaxSec=240', arguments)
        self.assertIn('heartbeat-' + 'a' * 32, arguments)
        self.assertNotIn('--create-if-missing', arguments)
        self.assertIn('Do no new work', arguments[-1])

    def test_missing_correlation_fails_before_entering_workshop(self):
        result = self.invoke(missing=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
