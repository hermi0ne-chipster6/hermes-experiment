import copy
from pathlib import Path
import unittest

try:
    from ci.check import validate_workflow, require_build_dispatch
except ImportError:
    validate_workflow = require_build_dispatch = None


class CITests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(validate_workflow, 'CI workflow validation is missing')

    def workflow(self):
        return {'name':'check', 'on':{'push':None}, 'permissions':{'contents':'read'},
                'jobs':{'check':{'runs-on':'ubuntu-24.04', 'steps':[
                    {'uses':'actions/checkout@'+'a'*40}]}}}

    def test_immutable_actions_and_read_only_permissions_are_required(self):
        good = self.workflow()
        validate_workflow(good)
        for broken in [dict(good, permissions={'contents':'write'}),
                       dict(good, on={'pull_request_target':None})]:
            with self.assertRaises(ValueError):
                validate_workflow(broken)
        broken = copy.deepcopy(good)
        broken['jobs']['check']['steps'][0]['uses'] = 'actions/checkout@main'
        with self.assertRaisesRegex(ValueError, 'immutable'):
            validate_workflow(broken)

    def test_privileged_runner_cannot_run_on_push_or_pull_request(self):
        doc = self.workflow()
        doc['jobs']['check']['runs-on'] = ['self-hosted','linux','x64','hermes-sdk-build']
        with self.assertRaisesRegex(ValueError, 'manual'):
            validate_workflow(doc)

    def test_build_dispatch_fails_without_explicit_online_runner_acknowledgment(self):
        with self.assertRaisesRegex(ValueError, 'KVM'):
            require_build_dispatch('main', False)
        with self.assertRaisesRegex(ValueError, 'main'):
            require_build_dispatch('untrusted-branch', True)
        require_build_dispatch('main', True)
