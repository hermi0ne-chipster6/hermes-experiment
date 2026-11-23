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
        roles = {record['name']: record['roles'] for record in records}
        self.assertEqual(roles['sui'], ['sui-cli'])
        self.assertEqual(roles['npm:@stripe/link-cli'], ['stripe-link-cli'])

    def test_transitive_locks_are_monitored_with_all_pinned_versions(self):
        records = inventory(ROOT)
        client = next(r for r in records if r['name'] == 'npm:@modelcontextprotocol/server')
        self.assertIn('2.3.1', client['versions'])
        self.assertIn('2.0.0-alpha.4', client['versions'])
        self.assertGreater(len([r for r in records if r['kind'] == 'pypi']), 150)

    def test_upstream_worker_locks_are_inventoried_and_bound_to_source_revisions(self):
        records = inventory(ROOT)
        self.assertTrue(any(r['kind']=='pypi' and 'hermes-execution' in r['roles'] for r in records))
        self.assertTrue(any(r['kind']=='npm' and 'upstream-locks/hermes/' in ' '.join(r['inputs']) for r in records))
        self.assertTrue(any(r['kind']=='upstream-lock' and 'opensandbox' in r['name'] for r in records))

    def test_hermes_pnpm_integrity_and_browser_lock_are_inventoried(self):
        records = {record['name']: record for record in inventory(ROOT)}
        sources = json.loads((ROOT/'sources.json').read_text())
        self.assertEqual(records['npm:pnpm']['current'], sources['hermes']['package_manager'])
        self.assertIn('release/upstream-locks/hermes/pm/lock.json', records['npm:pnpm']['inputs'])
        self.assertIn('release/upstream-locks/hermes/pnpm-lock.yaml', records['npm:@nous-research/ui']['inputs'])
        self.assertIn('sdks/hermes-experiment/core-requirements.txt', records['pypi:browser-harness']['inputs'])

    def test_pnpm_manifest_changes_require_a_matching_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('release', 'sdks', 'ci'):
                shutil.copytree(ROOT/name, root/name, ignore=shutil.ignore_patterns('*.sdk', '__pycache__'))
            shutil.copy(ROOT/'sources.json', root/'sources.json')
            path = root/'release/upstream-locks/hermes/web/package.json'
            manifest = json.loads(path.read_text())
            manifest['dependencies']['@nous-research/ui'] = '99.0.0'
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'pnpm manifest disagrees'):
                inventory(root)

    def test_npm_aliases_monitor_the_real_package_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('release', 'sdks', 'ci'):
                shutil.copytree(ROOT/name, root/name, ignore=shutil.ignore_patterns('*.sdk', '__pycache__'))
            shutil.copy(ROOT/'sources.json', root/'sources.json')
            path = root/'sdks/hermes-rea/npm/package-lock.json'
            lock = json.loads(path.read_text())
            lock['packages']['node_modules/alias-name'] = {'name':'real-package','version':'1.0.0'}
            path.write_text(json.dumps(lock))
            names = {r['name'] for r in inventory(root)}
            self.assertIn('npm:real-package', names)
            self.assertNotIn('npm:alias-name', names)

    def test_unsupported_manifests_cannot_hide_under_a_classified_part(self):
        for filename in ('pyproject.toml', 'pnpm-lock.yaml', 'npm-shrinkwrap.json'):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for name in ('release', 'sdks', 'ci'):
                    shutil.copytree(ROOT/name, root/name, ignore=shutil.ignore_patterns('*.sdk', '__pycache__'))
                shutil.copy(ROOT/'sources.json', root/'sources.json')
                (root/'sdks/hermes-rea/npm'/filename).write_text('{}')
                with self.assertRaisesRegex(ValueError, 'unclassified'):
                    inventory(root)

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

    def test_version_file_cannot_disagree_with_source_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('release', 'sdks', 'ci'):
                shutil.copytree(ROOT/name, root/name, ignore=shutil.ignore_patterns('*.sdk', '__pycache__'))
            shutil.copy(ROOT/'sources.json', root/'sources.json')
            (root/'sdks/hermes-experiment/VERSION').write_text('99.0.0\n')
            with self.assertRaisesRegex(ValueError, 'pin mismatch'):
                inventory(root)

    def test_npm_manifest_changes_require_a_matching_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('release', 'sdks', 'ci'):
                shutil.copytree(ROOT/name, root/name, ignore=shutil.ignore_patterns('*.sdk', '__pycache__'))
            shutil.copy(ROOT/'sources.json', root/'sources.json')
            path = root/'sdks/hermes-rea/npm/package.json'
            document = json.loads(path.read_text())
            document['dependencies']['rea-agents'] = '99.0.0'
            path.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError, 'npm manifest'):
                inventory(root)

    def test_new_python_input_pin_requires_regenerating_the_frozen_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('release', 'sdks', 'ci'):
                shutil.copytree(ROOT/name, root/name, ignore=shutil.ignore_patterns('*.sdk', '__pycache__'))
            shutil.copy(ROOT/'sources.json', root/'sources.json')
            path = root/'sdks/hermes-experiment/plugin-requirements.in'
            path.write_text(path.read_text().replace('opensandbox-mcp==1.2.0','opensandbox-mcp==99.0.0'))
            with self.assertRaisesRegex(ValueError, 'Python input'):
                inventory(root)
