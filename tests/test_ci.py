import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

from ci.check import validate_workflow


class CITests(unittest.TestCase):
    def test_sdk_qualification_uploads_only_this_run_attempts_evidence(self):
        root = Path(__file__).resolve().parents[1]
        workflow = yaml.safe_load((root / '.github/workflows/sdk-qualification.yml').read_text())
        steps = workflow['jobs']['sdk']['steps']
        build = next(step for step in steps if step.get('name') == 'Build and exercise Workshop A')
        upload = next(step for step in steps if step.get('name') == 'Retain qualification evidence')
        directory = build['env']['EVIDENCE_DIR']
        self.assertEqual(upload['with']['path'].rstrip('/'), directory)
        self.assertIn('${{ github.run_id }}', directory)
        self.assertIn('${{ github.run_attempt }}', directory)

    def test_workshop_cleanup_is_armed_when_launch_fails(self):
        root = Path(__file__).resolve().parents[1]
        driver = root / 'validation/hermes-agent/qualify-workshop'
        with tempfile.TemporaryDirectory() as scratch:
            directory = Path(scratch)
            tools = directory / 'bin'
            tools.mkdir()
            artifacts = directory / 'artifacts'
            artifacts.mkdir()
            archive = artifacts / 'candidate.sdk'
            archive.touch()
            log = directory / 'workshop.log'
            (tools / 'sdkcraft').write_text('#!/bin/bash\nexit "$FAKE_TRY_EXIT"\n')
            (tools / 'python3').write_text(
                '#!/bin/bash\ncase "$1" in\n'
                '  */ci/sdk_payload.py|*/ci/workshop_archive.py) exit 0 ;;\n'
                '  *) exec "$TEST_PYTHON" "$@" ;;\nesac\n'
            )
            (tools / 'workshop').write_text(
                '#!/bin/bash\n'
                'printf "%s\\t%s\\n" "$3" "$2" >> "$FAKE_WORKSHOP_LOG"\n'
                'case "$3" in\n'
                '  launch) exit 21 ;;\n'
                '  remove) exit "$FAKE_REMOVE_EXIT" ;;\n'
                'esac\n'
            )
            for tool in tools.iterdir():
                tool.chmod(0o755)
            for try_exit, remove_exit, expected in ((22, 0, 22), (0, 0, 21), (0, 8, 1)):
                with self.subTest(try_exit=try_exit, remove_exit=remove_exit):
                    log.unlink(missing_ok=True)
                    result = subprocess.run(
                        ['bash', str(driver), str(archive)], capture_output=True, text=True, timeout=15,
                        env={**os.environ, 'PATH': f"{tools}:{os.environ['PATH']}",
                             'HERMES_QUALIFICATION_LKG': str(directory / 'no-lkg'),
                             'FAKE_TRY_EXIT': str(try_exit), 'FAKE_REMOVE_EXIT': str(remove_exit),
                             'FAKE_WORKSHOP_LOG': str(log), 'TEST_PYTHON': sys.executable},
                    )
                    self.assertEqual(result.returncode, expected, result.stderr)
                    if try_exit:
                        self.assertFalse(log.exists())
                        self.assertFalse(list(directory.glob('hermes-workshop.*')))
                        continue
                    records = [line.split('\t') for line in log.read_text().splitlines()]
                    self.assertEqual([action for action, _ in records], ['launch', 'info', 'tasks', 'remove'])
                    projects = {Path(project) for _, project in records}
                    self.assertEqual(len(projects), 1)
                    project = projects.pop()
                    self.assertEqual(project.name, 'project')
                    self.assertEqual(project.parent.parent.resolve(), directory.resolve())
                    self.assertEqual(project.exists(), bool(remove_exit))
                    if remove_exit:
                        self.assertIn(str(project), result.stderr)

    def workflow(self):
        return {'name': 'check', 'on': {'push': {}}, 'permissions': {'contents': 'read'},
                'jobs': {'check': {'runs-on': 'ubuntu-24.04', 'steps': [
                    {'uses': 'actions/checkout@' + 'a' * 40}]}}}

    def test_actions_require_immutable_pins(self):
        doc = self.workflow()
        validate_workflow(doc)
        doc['jobs']['check']['steps'][0]['uses'] = 'actions/checkout@main'
        with self.assertRaisesRegex(ValueError, 'immutable'):
            validate_workflow(doc)

    def test_write_permissions_and_privileged_triggers_are_rejected(self):
        doc = self.workflow()
        doc['jobs']['check']['permissions'] = {'contents': 'write'}
        with self.assertRaisesRegex(ValueError, 'permissions'):
            validate_workflow(doc)
        doc = self.workflow()
        doc['on'] = {'pull_request_target': {}}
        with self.assertRaisesRegex(ValueError, 'trigger'):
            validate_workflow(doc)

    def test_pull_request_cannot_target_privileged_runner(self):
        doc = self.workflow()
        doc['on'] = {'pull_request': {}}
        doc['jobs']['check']['runs-on'] = ['self-hosted', 'linux', 'x64', 'hermes-sdk-build']
        with self.assertRaisesRegex(ValueError, 'trusted release workflow'):
            validate_workflow(doc)

    def test_reusable_qualification_requires_the_trusted_main_caller(self):
        doc = self.workflow()
        doc['on'] = {'workflow_call': {}}
        doc['jobs'] = {'sdk': {'runs-on': ['self-hosted', 'linux', 'x64', 'hermes-sdk-build']}}
        with self.assertRaisesRegex(ValueError, 'trusted release workflow'):
            validate_workflow(doc, 'sdk-qualification.yml')
        doc['jobs']['sdk']['if'] = (
            "github.repository == 'hermi0ne-chipster6/hermes-experiment' && "
            "((github.workflow_ref == format('{0}/.github/workflows/releases.yml@refs/heads/main', "
            "github.repository) && !inputs.human_candidate) || "
            "(github.workflow_ref == format('{0}/.github/workflows/qualify-human-pr.yml@refs/heads/main', "
            "github.repository) && inputs.human_candidate))"
        )
        validate_workflow(doc, 'sdk-qualification.yml')
        doc['jobs']['sdk']['if'] = doc['jobs']['sdk']['if'].replace('!inputs.human_candidate', 'true')
        with self.assertRaisesRegex(ValueError, 'trusted release workflow'):
            validate_workflow(doc, 'sdk-qualification.yml')

    def test_only_trusted_release_jobs_receive_specific_write_permissions(self):
        doc = self.workflow()
        doc['on'] = {'schedule': [], 'workflow_dispatch': {}, 'push': {'branches': ['main']}}
        doc['jobs'] = {
            'prepare': {'runs-on': 'ubuntu-24.04',
                        'permissions': {'contents': 'write', 'pull-requests': 'write'},
                        'if': ("github.repository == 'hermi0ne-chipster6/hermes-experiment' "
                               "&& github.ref == 'refs/heads/main'")},
        }
        validate_workflow(doc, 'releases.yml')
        with self.assertRaisesRegex(ValueError, 'permissions'):
            validate_workflow(doc, 'other.yml')
        doc['jobs']['prepare']['permissions']['actions'] = 'write'
        with self.assertRaisesRegex(ValueError, 'permissions'):
            validate_workflow(doc, 'releases.yml')

    def test_only_the_main_manual_qualifier_can_publish_human_status(self):
        doc = self.workflow()
        doc['on'] = {'workflow_dispatch': {}}
        doc['jobs'] = {
            'publish': {
                'runs-on': 'ubuntu-24.04',
                'permissions': {'contents': 'read', 'pull-requests': 'read', 'statuses': 'write'},
                'if': ("always() && needs.inspect.result == 'success' && "
                       "github.repository == 'hermi0ne-chipster6/hermes-experiment' "
                       "&& github.ref == 'refs/heads/main'"),
            },
        }
        validate_workflow(doc, 'qualify-human-pr.yml')
        with self.assertRaisesRegex(ValueError, 'permissions'):
            validate_workflow(doc, 'untrusted.yml')
        doc['on']['pull_request'] = {}
        with self.assertRaisesRegex(ValueError, 'permissions'):
            validate_workflow(doc, 'qualify-human-pr.yml')
