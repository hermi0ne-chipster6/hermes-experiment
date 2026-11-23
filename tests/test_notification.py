from pathlib import Path
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'diary'))
try:
    from hermes_diary.notification import notify
except ImportError:
    notify = None


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(notify)

    def test_attachment_or_empty_message_is_rejected_before_execution(self):
        with patch('subprocess.run') as run:
            for text in ['', 'MEDIA:/home/workshop/.hermes/.env', 'x'*4097]:
                self.assertIn('error', json.loads(notify({'text':text})))
        run.assert_not_called()

    def test_operator_destination_and_argument_boundaries_are_fixed(self):
        with patch.dict(os.environ, {'EMAIL_HOME_ADDRESS':'operator@example.invalid','BUZZ_HOME_CHANNEL':''}):
            with patch('subprocess.run') as run:
                run.return_value = subprocess.CompletedProcess(
                    [], 0, b'{"success": true, "platform": "email"}',
                )
                value=json.loads(notify({'text':'hello; $(ignored)'}))
        self.assertTrue(value['delivered'])
        self.assertEqual(run.call_args.args[0], ['/usr/local/bin/hermes','send','--json','--to','email:operator@example.invalid','--','hello; $(ignored)'])
        self.assertFalse(run.call_args.kwargs.get('shell',False))

    def test_missing_destination_and_delivery_failure_are_explicit(self):
        with patch.dict(os.environ, {'EMAIL_HOME_ADDRESS':'','BUZZ_HOME_CHANNEL':''}):
            self.assertIn('error', json.loads(notify({'text':'hello'})))
        with patch.dict(os.environ, {'EMAIL_HOME_ADDRESS':'operator@example.invalid'}):
            with patch('subprocess.run') as run:
                run.return_value = subprocess.CompletedProcess([], 1, b'{"success": true}')
                self.assertIn('error',json.loads(notify({'text':'hello'})))

    def test_native_skip_is_explicit_despite_success_flag_and_zero_exit(self):
        payload = b'{"success": true, "skipped": true, "reason": "cron_auto_delivery_duplicate_target"}'
        with patch.dict(os.environ, {'BUZZ_HOME_CHANNEL': 'fixture', 'EMAIL_HOME_ADDRESS': 'operator@example.invalid'}):
            with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, payload)) as run:
                outcome = json.loads(notify({'text': 'hello'}))
        self.assertIn('skipped', outcome['error'])
        self.assertNotIn('delivered', outcome)
        self.assertEqual(run.call_args.args[0][4], 'buzz:fixture')

    def test_native_rejection_is_sanitized_even_when_process_exits_zero(self):
        for payload in (b'{"success": false}', b'{"success": true, "error": "sensitive detail"}'):
            with self.subTest(payload=payload):
                with patch.dict(os.environ, {'BUZZ_HOME_CHANNEL': 'fixture'}):
                    with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, payload)):
                        output = notify({'text': 'hello'})
                outcome = json.loads(output)
                self.assertIn('failed', outcome['error'])
                self.assertNotIn('delivered', outcome)
                self.assertNotIn('sensitive detail', output)

    def test_malformed_native_receipts_are_rejected(self):
        for payload in (b'', b'not JSON', b'\xff', b'null', b'[]', b'{}', b'{"success": 1}',
                        b'{"success": "true"}', b'{"success": true, "skipped": "false"}'):
            with self.subTest(payload=payload):
                with patch.dict(os.environ, {'BUZZ_HOME_CHANNEL': 'fixture'}):
                    with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, payload)):
                        outcome = json.loads(notify({'text': 'hello'}))
                self.assertIn('invalid result', outcome['error'])
                self.assertNotIn('delivered', outcome)

    def test_native_launch_errors_and_timeouts_are_sanitized(self):
        for failure in (OSError('sensitive detail'), subprocess.TimeoutExpired('hermes send', 30)):
            with self.subTest(failure=type(failure).__name__):
                with patch.dict(os.environ, {'BUZZ_HOME_CHANNEL': 'fixture'}):
                    with patch('subprocess.run', side_effect=failure):
                        output = notify({'text': 'hello'})
                self.assertIn('error', json.loads(output))
                self.assertNotIn('sensitive detail', output)

    def test_agent_email_uses_native_sender_with_no_model_supplied_from_identity(self):
        from hermes_diary import notification
        self.assertTrue(hasattr(notification, 'send_email'))
        with patch.dict(os.environ, {'EMAIL_ADDRESS':'agent@example.invalid'}), patch('subprocess.run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, b'{"success": true}')
            value=json.loads(notification.send_email({'recipient':'contact@example.invalid','text':'Hello'}))
        self.assertTrue(value['delivered'])
        self.assertEqual(run.call_args.args[0], ['/usr/local/bin/hermes','send','--json','--to','email:contact@example.invalid','--','Hello'])
        self.assertFalse(value['financial_authorization'])

    def test_agent_email_rejects_header_injection_and_missing_identity(self):
        from hermes_diary import notification
        self.assertTrue(hasattr(notification, 'send_email'))
        with patch.dict(os.environ, {'EMAIL_ADDRESS':'agent@example.invalid'}), patch('subprocess.run') as run:
            for recipient in ('a@example.invalid\r\nBcc: b@example.invalid', 'Name <a@example.invalid>', 'a@example.invalid,b@example.invalid'):
                self.assertIn('error',json.loads(notification.send_email({'recipient':recipient,'text':'Hello'})))
            run.assert_not_called()
        with patch.dict(os.environ, {'EMAIL_ADDRESS':''}), patch('subprocess.run') as run:
            self.assertIn('error',json.loads(notification.send_email({'recipient':'a@example.invalid','text':'Hello'})))
            run.assert_not_called()
