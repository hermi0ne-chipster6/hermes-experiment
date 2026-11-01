from pathlib import Path
import json
import shutil
import tempfile
import unittest

try:
    from release.inventory import inventory, validate_coverage
except ImportError:
    inventory = validate_coverage = None

ROOT = Path(__file__).resolve().parents[1]


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(inventory, 'complete component inventory is missing')

    def test_all_worker_applications_and_platform_inputs_are_covered(self):
        records = inventory(ROOT)
        names = {r['name'] for r in records}
        self.assertTrue({'hermes', 'opensandbox', 'rea', 'ghidra', 'frida', 'buzz',
                         'sui', 'cloudflared', 'node', 'python', 'docker-sdk',
                         'docker-engine', 'ubuntu-security', 'plugin:rea',
                         'plugin:hindsight', 'plugin:hermes_otel', 'snap:workshop',
                         'snap:sdkcraft', 'snap:lxd', 'snap:astral-uv',
                         'pypi:mcp', 'pypi:hindsight-api-slim', 'npm:@stripe/link-cli',
                         'image:opensandbox/execd', 'ci:gitleaks'} <= names)
        self.assertTrue(all(r['roles'] and r['inputs'] for r in records))

    def test_transitive_locks_are_monitored_with_all_pinned_versions(self):
        records = inventory(ROOT)
        client = next(r for r in records if r['name'] == 'npm:@modelcontextprotocol/server')
        self.assertIn('2.3.1', client['versions'])
        self.assertIn('2.0.0-alpha.4', client['versions'])
        self.assertGreater(len([r for r in records if r['kind'] == 'pypi']), 150)

    def test_new_external_part_cannot_escape_coverage(self):
        import yaml
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(ROOT/'release', root/'release', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT/'sdks', root/'sdks', ignore=shutil.ignore_patterns('*.sdk', '__pycache__'))
            shutil.copytree(ROOT/'ci', root/'ci')
            shutil.copy(ROOT/'sources.json', root/'sources.json')
            file = root/'sdks/hermes-rea/sdkcraft.yaml'
            doc = yaml.safe_load(file.read_text())
            doc['parts']['untracked'] = {'plugin': 'dump', 'source': 'https://example.org/new.tar.gz'}
            file.write_text(yaml.safe_dump(doc))
            with self.assertRaisesRegex(ValueError, 'untracked'):
                validate_coverage(root)

    def test_unknown_lock_format_is_a_coverage_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(ROOT/'release', root/'release', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT/'sdks', root/'sdks', ignore=shutil.ignore_patterns('*.sdk', '__pycache__'))
            shutil.copytree(ROOT/'ci', root/'ci')
            shutil.copy(ROOT/'sources.json', root/'sources.json')
            (root/'poetry.lock').write_text('unclassified lock')
            with self.assertRaisesRegex(ValueError, 'poetry.lock'):
                validate_coverage(root)

    def test_inventory_does_not_modify_pins(self):
        before = (ROOT/'sources.json').read_bytes()
        inventory(ROOT)
        self.assertEqual((ROOT/'sources.json').read_bytes(), before)
