from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

VALIDATOR = Path(__file__).resolve().parents[1] / 'sdks/hermes-experiment/assets/wrappers/check-configuration.py'
DISABLED = ['terminal', 'file', 'browser', 'code_execution', 'computer_use', 'delegation',
            'skills', 'connections', 'kanban', 'catalog', 'project', 'desktop_ui']


class ConfigurationTests(unittest.TestCase):
    def check(self, config):
        self.assertTrue(VALIDATOR.exists(), 'runtime configuration guard is missing')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps(config))
            return subprocess.run([sys.executable, str(VALIDATOR), str(path)],
                                  capture_output=True, text=True)

    def safe(self):
        return {'agent': {'disabled_toolsets': DISABLED},
                'terminal': {'cwd': '/project'},
                'platform_toolsets': {p:['memory', 'hermes_diary', 'mcp-rea'] for p in ('cli','buzz','email','cron')}}

    def test_safe_execution_restrictions_are_accepted(self):
        self.assertEqual(self.check(self.safe()).returncode, 0)

    def test_empty_or_missing_restrictions_fail_closed(self):
        self.assertNotEqual(self.check({}).returncode, 0)
        config = self.safe()
        config['agent']['disabled_toolsets'] = []
        self.assertNotEqual(self.check(config).returncode, 0)

    def test_platform_wildcards_or_local_toolsets_are_rejected(self):
        for tool in ('all', '*', 'terminal', 'skills'):
            config = self.safe()
            config['platform_toolsets']['cron'] = [tool]
            self.assertNotEqual(self.check(config).returncode, 0)

    def test_context_directory_cannot_omit_the_governing_charter(self):
        config = self.safe()
        config['terminal']['cwd'] = '/tmp/untrusted'
        self.assertNotEqual(self.check(config).returncode, 0)

    def test_explicit_context_cap_cannot_truncate_the_original_charter(self):
        config = self.safe()
        config['context_file_max_chars'] = 200
        self.assertNotEqual(self.check(config).returncode, 0)
