import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest


CHECKER = (Path(__file__).resolve().parents[1] /
           'sdks/hermes-experiment/assets/wrappers/check-core.py')


class RuntimeIdentityTests(unittest.TestCase):
    def test_requires_the_exact_install_stamp_and_real_cli_version(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory)
            pins = {'baseVersion': '0.28.4', 'commit': '0123456789' * 4,
                    'pythonVersion': platform.python_version()}
            manifest = sdk / 'share/hermes/core-pin.json'
            source = sdk / 'hermes-src'
            stamp = source / 'install-stamp.json'
            manifest.parent.mkdir(parents=True)
            source.mkdir()
            manifest.write_text(json.dumps(pins))
            identity = {**pins, 'distribution': 'sdkcraft', 'updateMechanism': 'external'}
            stamp.write_text(json.dumps(identity))
            command = [sys.executable, str(CHECKER), str(sdk)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)

            launch = sdk / 'hermes'
            launch.write_text('#!/bin/sh\nprintf "%s\\n" "Hermes Agent v0.28.4 (fixture)" '
                              f'"Install directory: {source}" "Python: {pins["pythonVersion"]}"\n')
            launch.chmod(0o755)
            self.assertEqual(subprocess.run([*command, str(launch)], capture_output=True).returncode, 0)

            launch.write_text(launch.read_text().replace('0.28.4', '0.28.5'))
            self.assertNotEqual(subprocess.run([*command, str(launch)], capture_output=True).returncode, 0)

            stamp.write_text(json.dumps({**identity, 'commit': 'f' * 40}))
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
