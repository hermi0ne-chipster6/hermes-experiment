"""Offline source and wrapper checks for the standalone Stripe Link SDK."""

import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import tempfile
import unittest

import yaml


SDK = Path(__file__).resolve().parents[1]
ROOT = SDK.parents[1]


class StripeLinkSdkTests(unittest.TestCase):
    def test_recipe_and_lock_match_recorded_inputs(self):
        recipe = yaml.safe_load((SDK / 'sdkcraft.yaml').read_text())
        package = json.loads((SDK / 'npm/package.json').read_text())
        lock = json.loads((SDK / 'npm/package-lock.json').read_text())
        sources = json.loads((ROOT / 'sources.json').read_text())
        link = sources['link']
        node = recipe['parts']['node-runtime']
        version = (SDK / 'VERSION').read_text().strip()
        self.assertEqual(recipe['name'], 'stripe-link-cli')
        self.assertEqual(recipe['base'], 'ubuntu@26.04')
        self.assertEqual(recipe['platforms'], {'amd64': None})
        self.assertEqual(recipe['plugs'], {
            'link-state': {'interface': 'mount', 'workshop-target': '/home/workshop/.link-cli', 'mode': 0o700},
        })
        self.assertEqual(version, link['version'])
        self.assertEqual(package['dependencies'], {'@stripe/link-cli': version})
        self.assertEqual(lock['packages']['']['dependencies'], package['dependencies'])
        locked = lock['packages']['node_modules/@stripe/link-cli']
        self.assertEqual(locked['version'], version)
        self.assertEqual(locked['integrity'], link['dist']['integrity'])
        self.assertEqual(locked['resolved'], link['dist']['tarball'])
        self.assertIn(sources['node']['version'], node['source'])
        self.assertEqual(node['source-checksum'],
                         'sha256/d28a96af6c38596f6d9d97c0ee531c13d238d757742387d1928de822d959e997')
        part = recipe['parts'][recipe['adopt-info']]
        self.assertEqual(part['source'], 'npm')
        self.assertEqual(part['after'], ['node-runtime'])
        self.assertIn('npm ci --omit=dev --ignore-scripts --no-audit --no-fund', part['override-build'])

    def test_wrapper_uses_own_node_and_preserves_native_auth_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / 'package path'
            (payload / 'node/bin').mkdir(parents=True)
            (payload / 'wrappers').mkdir()
            node = payload / 'node/bin/node'
            script = payload / 'finance/node_modules/@stripe/link-cli/dist/cli.js'
            script.parent.mkdir(parents=True)
            script.write_text('// synthetic native command payload\n')
            self.write_command(node, 'test -f "$1"\n'
                               'printf "%s\\n" "$1" "$LINK_AUTH_FILE"\n'
                               'shift\n'
                               'case "$1" in\n'
                               '  --help) printf "%s\\n" "Usage: link-cli" ;;\n'
                               '  --version) printf "%s\\n" "1.0.1-fixture" ;;\n'
                               '  --mcp) printf "%s\\n" "$@"; exit 42 ;;\n'
                               '  *) exit 99 ;;\n'
                               'esac\n')
            wrapper = payload / 'wrappers/link-cli'
            wrapper.write_bytes((SDK / 'wrappers/link-cli').read_bytes())
            wrapper.chmod(0o755)
            (root / 'bin').mkdir()
            (root / 'local-bin').mkdir()
            exposed = root / 'local-bin/link-cli'
            self.write_command(
                root / 'bin/ln',
                'test "$#" -eq 3 && test "$3" = "/usr/local/bin/link-cli"\n'
                f'exec /usr/bin/ln "$1" "$2" {shlex.quote(str(exposed))}\n',
            )

            state = root / 'home/.link-cli'
            state.mkdir(mode=0o700, parents=True)
            auth = state / 'synthetic auth.json'
            identity = state / 'identity'
            auth.write_bytes(b'{"fixture": true}\n')
            identity.write_bytes(b'fixture identity\n')
            auth.chmod(0o600)
            identity.chmod(0o600)
            baseline = {
                path: (path.stat(), path.read_bytes()) for path in (auth, identity)
            }
            env = dict(os.environ, SDK=str(payload), HOME=str(state.parent),
                       PATH=f'{root / "bin"}:{os.environ["PATH"]}')
            env.pop('LINK_AUTH_FILE', None)

            for _ in range(2):
                subprocess.run([SDK / 'hooks/setup-base'], check=True, env=env)
                self.assertEqual(exposed.resolve(), wrapper)
                self.assertEqual(stat.S_IMODE(exposed.stat().st_mode), 0o755)
                help_text = subprocess.check_output([exposed, '--help'], env=env, text=True)
                self.assertEqual(help_text.splitlines(), [
                    str(script), '/home/workshop/.link-cli/auth.json', 'Usage: link-cli',
                ])
                version_text = subprocess.check_output(
                    [exposed, '--version'], env=dict(env, LINK_AUTH_FILE=str(auth)), text=True,
                )
                self.assertEqual(version_text.splitlines(), [str(script), str(auth), '1.0.1-fixture'])

            missing_auth = state / 'does-not-exist.json'
            result = subprocess.run(
                [exposed, '--mcp', 'synthetic argument'], env=dict(env, LINK_AUTH_FILE=str(missing_auth)),
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 42)
            self.assertEqual(result.stdout.splitlines(), [
                str(script), str(missing_auth), '--mcp', 'synthetic argument',
            ])
            self.assertEqual(set(state.iterdir()), {auth, identity})
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
            for path, (original, data) in baseline.items():
                actual = path.stat()
                self.assertEqual(path.read_bytes(), data)
                self.assertEqual(actual.st_mode, original.st_mode)
                self.assertEqual(actual.st_ino, original.st_ino)
                self.assertEqual(actual.st_mtime_ns, original.st_mtime_ns)

    @staticmethod
    def write_command(path, body):
        path.write_text('#!/bin/sh\nset -eu\n' + body)
        path.chmod(0o755)


if __name__ == '__main__':
    unittest.main()
