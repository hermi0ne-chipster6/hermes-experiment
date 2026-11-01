from pathlib import Path
import os
import subprocess
import tempfile
import unittest


HOOK=Path(__file__).resolve().parents[1]/'sdks/hermes-execution/hooks/check-health'


class WorkerHealthTests(unittest.TestCase):
    hook = HOOK
    def invoke(self, code):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            (root/'timeout').write_text(f'#!/bin/bash\nexit {code}\n')
            (root/'workshopctl').write_text('#!/bin/bash\nprintf "%s\\n" "$*"\n')
            for path in root.iterdir():path.chmod(0o755)
            return subprocess.run(['/bin/bash',str(self.hook)],env={'PATH':str(root)+':/usr/bin:/bin','SDK':str(root)},capture_output=True,text=True)

    def test_cold_start_timeout_waits_instead_of_permanently_failing(self):
        result=self.invoke(124)
        self.assertEqual(result.returncode,0)
        self.assertIn('set-health waiting',result.stdout)

    def test_broken_cli_reports_error(self):
        result=self.invoke(1)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('set-health error',result.stdout)

    def test_healthy_cli_reports_okay(self):
        result=self.invoke(0)
        self.assertEqual(result.returncode,0)
        self.assertIn('set-health okay',result.stdout)


class REAHealthTests(WorkerHealthTests):
    hook = HOOK.parents[2] / 'hermes-rea/hooks/check-health'


class AgentHealthTests(WorkerHealthTests):
    hook = HOOK.parents[2] / 'hermes-experiment/hooks/check-health'
