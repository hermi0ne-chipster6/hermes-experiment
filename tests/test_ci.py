import unittest

from ci.check import validate_workflow


class CITests(unittest.TestCase):
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
