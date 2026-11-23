from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / 'sdks/hermes-experiment/assets/wrappers/check-configuration.py'
EXAMPLE = ROOT / 'deployment/a/config.yaml.example'
DISABLED = ['terminal', 'file', 'browser', 'code_execution', 'computer_use', 'delegation',
            'skills', 'connections', 'kanban', 'catalog', 'project', 'desktop_ui']
LEGACY = ['memory', 'todo', 'session_search', 'cronjob', 'clarify', 'hermes_diary',
          'hermes_notifications', 'hermes_artifacts', 'mcp-opensandbox', 'mcp-rea', 'mcp-link']


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.seed = self.root / 'config.yaml'
        self.profile = self.home / 'config.yaml'
        self.sdk = self.root / 'sdk'
        for name in ('hindsight', 'hermes_otel', 'rea', 'hermes_diary',
                     'hermes_notifications'):
            (self.sdk / 'plugins' / name).mkdir(parents=True)
        shipped = self.sdk / 'share/hermes/enabled-features.json'
        shipped.parent.mkdir(parents=True)
        shipped.write_text('{"schema":1,"extras":["mcp","web"]}')

    def run_validator(self, *arguments):
        return subprocess.run([sys.executable, str(VALIDATOR), *map(str, arguments)],
                              capture_output=True, text=True)

    def setup_profile(self):
        return self.run_validator('--setup', self.home, self.seed, self.sdk)

    def legacy(self):
        config = yaml.safe_load(EXAMPLE.read_text())
        config['agent'] = {'disabled_toolsets': DISABLED.copy()}
        for platform in ('cli', 'buzz', 'email', 'cron'):
            config['platform_toolsets'][platform] = LEGACY.copy()
        return config

    def check(self, config):
        self.seed.write_text(json.dumps(config))
        return self.run_validator(self.seed)

    def test_upstream_default_and_operator_selected_toolsets_are_accepted(self):
        config = self.legacy()
        self.assertEqual(self.check(config).returncode, 0)
        config['agent']['disabled_toolsets'] = '["browser"]'
        config['platform_toolsets']['cli'] = ['hermes-cli', 'terminal']
        config['platform_toolsets']['cron'] = '["memory"]'
        self.assertEqual(self.check(config).returncode, 0)
        config.pop('agent')
        self.assertEqual(self.check(config).returncode, 0)

    def test_rejects_malformed_config_without_dumping_values(self):
        for config in ({}, {'agent': 'synthetic-secret', 'terminal': {'cwd': '/project'}},
                       {'platform_toolsets': {'cron': True}, 'terminal': {'cwd': '/project'}},
                       {'plugins': {'disabled': 42}, 'terminal': {'cwd': '/project'}}):
            with self.subTest(config=config):
                result = self.check(config)
                self.assertEqual(result.returncode, 78)
                self.assertNotIn('synthetic-secret', result.stderr)

    def test_context_directory_cannot_omit_the_governing_charter(self):
        config = self.legacy()
        config['terminal']['cwd'] = '/tmp/synthetic'
        self.assertNotEqual(self.check(config).returncode, 0)

    def test_explicit_context_cap_cannot_truncate_the_original_charter(self):
        config = self.legacy()
        config['context_file_max_chars'] = 200
        self.assertNotEqual(self.check(config).returncode, 0)

    def test_migrates_legacy_link_once_with_original_recovery_copy(self):
        legacy = self.legacy()
        legacy['display'] = {'compact': True}
        original = '# Operator comment\n' + yaml.safe_dump(legacy)
        self.seed.write_text(original)
        self.profile.symlink_to(self.seed)
        result = self.setup_profile()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.profile.is_symlink())
        self.assertEqual(self.profile.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.seed.read_text(), original)
        recovery = self.home / 'config.yaml.pre-sdk-migration'
        self.assertEqual(recovery.read_text(), original)
        self.assertEqual(recovery.stat().st_mode & 0o777, 0o600)
        current = yaml.safe_load(self.profile.read_text())
        self.assertIn('# Operator comment', self.profile.read_text())
        self.assertEqual(current['agent']['disabled_toolsets'], [])
        self.assertIn('hermes-cli', current['platform_toolsets']['cli'])
        self.assertNotIn('hermes_artifacts', current['platform_toolsets']['cli'])
        for platform in ('buzz', 'email', 'cron'):
            self.assertEqual(current['platform_toolsets'][platform], legacy['platform_toolsets'][platform])
        self.assertEqual(current['mcp_servers'], legacy['mcp_servers'])
        self.assertEqual(current['display'], legacy['display'])
        edited = self.profile.read_text() + '\n# edit after migration\n'
        self.profile.write_text(edited)
        self.seed.write_text('irrelevant after migration')
        self.assertEqual(self.setup_profile().returncode, 0)
        self.assertEqual(self.profile.read_text(), edited)
        self.assertEqual(recovery.read_text(), original)

    def test_preserves_operator_tool_restrictions_and_existing_cron_overrides(self):
        for overrides in ('edited', 'job'):
            with self.subTest(overrides=overrides):
                legacy = self.legacy()
                if overrides == 'edited':
                    legacy['agent']['disabled_toolsets'].remove('browser')
                else:
                    (self.home / 'cron').mkdir(exist_ok=True)
                    (self.home / 'cron/jobs.json').write_text(
                        json.dumps({'jobs': [{'enabled_toolsets': ['hermes-cron']}]}))
                self.seed.write_text(yaml.safe_dump(legacy))
                self.profile.unlink(missing_ok=True)
                self.profile.symlink_to(self.seed)
                result = self.setup_profile()
                self.assertEqual(result.returncode, 0, result.stderr)
                current = yaml.safe_load(self.profile.read_text())
                self.assertEqual(current['agent'], legacy['agent'])
                self.assertIn('hermes-cli', current['platform_toolsets']['cli'])

    def test_refuses_unexpected_profile_link_and_preserves_both_files(self):
        self.seed.write_text(EXAMPLE.read_text())
        other = self.root / 'other.yaml'
        other.write_text('operator-managed')
        self.profile.symlink_to(other)
        result = self.setup_profile()
        self.assertEqual(result.returncode, 78)
        self.assertEqual(self.profile.readlink(), other)
        self.assertEqual(other.read_text(), 'operator-managed')

    def test_bundle_seeding_leaves_user_plugins_and_disabled_names_alone(self):
        config = yaml.safe_load(EXAMPLE.read_text())
        config['plugins']['disabled'] = ['hermes_otel']
        self.seed.write_text(yaml.safe_dump(config))
        plugins = self.home / 'plugins'
        plugins.mkdir()
        user = plugins / 'hermes_diary'
        user.mkdir()
        (user / 'owner').write_text('user-managed')
        dangling = plugins / 'hermes_notifications'
        dangling.symlink_to(self.root / 'unrelated')
        result = self.setup_profile()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((user / 'owner').read_text(), 'user-managed')
        self.assertEqual(dangling.readlink(), self.root / 'unrelated')
        self.assertFalse((plugins / 'hermes_otel').exists())
        generated = plugins / 'hindsight'
        self.assertEqual(generated.readlink(), self.sdk / 'plugins/hindsight')
        self.assertEqual((self.home / 'enabled-features.json').resolve(),
                         self.sdk / 'share/hermes/enabled-features.json')
        generated.unlink()
        config['plugins']['enabled'].remove('hindsight')
        config['memory']['provider'] = 'builtin'
        self.profile.write_text(yaml.safe_dump(config))
        self.assertEqual(self.setup_profile().returncode, 0)
        self.assertFalse(generated.exists())

    def test_retires_only_the_obsolete_sdk_transfer_symlink(self):
        self.seed.write_text(EXAMPLE.read_text())
        plugins = self.home / 'plugins'
        plugins.mkdir()
        retired = plugins / 'hermes_artifacts'
        retired.symlink_to(self.sdk / 'plugins' / retired.name)
        self.assertEqual(self.setup_profile().returncode, 0)
        self.assertFalse(retired.is_symlink())
        retired.mkdir()
        self.assertEqual(self.setup_profile().returncode, 0)
        self.assertTrue(retired.is_dir())

    def test_legacy_profile_preserves_independently_managed_transfer_tools(self):
        config = self.legacy()
        config['known_plugin_toolsets'] = {'cli': ['hermes_artifacts']}
        self.seed.write_text(yaml.safe_dump(config))
        self.profile.symlink_to(self.seed)
        custom = self.home / 'plugins/hermes_artifacts'
        custom.mkdir(parents=True)
        marker = custom / 'owner'
        marker.write_text('operator')
        result = self.setup_profile()
        self.assertEqual(result.returncode, 0, result.stderr)
        migrated = yaml.safe_load(self.profile.read_text())
        self.assertIn('hermes_artifacts', migrated['platform_toolsets']['cli'])
        self.assertEqual(migrated['known_plugin_toolsets'], config['known_plugin_toolsets'])
        self.assertEqual(marker.read_text(), 'operator')
