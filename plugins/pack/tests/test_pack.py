"""Check pack identity and separation from the bundled inventory."""

import json
from pathlib import Path
import unittest

import yaml


PACK = Path(__file__).resolve().parents[1]
ROOT = PACK.parents[1]


class PluginPackTests(unittest.TestCase):
    def test_pack_uses_exact_independently_installable_catalog_sources(self):
        catalog = yaml.safe_load((PACK / 'catalog.yaml').read_text())
        pack = yaml.safe_load((PACK / 'hermes-pack.yaml').read_text())
        entries = {entry['name']: entry for entry in catalog['plugins']}
        self.assertEqual(len(entries), len(catalog['plugins']))
        self.assertEqual(pack['version'], catalog['version'])
        self.assertNotIn('config', pack)
        self.assertNotIn('skills', pack)
        for entry in entries.values():
            self.assertRegex(entry['ref'], r'^[0-9a-f]{40}$')
        expected = {
            (entry['name'], entry['repository'], entry['ref'])
            for entry in entries.values() if entry['distribution'] == 'native-pack'
        }
        self.assertEqual({(item['name'], item['repo'], item['ref']) for item in pack['plugins']}, expected)
        self.assertEqual(len(pack['plugins']), len(expected))
        self.assertEqual(entries['mandate']['qualification'], 'historical-scanner-block')
        self.assertEqual(entries['rea']['distribution'], 'sdk-bundled-provenance-only')

    def test_existing_core_and_bundle_provenance_matches_repository_pins(self):
        catalog = yaml.safe_load((PACK / 'catalog.yaml').read_text())
        entries = {entry['name']: entry for entry in catalog['plugins']}
        sources = json.loads((ROOT / 'sources.json').read_text())
        self.assertEqual(catalog['hermes']['ref'], sources['hermes_commit'])
        self.assertEqual(catalog['hermes']['tag'], sources['hermes']['tag'])
        for name in ('hindsight', 'hermes_otel', 'rea'):
            with self.subTest(name=name):
                source = sources[f'{name}_plugin']
                entry = entries[name]
                self.assertEqual((entry['repository'], entry['ref'], entry['path']),
                                 (source['repo'], source['sha'], source['subdir']))


if __name__ == '__main__':
    unittest.main()
