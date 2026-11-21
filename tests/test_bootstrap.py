from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'sdks/hermes-experiment/assets/bootstrap/hermes'


class BootstrapTests(unittest.TestCase):
    def test_working_directory_cannot_override_immutable_source_imports(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            (root/'bin').mkdir()
            (root/'bin/python').symlink_to(sys.executable)
            shutil.copyfile(SOURCE,root/'bin/hermes')
            (root/'bin/hermes').chmod(0o755)
            package=root/'hermes-src/hermes_cli'
            package.mkdir(parents=True)
            (package.parent/'hermes_bootstrap.py').write_text('# Native bootstrap fixture.\n')
            (package/'__init__.py').write_text('')
            (package/'main.py').write_text('import json\ndef main():\n    return 0\n')
            cwd=root/'untrusted'
            cwd.mkdir()
            (cwd/'json.py').write_text('raise RuntimeError("working directory import")\n')
            result=subprocess.run([str(root/'bin/hermes'),'--version'],cwd=cwd,
                                  env={'PATH':'/usr/bin:/bin'},capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_native_cli_exit_code_survives_source_bootstrap(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            (root/'bin').mkdir()
            (root/'bin/python').symlink_to(sys.executable)
            shutil.copyfile(SOURCE,root/'bin/hermes')
            (root/'bin/hermes').chmod(0o755)
            package=root/'hermes-src/hermes_cli'
            package.mkdir(parents=True)
            (package.parent/'hermes_bootstrap.py').write_text('# Native bootstrap fixture.\n')
            (package/'__init__.py').write_text('')
            (package/'main.py').write_text('def main():\n    return 7\n')
            result=subprocess.run([str(root/'bin/hermes'),'--version'],env={'PATH':'/usr/bin:/bin'},capture_output=True,text=True)
            self.assertEqual(result.returncode,7,result.stderr)

    def test_dashboard_defaults_to_the_packaged_dist_and_preserves_overrides(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            executable = root / 'bin/hermes'
            executable.parent.mkdir()
            (executable.parent / 'python').symlink_to(sys.executable)
            shutil.copyfile(SOURCE, executable)
            executable.chmod(0o755)
            package = root / 'hermes-src/hermes_cli'
            package.mkdir(parents=True)
            (package.parent / 'hermes_bootstrap.py').write_text('')
            (package / 'main.py').write_text(
                'import os\ndef main():\n    print(os.environ.get("HERMES_WEB_DIST", ""))\n'
            )
            for override in ('', '/operator/web-dist'):
                with self.subTest(override=override):
                    env = {'PATH': '/usr/bin:/bin'}
                    if override:
                        env['HERMES_WEB_DIST'] = override
                    result = subprocess.run([str(executable), 'dashboard'], env=env,
                                            capture_output=True, text=True, check=True)
                    self.assertEqual(result.stdout.strip(), override or str(package / 'web_dist'))
