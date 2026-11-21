from pathlib import Path
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'sdks/hermes-experiment/assets/wrappers/hermes'


class RuntimeWrapperTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(WRAPPER.exists(), 'runtime wrapper has not been implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root/'wrappers').mkdir()
        (root/'bin').mkdir()
        self.wrapper = root/'wrappers/hermes'
        self.home = root / '.hermes'
        self.project = root / 'project'
        mount = root / 'configuration'
        for directory in (self.home, self.project, mount):
            directory.mkdir()
        charter = mount / 'original-charter.md'
        shutil.copyfile(ROOT / 'deployment/a/original-charter.md.example', charter)
        (self.project / '.hermes.md').symlink_to(charter)
        wrapper = WRAPPER.read_text().replace('/home/workshop/.hermes', str(self.home))
        wrapper = wrapper.replace('/etc/hermes-experiment/original-charter.md', str(charter))
        wrapper = wrapper.replace('/project', str(self.project))
        self.wrapper.write_text(wrapper)
        self.wrapper.chmod(0o755)
        python = root / 'bin/python'
        python.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n')
        python.chmod(0o755)
        shutil.copyfile(WRAPPER.with_name('check-configuration.py'),
                        self.wrapper.with_name('check-configuration.py'))
        fake = root/'bin/hermes'
        fake.write_text('#!/bin/bash\nprintf "real-hermes:%s:%s\\n" "$1" "${EMAIL_PASSWORD:+credential-present}"\n')
        fake.chmod(0o755)
        ctl = root/'bin/workshopctl'
        ctl.write_text('#!/bin/bash\necho "unconnected" >&2\nexit 3\n')
        ctl.chmod(0o755)
        self.env = {'PATH':str(root/'bin')+':/usr/bin:/bin','HOME':str(root)}

    def invoke(self, *args, extra=None):
        return subprocess.run([str(self.wrapper), *args], env={**self.env, **(extra or {})}, capture_output=True, text=True)

    def test_offline_version_does_not_request_credentials(self):
        result = self.invoke('--version')
        self.assertEqual(result.returncode, 0)
        self.assertNotIn('unconnected', result.stderr)

    def test_uncontrolled_runtime_update_is_blocked(self):
        result = self.invoke('update')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('real-hermes', result.stdout)
        self.assertIn('workshop refresh', result.stderr)

    def test_chat_refuses_missing_operator_configuration(self):
        result = self.invoke('chat', '--oneshot', '-q', 'synthetic')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('real-hermes', result.stdout)

    def test_plugin_operations_reach_upstream_with_valid_profile(self):
        profile = self.home / 'config.yaml'
        # The fixture changes the shell launch directory only. The validated
        # configuration still models Workshop's real /project.
        profile.write_text('terminal: {cwd: /project}\n')
        for action in ('install', 'update', 'enable', 'disable', 'remove'):
            with self.subTest(action=action):
                result = self.invoke('plugins', action, 'sdk-fixture')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('real-hermes:plugins:', result.stdout)

    def test_existing_credential_is_used_without_printing_it(self):
        result = self.invoke('send', '--to', 'email:operator@example.invalid', 'hello', extra={'EMAIL_PASSWORD':'synthetic-secret'})
        self.assertEqual(result.returncode, 0)
        self.assertIn('credential-present', result.stdout)
        self.assertNotIn('synthetic-secret', result.stdout+result.stderr)

    def test_secret_lookup_uses_registered_experiment_namespace(self):
        root = Path(self.temp.name)
        calls = root/'secret-lookups'
        (root/'bin/workshopctl').write_text(
            '#!/bin/bash\n'
            'printf "%s\\n" "$2" >> "$HOME/secret-lookups"\n'
            'case "$2" in hermes-experiment.*) printf "synthetic-secret\\n" ;; *) exit 3 ;; esac\n'
        )
        result = self.invoke('send', '--to', 'email:operator@example.invalid', 'hello',
                             extra={'HERMES_PROVIDER_KEY_ENV':'OPENAI_API_KEY'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('credential-present', result.stdout)
        self.assertEqual(calls.read_text().splitlines(), [
            'hermes-experiment.buzz-key', 'hermes-experiment.email-password',
            'hermes-experiment.sandbox-api-key', 'hermes-experiment.model-key',
        ])
        self.assertNotIn('synthetic-secret', result.stdout+result.stderr)

    def test_profile_override_cannot_redirect_native_sender_or_configuration(self):
        for arguments in (('send','--profile','other'),('send','--profile=other'),('send','-p','other'),('send','-pother')):
            result=self.invoke(*arguments)
            self.assertEqual(result.returncode,64,result.stdout+result.stderr)
            self.assertNotIn('real-hermes',result.stdout)

    def test_literal_email_text_after_separator_is_not_a_profile_override(self):
        result=self.invoke('send','--to','email:recipient@example.invalid','--','--profile=literal-text')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('real-hermes:send:',result.stdout)


if __name__ == '__main__':
    unittest.main()
