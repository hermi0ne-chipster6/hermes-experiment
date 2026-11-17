"""Source-built REA pins must remain connected to release monitoring."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from release.inventory import inventory
from release.monitor import inspect_component
from test_monitor import FixtureClient

ROOT = Path(__file__).resolve().parents[1]


class ReaInventoryTests(unittest.TestCase):
    def checkout(self, directory):
        destination = Path(directory)
        for name in ('release', 'sdks', 'ci'):
            shutil.copytree(ROOT/name, destination/name,
                            ignore=shutil.ignore_patterns('*.sdk', '__pycache__'))
        shutil.copyfile(ROOT/'sources.json', destination/'sources.json')
        return destination

    def test_source_commit_and_active_lock_are_monitored(self):
        records = {item['name']:item for item in inventory(ROOT)}
        self.assertEqual(records['rea']['kind'], 'github-commit')
        self.assertEqual(records['rea']['current'], json.loads((ROOT/'sdks/hermes-rea/SOURCE.json').read_text())['commit'])
        self.assertEqual(records['node:rea']['current'], 'v24.22.1')
        self.assertEqual(records['node']['roles'], ['hermes-experiment'])
        self.assertIn('release/upstream-locks/rea/package-lock.json', records['npm:playwright-core']['inputs'])
        self.assertEqual(records['ilspy']['current'], '11.2.0.10050')

    def test_changed_source_metadata_requires_reviewed_pin_update(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.checkout(directory)
            path = root/'sdks/hermes-rea/SOURCE.json'
            value = json.loads(path.read_text()); value['commit'] = 'a'*40
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'pin mismatch'):
                inventory(root)

    def test_changed_provider_archive_requires_monitor_metadata_update(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.checkout(directory)
            path = root/'sdks/hermes-rea/sdkcraft.yaml'
            path.write_text(path.read_text().replace('wabt-1.0.42-linux-x64.tar.gz', 'wabt-1.0.43-linux-x64.tar.gz'))
            with self.assertRaisesRegex(ValueError, 'maintenance metadata'):
                inventory(root)

    def test_source_commit_monitor_detects_same_version_main_change(self):
        record = dict(name='rea', kind='github-commit', repository='morluto/rea', ref='main', current='a'*40, roles=['hermes-rea'], inputs=['sources.json'])
        for revision, status in [('a'*40,'current'), ('b'*40,'review-required')]:
            result = inspect_component(record, FixtureClient({'/commits/main':{'sha':revision}}))
            self.assertEqual(result['status'], status)
        with self.assertRaisesRegex(ValueError, 'immutable revision'):
            inspect_component(record, FixtureClient({'/commits/main':{'sha':'main'}}))

    def test_provider_wheel_digest_is_bound_to_its_frozen_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.checkout(directory)
            path = root/'sdks/hermes-rea/dependencies/assets.json'
            value = json.loads(path.read_text())
            asset = next(item for item in value['assets'] if item['name'] == 'agentenv-framework')
            asset['sha256'] = '0'*64
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'locked provider asset'):
                inventory(root)

    def test_nuget_monitor_uses_four_part_stable_versions(self):
        record = dict(name='ilspy', kind='nuget', package='ilspycmd.linux-x64', current='11.2.0.10050', roles=['hermes-rea'], inputs=['components.json'])
        client = FixtureClient({'/ilspycmd.linux-x64/index.json':{'versions':['11.2.0.10050','11.2.1.10060','12.0.0-preview.1']}})
        result = inspect_component(record, client)
        self.assertEqual(result['candidate']['version'], '11.2.1.10060')
        self.assertEqual(result['status'], 'review-required')
