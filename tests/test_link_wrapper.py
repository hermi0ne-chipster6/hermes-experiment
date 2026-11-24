from pathlib import Path
import json
import subprocess
import tempfile
import unittest
import shutil

WRAPPER = Path(__file__).resolve().parents[1] / 'sdks/stripe-link-cli/wrappers/link-cli'


class LinkWrapperTests(unittest.TestCase):
    def test_native_cli_receives_persistent_auth_path_without_runtime_installation(self):
        self.assertTrue(WRAPPER.exists(), 'native Link wrapper is missing')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'wrappers').mkdir()
            (root/'node/bin').mkdir(parents=True)
            wrapper = root/'wrappers/link-cli'
            shutil.copyfile(WRAPPER, wrapper)
            wrapper.chmod(0o755)
            node = root/'node/bin/node'
            node.write_text('#!/usr/bin/python3\nimport os,sys,json\nprint(json.dumps({"auth":os.environ.get("LINK_AUTH_FILE"),"args":sys.argv[1:]}))\n')
            node.chmod(0o755)
            result = subprocess.run([str(wrapper),'--help'],env={'PATH':'/usr/bin:/bin'},capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            output=json.loads(result.stdout)
            self.assertEqual(output['auth'],'/home/workshop/.link-cli/auth.json')
            self.assertTrue(output['args'][0].endswith('/finance/node_modules/@stripe/link-cli/dist/cli.js'))
            self.assertEqual(output['args'][1:],['--help'])
