from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / 'deployment/enter-heartbeat'
SDK = ROOT / 'sdks/hermes-experiment'


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
        self.assertIn('--format', arguments)
        self.assertEqual(arguments[arguments.index('--format') + 1], 'stream-json')
        self.assertIn('--create-if-missing', arguments)
        self.assertNotIn('--run-budget', arguments)
        self.assertNotIn('--no-restore-cwd', arguments)
        self.assertIn('"run_id":"' + 'a' * 32 + '"', arguments[-1])
        self.assertIn('"commitments"', arguments[-1])
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
        self.assertIn('--format', arguments)
        self.assertEqual(arguments[arguments.index('--format') + 1], 'stream-json')
        self.assertNotIn('--run-budget', arguments)
        self.assertIn('"run_id":"' + 'a' * 32 + '"', arguments[-1])

    def test_missing_correlation_fails_before_entering_workshop(self):
        result = self.invoke(missing=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')


class GatewayServiceTests(unittest.TestCase):
    def test_workshop_gateway_keeps_its_environment_and_launcher_after_unit_regeneration(self):
        name = 'hermes-gateway.service.d/50-hermes-experiment.conf'
        drop_in = (SDK / 'services' / name).read_text()
        setup = (SDK / 'hooks/setup-project').read_text()
        self.assertIn(f'gateway_drop_in={name}', setup)
        self.assertIn('install -D --mode=644 "$SDK/$gateway_drop_in" "$gateway_unit_directory/$gateway_drop_in"', setup)
        self.assertIn('ConditionPathExists=/etc/hermes-experiment/gateway.enabled', drop_in)
        self.assertIn('WorkingDirectory=/project', drop_in)
        self.assertIn('EnvironmentFile=-/etc/hermes-experiment/gateway.env', drop_in)
        self.assertEqual([line for line in drop_in.splitlines() if line.startswith('ExecStart=')],
                         ['ExecStart=', 'ExecStart=/usr/local/bin/hermes gateway run'])

    def test_setup_retries_an_unapplied_gateway_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / 'sdk'
            home = root / 'home'
            operator = root / 'operator'
            project = root / 'project'
            shutil.copytree(SDK / 'services', sdk)
            (sdk / 'bin').mkdir()
            interpreter = sdk / 'bin/python'
            interpreter.write_text('#!/bin/bash\nexit 0\n')
            interpreter.chmod(0o755)
            (sdk / 'share/hermes').mkdir(parents=True)
            (sdk / 'share/hermes/SOUL.md').write_text('fixture charter context\n')
            operator.mkdir()
            (operator / 'gateway.enabled').touch()
            (project / '.hermes-charter').mkdir(parents=True)
            (project / '.hermes-charter/original-charter.md').touch()
            systemctl = root / 'systemctl'
            systemctl.write_text(
                '#!/bin/bash\n'
                'printf "%s\\n" "$*" >> "$GATEWAY_FIXTURE_LOG"\n'
                'if [[ $2 == restart && $GATEWAY_FIXTURE_FAIL == 1 ]]; then exit 1; fi\n'
            )
            systemctl.chmod(0o755)
            hook = (SDK / 'hooks/setup-project').read_text()
            script = hook.replace('/etc/hermes-experiment', str(operator)).replace('/project', str(project))
            log = root / 'systemctl.log'
            environment = {'PATH': f'{root}:/usr/bin:/bin', 'HOME': str(home), 'SDK': str(sdk),
                           'GATEWAY_FIXTURE_LOG': str(log)}
            exits = []
            for fail in ('1', '0', '0'):
                result = subprocess.run(['bash'], input=script, text=True, capture_output=True,
                                        env={**environment, 'GATEWAY_FIXTURE_FAIL': fail})
                exits.append(result.returncode)
            self.assertEqual(exits, [1, 0, 0])
            operations = [line for line in log.read_text().splitlines()
                          if line.startswith(('--user restart ', '--user start '))]
            self.assertEqual(operations, ['--user restart hermes-gateway.service',
                                          '--user restart hermes-gateway.service',
                                          '--user start hermes-gateway.service'])
