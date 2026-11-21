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


class RuntimeDependencyRefreshTests(unittest.TestCase):
    def test_native_currency_probe_only_syncs_existing_stale_generation(self):
        import runpy
        from types import ModuleType
        from unittest.mock import Mock, patch

        path = CHECKER.with_name('sync-plugin-dependencies.py')
        sync = runpy.run_path(str(path))['sync']
        pm = ModuleType('pm')
        pm.sync_venv = Mock()
        environments = ModuleType('pm.environments')
        install = ModuleType('pm.install')
        root = Path('/synthetic/sdk/hermes-src')
        environments.committed_venv = Mock(return_value=None)
        install.venv_is_current = Mock()
        with patch.dict(sys.modules, {'pm': pm, 'pm.environments': environments,
                                     'pm.install': install}):
            sync(root)
            install.venv_is_current.assert_not_called()
            pm.sync_venv.assert_not_called()
            environments.committed_venv.return_value = Path('/synthetic/profile/installs/venv')
            install.venv_is_current.return_value = True
            sync(root)
            install.venv_is_current.assert_called_once_with(project_root=root)
            pm.sync_venv.assert_not_called()

            install.venv_is_current.side_effect = [False, True]
            sync(root)
            pm.sync_venv.assert_called_once_with(explicit=True)
            self.assertEqual(install.venv_is_current.call_count, 3)

            install.venv_is_current.side_effect = None
            install.venv_is_current.return_value = False
            pm.sync_venv.side_effect = RuntimeError('synthetic resolution failure')
            with self.assertRaisesRegex(RuntimeError, 'synthetic resolution failure'):
                sync(root)
