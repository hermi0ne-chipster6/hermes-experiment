from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / 'validation/hermes-agent/probe-qualification.py'
SPEC = importlib.util.spec_from_file_location('probe_qualification', PROBE)
qualification = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qualification)


class QualificationPackTests(unittest.TestCase):
    def test_probes_the_selected_pack_and_separate_mandate_pin(self):
        pack_path = ROOT / 'plugins/pack/hermes-pack.yaml'
        catalog_path = ROOT / 'plugins/pack/catalog.yaml'
        pack = yaml.safe_load(pack_path.read_text())
        catalog = {entry['name']: entry for entry in yaml.safe_load(catalog_path.read_text())['plugins']}
        installs = []
        doctors = []
        removals = []
        with tempfile.TemporaryDirectory() as scratch:
            profile = Path(scratch)
            plugins = profile / 'plugins'
            plugins.mkdir()
            records = {}

            def hermes(*args, **kwargs):
                if args[1] == 'install':
                    identifier, revision = args[2], args[4]
                    self.assertEqual(args[3], '--ref')
                    self.assertEqual(args[5:], ('--no-enable', '--yes-deps'))
                    installs.append((identifier, revision))
                    name = next(name for name, item in catalog.items() if item['ref'] == revision)
                    (plugins / name).mkdir()
                    records[name] = {'pinned': True, 'revision': revision}
                    (plugins / '.install-metadata.json').write_text(json.dumps(records))
                elif args[1] == 'doctor':
                    self.assertEqual(args[3:], ('--ci',))
                    doctors.append(Path(args[2]).name)
                elif args[1] == 'remove':
                    removals.append(args[2])
                else:
                    self.fail(f'Unexpected Hermes command: {args}')

            with (patch.object(qualification, 'PROFILE', profile),
                  patch.object(qualification, 'hermes', hermes), redirect_stdout(io.StringIO())):
                qualification.probe_selected_plugins(pack_path, catalog_path)

        expected = [
            (item['repo'] + ('#' + item['subdir'] if 'subdir' in item else ''), item['ref'])
            for item in pack['plugins']
        ]
        expected.append((catalog['mandate']['repository'], catalog['mandate']['ref']))
        self.assertEqual(installs, expected)
        self.assertEqual(doctors, [item['name'] for item in pack['plugins']] + ['mandate'])
        self.assertEqual(removals, doctors)

    def test_rejects_a_pack_pin_that_disagrees_with_the_catalog_before_installing(self):
        catalog_path = ROOT / 'plugins/pack/catalog.yaml'
        pack = yaml.safe_load((ROOT / 'plugins/pack/hermes-pack.yaml').read_text())
        pack['plugins'][0]['ref'] = '0' * 40
        with tempfile.TemporaryDirectory() as scratch:
            pack_path = Path(scratch) / 'pack.yaml'
            pack_path.write_text(yaml.safe_dump(pack))
            with patch.object(qualification, 'hermes') as hermes:
                with self.assertRaisesRegex(AssertionError, 'promise-keeper'):
                    qualification.probe_selected_plugins(pack_path, catalog_path)
                hermes.assert_not_called()
