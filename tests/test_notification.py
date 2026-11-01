from pathlib import Path
import json
import os
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
                run.return_value.returncode=0
                value=json.loads(notify({'text':'hello; $(ignored)'}))
        self.assertTrue(value['delivered'])
        self.assertEqual(run.call_args.args[0], ['/usr/local/bin/hermes','send','--to','email:operator@example.invalid','--','hello; $(ignored)'])
        self.assertFalse(run.call_args.kwargs.get('shell',False))

    def test_missing_destination_and_delivery_failure_are_explicit(self):
        with patch.dict(os.environ, {'EMAIL_HOME_ADDRESS':'','BUZZ_HOME_CHANNEL':''}):
            self.assertIn('error', json.loads(notify({'text':'hello'})))
        with patch.dict(os.environ, {'EMAIL_HOME_ADDRESS':'operator@example.invalid'}):
            with patch('subprocess.run') as run:
                run.return_value.returncode=1
                self.assertIn('error',json.loads(notify({'text':'hello'})))

    def test_agent_email_uses_native_sender_with_no_model_supplied_from_identity(self):
        from hermes_diary import notification
        self.assertTrue(hasattr(notification, 'send_email'))
        with patch.dict(os.environ, {'EMAIL_ADDRESS':'agent@example.invalid'}), patch('subprocess.run') as run:
            run.return_value.returncode=0
            value=json.loads(notification.send_email({'recipient':'contact@example.invalid','text':'Hello'}))
        self.assertTrue(value['delivered'])
        self.assertEqual(run.call_args.args[0], ['/usr/local/bin/hermes','send','--to','email:contact@example.invalid','--','Hello'])
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
