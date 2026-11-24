"""Offline verification of the Sui SDK recipe and installation hook."""

import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import tarfile
import tempfile
import unittest

import yaml


SDK = Path(__file__).resolve().parents[1]
ROOT = SDK.parents[1]


class SuiSdkTests(unittest.TestCase):
    def test_recipe_matches_upstream_pin_and_state_contract(self):
        recipe = yaml.safe_load((SDK / 'sdkcraft.yaml').read_text())
        version = (SDK / 'VERSION').read_text().strip()
        pin = json.loads((ROOT / 'sources.json').read_text())['sui']
        self.assertEqual(pin['tag'], f'mainnet-v{version}')
        asset = next(item for item in pin['assets'] if item['name'].endswith('ubuntu-x86_64.tgz'))
        self.assertEqual(recipe['name'], 'sui-cli')
        self.assertEqual(recipe['base'], 'ubuntu@26.04')
        self.assertEqual(recipe['platforms'], {'amd64': None})
        self.assertEqual(recipe['plugs'], {
            'sui-state': {'interface': 'mount', 'workshop-target': '/home/workshop/.sui', 'mode': 0o700},
        })
        part = recipe['parts'][recipe['adopt-info']]
        self.assertIn(asset['url'], part['override-pull'])
        self.assertIn(asset['digest'].removeprefix('sha256:'), part['override-pull'])

    def test_download_checksum_precedes_executable_extraction(self):
        recipe = yaml.safe_load((SDK / 'sdkcraft.yaml').read_text())
        pull = recipe['parts']['sui']['override-pull']
        pin = json.loads((ROOT / 'sources.json').read_text())['sui']
        asset = next(item for item in pin['assets'] if item['name'].endswith('ubuntu-x86_64.tgz'))
        expected_digest = asset['digest'].removeprefix('sha256:')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bin').mkdir()
            (root / 'source').mkdir()
            project = root / 'project'
            license_path = Path('build-source/sui/LICENSE')
            fixture_license = project / license_path
            fixture_license.parent.mkdir(parents=True)
            fixture_license.write_bytes((SDK / license_path).read_bytes())
            fixture_license.chmod(0o600)
            (project / 'VERSION').write_bytes((SDK / 'VERSION').read_bytes())
            archive = root / 'fixture.tgz'
            binary = b'#!/bin/sh\nprintf "%s\\n" "sui 1.82.3-fixture"\n'
            with tarfile.open(archive, 'w:gz') as tar:
                member = tarfile.TarInfo('release/sui')
                member.size = len(binary)
                tar.addfile(member, io.BytesIO(binary))
            self.write_command(root / 'bin/curl', 'while [ "$1" != "-o" ]; do shift; done\n'
                               f'cp {shlex.quote(str(archive))} "$2"\n')
            self.write_command(root / 'bin/craftctl', 'test "$1 $2" = "set version=1.82.3"\n')
            env = dict(os.environ, PATH=f'{root / "bin"}:{os.environ["PATH"]}',
                       CRAFT_PART_SRC=str(root / 'source'), CRAFT_PROJECT_DIR=str(project))
            failed = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', pull], env=env, capture_output=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn(b'checksum did NOT match', failed.stderr)
            executable = root / 'source/sui/bin/sui'
            self.assertFalse(executable.exists())
            fixture_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            fixture_pull = pull.replace(expected_digest, fixture_digest)
            subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', fixture_pull], env=env, check=True,
                           capture_output=True)
            self.assertEqual(executable.read_bytes(), binary)
            self.assertEqual(stat.S_IMODE(executable.stat().st_mode), 0o755)
            staged_license = root / 'source/sui/LICENSE'
            self.assertTrue(staged_license.is_file(), 'The SDK part must stage the upstream license')
            self.assertEqual(hashlib.sha256(staged_license.read_bytes()).hexdigest(),
                             'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4')
            self.assertEqual(stat.S_IMODE(staged_license.stat().st_mode), 0o644)

    def test_setup_repeat_and_upgrade_preserve_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bin').mkdir()
            (root / 'usr-local-bin').mkdir()
            exposed = root / 'usr-local-bin/sui'
            self.write_command(
                root / 'bin/ln',
                'test "$#" -eq 3 && test "$3" = "/usr/local/bin/sui"\n'
                f'exec /usr/bin/ln "$1" "$2" {shlex.quote(str(exposed))}\n',
            )
            state = root / 'home/.sui'
            state.mkdir(mode=0o700, parents=True)
            client = state / 'client.yaml'
            client.write_bytes(b'# synthetic configuration\nactive_env: fixture\n')
            client.chmod(0o600)
            baseline = (client.read_bytes(), client.stat(), state.stat())

            for version, mount in (('1.82.3', 'current'), ('1.82.3', 'current'), ('9.9.9', 'upgrade')):
                payload = root / mount / 'sui/bin/sui'
                payload.parent.mkdir(parents=True, exist_ok=True)
                self.write_command(payload, f'printf "%s\\n" "sui {version}-fixture"\n')
                env = dict(os.environ, SDK=str(root / mount), HOME=str(state.parent),
                           PATH=f'{root / "bin"}:{os.environ["PATH"]}')
                subprocess.run([SDK / 'hooks/setup-base'], env=env, check=True)
                self.assertEqual(exposed.resolve(), payload)
                self.assertEqual(stat.S_IMODE(exposed.stat().st_mode), 0o755)
                result = subprocess.check_output([exposed, '--version'], text=True)
                self.assertEqual(result.strip(), f'sui {version}-fixture')
                self.assertEqual(list(state.iterdir()), [client])
                self.assertEqual(client.read_bytes(), baseline[0])
                for actual, original in ((client.stat(), baseline[1]), (state.stat(), baseline[2])):
                    self.assertEqual(actual.st_mode, original.st_mode)
                    self.assertEqual(actual.st_ino, original.st_ino)
                    self.assertEqual(actual.st_mtime_ns, original.st_mtime_ns)

    @staticmethod
    def write_command(path, body):
        path.write_text('#!/bin/sh\nset -eu\n' + body)
        path.chmod(0o755)


if __name__ == '__main__':
    unittest.main()
