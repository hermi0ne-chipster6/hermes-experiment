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
        mount = self.project / '.hermes-charter'
        configuration = root / 'configuration'
        for directory in (self.home, self.project, mount, configuration):
            directory.mkdir()
        charter = mount / 'original-charter.md'
        self.legacy_charter = configuration / 'original-charter.md'
        shutil.copyfile(ROOT / 'deployment/a/original-charter.md.example', charter)
        shutil.copyfile(charter, self.legacy_charter)
        (self.project / '.hermes.md').symlink_to(charter)
        wrapper = WRAPPER.read_text().replace('/home/workshop/.hermes', str(self.home))
        wrapper = wrapper.replace('/project', str(self.project))
        self.wrapper.write_text(wrapper)
        self.wrapper.chmod(0o755)
        python = root / 'bin/python'
        python.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n')
        python.chmod(0o755)
        shutil.copyfile(WRAPPER.with_name('check-configuration.py'),
                        self.wrapper.with_name('check-configuration.py'))
        bootstrap = root/'bin/hermes'
        shutil.copyfile(WRAPPER.parents[1] / 'bootstrap/hermes', bootstrap)
        bootstrap.chmod(0o755)
        source = root/'hermes-src'
        cli = source/'hermes_cli'
        cli.mkdir(parents=True)
        (source/'hermes_bootstrap.py').write_text('')
        (cli/'_parser.py').write_text('''
def scan_profile_flag(args):
    for index, arg in enumerate(args):
        if arg == '--' or (args[:2] == ['mcp', 'add'] and arg == '--args'):
            break
        if arg in ('-p', '--profile') and index+1 < len(args):
            return args[index+1], 2, index
        if arg.startswith('--profile='):
            return arg.split('=', 1)[1], 1, index
    return None, 0, None

def command_argv(args):
    if args[:1] == ['--provider']:
        args = args[2:]
    return args
''')
        (cli/'main.py').write_text('''
import argparse
import os
from pathlib import Path
import subprocess
import sys
from hermes_cli._parser import scan_profile_flag

root = Path(os.environ['HERMES_HOME'])
selector, used, index = scan_profile_flag(sys.argv[1:])
if index is not None:
    del sys.argv[index+1:index+1+used]
elif (root/'active_profile').is_file():
    selector = (root/'active_profile').read_text().strip()
if selector and selector != 'default':
    os.environ['HERMES_HOME'] = str(root/'profiles'/selector)

def cmd_update(args):
    print('native updater reached')
    return 5

def main():
    if sys.argv[1:] == ['--tui']:
        node = os.environ.get('HERMES_NODE')
        if not node:
            print('TUI Node override missing', file=sys.stderr)
            return 1
        return subprocess.call([node])
    if 'update' in sys.argv[1:] and sys.argv[1].startswith('--'):
        parser = argparse.ArgumentParser()
        parser.add_argument('--provider')
        parser.add_argument('--model')
        parser.add_argument('--reasoning')
        update = parser.add_subparsers().add_parser('update')
        update.set_defaults(func=cmd_update)
        args = parser.parse_args()
        return args.func(args)
    credential = 'credential-present' if os.environ.get('EMAIL_PASSWORD') else ''
    print(f'real-hermes:{sys.argv[1]}:{credential}')
    print(os.environ['HERMES_HOME'])
    print(repr(sys.argv[1:]))
''')
        ctl = root/'bin/workshopctl'
        ctl.write_text('#!/bin/bash\necho "unconnected" >&2\nexit 3\n')
        ctl.chmod(0o755)
        self.env = {'PATH':str(root/'bin')+':/usr/bin:/bin','HOME':str(root)}

    def invoke(self, *args, extra=None):
        return subprocess.run([str(self.wrapper), *args], env={**self.env, **(extra or {})}, capture_output=True, text=True)

    def test_offline_version_does_not_request_credentials(self):
        result = self.invoke('--version')
        self.assertEqual(result.returncode, 0)
        self.assertIn('real-hermes:--version:', result.stdout)
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

    def test_charter_context_must_resolve_inside_the_project(self):
        (self.home / 'config.yaml').write_text('terminal: {cwd: /project}\n')
        link = self.project / '.hermes.md'
        inside = self.project / '.hermes-charter' / 'original-charter.md'
        link.unlink()
        link.symlink_to(self.legacy_charter)

        result = self.invoke('chat', '--oneshot', '-q', 'synthetic')
        self.assertEqual(result.returncode, 78, result.stdout)
        self.assertIn('charter context is required', result.stderr)

        link.unlink()
        link.symlink_to(inside)
        result = self.invoke('chat', '--oneshot', '-q', 'synthetic')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('real-hermes:chat:', result.stdout)

        inside.write_text('altered charter\n')
        result = self.invoke('chat', '--oneshot', '-q', 'synthetic')
        self.assertEqual(result.returncode, 78, result.stdout)
        self.assertIn('differs from the approved original', result.stderr)

    def test_tui_defaults_to_packaged_node_and_preserves_operator_override(self):
        (self.home / 'config.yaml').write_text('terminal: {cwd: /project}\n')
        root = Path(self.temp.name)
        bundled = root / 'node/bin/node'
        bundled.parent.mkdir(parents=True)
        operator = root / 'operator-node'
        for executable, label in ((bundled, 'bundled'), (operator, 'operator')):
            executable.write_text(f'#!/bin/sh\nprintf "%s\\n" {label}\n')
            executable.chmod(0o755)

        for extra, expected in (({}, 'bundled'), ({'HERMES_NODE': str(operator)}, 'operator')):
            with self.subTest(expected=expected):
                result = self.invoke('--tui', extra=extra)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)

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

    def test_native_named_profile_is_dispatched_with_its_own_valid_config(self):
        named = self.home/'profiles/work'
        named.mkdir(parents=True)
        (named/'config.yaml').write_text('terminal: {cwd: /project}\n')
        (self.home/'config.yaml').write_text('terminal: [malformed\n')
        for selector in (('-p', 'work'), ('--profile', 'work'), ('--profile=work',)):
            with self.subTest(selector=selector):
                result = self.invoke(*selector, 'plugins', 'list')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(str(named), result.stdout.splitlines())

    def test_sticky_named_profile_is_validated_before_dispatch(self):
        (self.home/'config.yaml').write_text('terminal: {cwd: /project}\n')
        named = self.home/'profiles/work'
        named.mkdir(parents=True)
        (named/'config.yaml').write_text('terminal: [malformed\n')
        (self.home/'active_profile').write_text('work\n')
        result = self.invoke('config', 'path')
        self.assertEqual(result.returncode, 78, result.stdout+result.stderr)
        self.assertIn('invalid profile', result.stderr)
        self.assertNotIn('real-hermes', result.stdout)
        explicit_default = self.invoke('config', 'path', '--profile=default')
        self.assertEqual(explicit_default.returncode, 0, explicit_default.stderr)
        self.assertIn(str(self.home), explicit_default.stdout.splitlines())

    def test_update_after_global_flag_is_blocked(self):
        (self.home/'config.yaml').write_text('terminal: {cwd: /project}\n')
        for arguments in (('--provider', 'example', 'update'), ('-p', 'default', 'update')):
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual(result.returncode, 64, result.stdout+result.stderr)
                self.assertIn('workshop refresh', result.stderr)
                self.assertNotIn('real-hermes', result.stdout)

    def test_abbreviated_global_options_cannot_reach_core_updater(self):
        (self.home/'config.yaml').write_text('terminal: {cwd: /project}\n')
        for option in ('--prov', '--mod', '--reason'):
            with self.subTest(option=option):
                result = self.invoke(option, 'fixture', 'update')
                self.assertEqual(result.returncode, 64, result.stdout+result.stderr)
                self.assertIn('workshop refresh', result.stderr)
                self.assertNotIn('native updater reached', result.stdout)

    def test_native_mcp_child_arguments_are_preserved(self):
        (self.home/'config.yaml').write_text('terminal: {cwd: /project}\n')
        result = self.invoke('mcp', 'add', 'fixture', '--args', '--profile=literal', '-package')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn("['mcp', 'add', 'fixture', '--args', '--profile=literal', '-package']", result.stdout)

    def test_literal_email_text_after_separator_is_not_a_profile_override(self):
        result=self.invoke('send','--to','email:recipient@example.invalid','--','--profile=literal-text')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('real-hermes:send:',result.stdout)


if __name__ == '__main__':
    unittest.main()
