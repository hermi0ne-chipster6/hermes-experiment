import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import yaml

from release import stable_pipeline as pipeline


def release(tag, release_id, **fields):
    return {'id': release_id, 'tag_name': tag, 'published_at': '2026-11-20T00:00:00Z',
            'draft': False, 'prerelease': False, **fields}


class StablePipelineTests(unittest.TestCase):
    def test_discovers_multiple_final_releases_in_order(self):
        releases = [release('v0.24.0', 4), release('v0.23.4', 3), release('v0.23.3', 2),
                    release('v2026.1.1', 5), release('v0.24.1', 6, draft=True),
                    release('v0.24.2', 7, prerelease=True), release('v0.24.2+canary', 8)]
        observed = {'v0.23.3': {'id': 2, 'revision': 'a' * 40}}
        revisions = {'v0.23.3': 'a' * 40, 'v0.23.4': 'b' * 40, 'v0.24.0': 'c' * 40}
        queue = pipeline.discover(releases, 'v0.23.3', observed, revisions.__getitem__)
        self.assertEqual([item['tag'] for item in queue], ['v0.23.4', 'v0.24.0'])
        self.assertEqual(queue[0]['revision'], 'b' * 40)

    def test_reports_moved_tags_and_reissued_or_missing_release_metadata(self):
        observed = {'v0.23.3': {'id': 2, 'revision': 'a' * 40}}
        for published, revision in [([release('v0.23.3', 2)], 'b' * 40),
                                    ([release('v0.23.3', 3)], 'a' * 40),
                                    ([], 'a' * 40), ([release('v0.23.3', None)], 'a' * 40)]:
            with self.subTest(published=published, revision=revision):
                with self.assertRaises(ValueError):
                    pipeline.discover(published, 'v0.23.3', observed, lambda _: revision)

    def test_recognizes_only_authenticated_prs_for_the_exact_repository_and_pin(self):
        candidate = {'tag': 'v0.23.4', 'id': 3, 'revision': 'a' * 40,
                     'published_at': '2026-11-20T00:00:00Z'}
        repo = 'owner/hermes-experiment'
        pr = {'number': 4, 'state': 'open', 'draft': False,
              'user': {'id': pipeline.BOT_ID, 'login': pipeline.BOT_LOGIN, 'type': 'Bot'},
              'head': {'ref': pipeline.branch(candidate), 'repo': {'full_name': repo}, 'sha': 'c' * 40},
              'base': {'ref': 'main', 'repo': {'full_name': repo}},
              'body': pipeline.pr_body(candidate)}
        self.assertTrue(pipeline.recognized(pr, candidate, repo))
        for edits in ({'number': 3}, {'draft': True}, {'state': 'closed'}, {'user': {'id': 42}},
                      {'body': 'wrong commit'}, {'head': {**pr['head'], 'repo': {'full_name': 'fork/project'}}}):
            self.assertFalse(pipeline.recognized({**pr, **edits}, candidate, repo))

    def test_protection_demands_strict_checks_and_disallows_bypass(self):
        rules = [{'type': 'pull_request', 'ruleset_id': 8},
                 {'type': 'non_fast_forward', 'ruleset_id': 8},
                 {'type': 'required_status_checks', 'ruleset_id': 8, 'parameters': {
                     'strict_required_status_checks_policy': True,
                     'required_status_checks': [{'context': pipeline.STATUS_CONTEXT,
                                                 'integration_id': pipeline.ACTIONS_APP_ID}]}}]
        settings = {8: {'enforcement': 'active', 'bypass_actors': []}}
        self.assertTrue(pipeline.protection_ready(rules, settings))
        self.assertTrue(pipeline.protection_ready(rules, {8: {'enforcement': 'active'}}))
        self.assertFalse(pipeline.protection_ready([rules[0], rules[-1]], settings))
        self.assertFalse(pipeline.protection_ready(rules, {8: {'enforcement': 'active', 'bypass_actors': [{}]}}))
        rules[-1]['parameters']['strict_required_status_checks_policy'] = False
        self.assertFalse(pipeline.protection_ready(rules, settings))

    def test_qualification_failure_or_changed_head_or_base_cannot_merge(self):
        pin = {'head': 'a' * 40, 'base': 'b' * 40}
        for result in ('failure', 'skipped', 'cancelled', ''):
            self.assertFalse(pipeline.qualified(result, pin, pin))
        self.assertFalse(pipeline.qualified('success', pin, {**pin, 'head': 'd' * 40}))
        self.assertFalse(pipeline.qualified('success', pin, {**pin, 'base': 'd' * 40}))
        self.assertTrue(pipeline.qualified('success', pin, pin))

    def test_operator_qualification_binds_the_reviewed_human_head_and_target(self):
        repo = 'owner/hermes-experiment'
        head, base = 'a' * 40, 'b' * 40
        candidate = {'pr': 3, 'head': head, 'base': base}
        pull = {'number': 3, 'state': 'open', 'draft': True, 'user': {'type': 'User'},
                'base': {'ref': 'main', 'repo': {'full_name': repo}},
                'head': {'ref': 'human/change', 'sha': head, 'repo': {'full_name': repo}}}
        for edits in ({}, {'number': 4}, {'state': 'closed'}, {'user': {'type': 'Bot'}},
                      {'auto_merge': {'enabled_by': {'id': 42}}},
                      {'base': {**pull['base'], 'ref': 'other'}},
                      {'head': {**pull['head'], 'ref': 'release/hermes/v0.24.0'}},
                      {'head': {**pull['head'], 'repo': {'full_name': 'fork/repo'}}},
                      {'head': {**pull['head'], 'sha': 'c' * 40}}):
            with (self.subTest(edits=edits),
                  patch.object(pipeline, 'main_tip', return_value=base),
                  patch.object(pipeline, 'gh', side_effect=[{'role_name': 'maintain'}, {**pull, **edits}]),
                  patch.object(pipeline, 'verify_human_scope') as scope):
                if edits:
                    with self.assertRaises(ValueError):
                        pipeline.inspect_human(repo, candidate, 'operator', base)
                    scope.assert_not_called()
                else:
                    self.assertEqual(pipeline.inspect_human(repo, candidate, 'operator', base), candidate)
                    scope.assert_called_once_with(base, head)

    def test_operator_qualification_rejects_unreviewed_inputs_and_untrusted_dispatch(self):
        candidate = {'pr': 3, 'head': 'a' * 40, 'base': 'b' * 40}
        with patch.object(pipeline, 'gh', return_value={'role_name': 'write'}) as api:
            with self.assertRaisesRegex(ValueError, 'maintainer'):
                pipeline.inspect_human('fixture', candidate, 'contributor', candidate['base'])
            api.assert_called_once_with('repos/fixture/collaborators/contributor/permission')
            api.reset_mock()
            for changed, workflow_sha in [({**candidate, 'head': 'unbound'}, candidate['base']),
                                          (candidate, 'c' * 40), ({**candidate, 'pr': 0}, candidate['base'])]:
                with self.assertRaises(ValueError):
                    pipeline.inspect_human('fixture', changed, 'operator', workflow_sha)
            api.assert_not_called()

    def test_human_status_rechecks_freshness_and_never_enables_auto_merge(self):
        candidate = {'pr': 3, 'head': 'a' * 40, 'base': 'b' * 40}
        for result, live, expected_status in [
                ('success', {'head': candidate['head'], 'base': candidate['base']}, 'success'),
                ('failure', {'head': candidate['head'], 'base': candidate['base']}, 'failure'),
                ('skipped', {'head': candidate['head'], 'base': candidate['base']}, 'failure'),
                ('cancelled', {'head': candidate['head'], 'base': candidate['base']}, 'failure'),
                ('success', {'head': 'c' * 40, 'base': candidate['base']}, None),
                ('success', {'head': candidate['head'], 'base': 'c' * 40}, None)]:
            with (self.subTest(result=result, live=live),
                  patch.object(pipeline, 'live_human', return_value=live),
                  patch.object(pipeline, 'status') as status,
                  patch.object(pipeline, 'verify_human_scope') as scope,
                  patch.object(pipeline, 'require_qualification_rule') as protection,
                  patch.object(pipeline, 'gh') as api):
                if expected_status == 'success':
                    pipeline.finalize_human('fixture', candidate, result, candidate['base'])
                    protection.assert_called_once_with('fixture')
                else:
                    with self.assertRaises(ValueError):
                        pipeline.finalize_human('fixture', candidate, result, candidate['base'])
                    protection.assert_not_called()
                if expected_status:
                    scope.assert_called_once_with(candidate['base'], candidate['head'])
                    self.assertEqual(status.call_args.args[:3], ('fixture', candidate, expected_status))
                else:
                    status.assert_not_called()
                api.assert_not_called()

    def test_out_of_scope_or_newly_stale_human_pr_cannot_publish_success(self):
        candidate = {'pr': 3, 'head': 'a' * 40, 'base': 'b' * 40}
        current = {'head': candidate['head'], 'base': candidate['base']}
        for scope_result, rule_result, live in [(ValueError('Outside A scope'), None, current),
                                               (None, ValueError('No strict rule'), current),
                                               (None, None, {**current, 'base': 'f' * 40})]:
            with (self.subTest(scope_result=scope_result, rule_result=rule_result),
                  patch.object(pipeline, 'live_human', side_effect=[current, live]),
                  patch.object(pipeline, 'verify_human_scope', side_effect=scope_result),
                  patch.object(pipeline, 'require_qualification_rule', side_effect=rule_result),
                  patch.object(pipeline, 'status') as status):
                with self.assertRaises(ValueError):
                    pipeline.finalize_human('fixture', candidate, 'success', candidate['base'])
                status.assert_not_called()

    def test_human_scope_checks_exact_git_changes_before_qualification(self):
        launcher = pipeline.SDK + 'assets/wrappers/hermes'
        docs = pipeline.SDK + 'README.md'
        peer = 'sdks/hermes-execution/VERSION'
        harness = 'ci/qualify-sdk'
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)

            def git(*args):
                return subprocess.run(['git', *args], cwd=root, timeout=15, check=True,
                                      capture_output=True, text=True).stdout.strip()

            def commit():
                git('add', '-A')
                git('-c', 'user.name=Qualification', '-c', 'user.email=ci@example.invalid',
                    'commit', '-m', 'Qualification scope fixture')
                return git('rev-parse', 'HEAD')

            git('init', '-b', 'main')
            for path in (launcher, docs, peer, harness):
                local = root / path
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_text('baseline\n')
            base = commit()
            original_run = pipeline.run
            for paths, symlink, allowed in (
                    ((launcher,), False, True), ((docs,), False, True), ((launcher,), True, False),
                    ((launcher, peer), False, False), ((harness,), False, False),
                    (('sources.json',), False, False),
                    (('.github/workflows/sdk-qualification.yml',), False, False),
                    (('tests/test_runtime_wrapper.py',), False, False),
                    (('validation/hermes-agent/probe-qualification.py',), False, False),
                    ((pipeline.SDK + 'sdkcraft.yaml',), False, False)):
                with self.subTest(paths=paths, symlink=symlink):
                    for path in paths:
                        local = root / path
                        local.parent.mkdir(parents=True, exist_ok=True)
                        if symlink:
                            local.unlink()
                            local.symlink_to(root / peer)
                        else:
                            local.write_text('changed\n')
                    head = commit()
                    git('checkout', '--detach', base)
                    with (patch.object(pipeline, 'fetch_commit') as fetch,
                          patch.object(pipeline, 'run', side_effect=lambda *args: original_run(*args, cwd=root))):
                        if allowed:
                            pipeline.verify_human_scope(base, head)
                        else:
                            with self.assertRaisesRegex(ValueError, 'outside A-only qualification scope'):
                                pipeline.verify_human_scope(base, head)
                        fetch.assert_called_once_with(head)

    def test_source_and_sdk_jobs_enforce_their_exact_commit_shape(self):
        workflows = pipeline.ROOT / '.github/workflows'
        job_names = {'checks.yml': ('checks', 'Verify candidate and base'),
                     'sdk-qualification.yml': ('sdk', 'Verify candidate against main')}
        with tempfile.TemporaryDirectory() as name:
            def git(*args):
                return subprocess.run(['git', *args], cwd=name, timeout=15, check=True,
                                      capture_output=True, text=True).stdout.strip()

            def commit(message):
                git('-c', 'user.name=Qualification', '-c', 'user.email=ci@example.invalid',
                    'commit', '--allow-empty', '-m', message)
                return git('rev-parse', 'HEAD')

            git('init', '-b', 'main')
            old_base = commit('old target')
            base = commit('current target')
            single = commit('bot update')
            multi = commit('human change')
            git('checkout', '--detach', old_base)
            stale = commit('old-base change')
            git('update-ref', 'refs/remotes/origin/main', base)
            for filename, (job_name, step_name) in job_names.items():
                doc = yaml.load((workflows / filename).read_text(), Loader=yaml.BaseLoader)
                step = next(s for s in doc['jobs'][job_name]['steps'] if s.get('name') == step_name)
                for checkout, expected_head, expected_base, human, expected in (
                        (single, single, base, 'false', 0),
                        (multi, multi, base, 'false', 1),
                        (multi, multi, base, 'true', 0),
                        (stale, stale, base, 'true', 1),
                        (stale, stale, old_base, 'true', 1),
                        (multi, single, base, 'true', 1)):
                    with self.subTest(workflow=filename, head=checkout, human=human,
                                      expected_head=expected_head, expected_base=expected_base):
                        git('checkout', '--detach', checkout)
                        env = {**os.environ, 'CANDIDATE_SHA': expected_head,
                               'BASE_SHA': expected_base, 'HUMAN_CANDIDATE': human}
                        result = subprocess.run(['bash', '-e', '-c', step['run']], env=env,
                                                cwd=name, timeout=15, capture_output=True, text=True)
                        self.assertEqual(result.returncode, expected, result.stderr)

    def test_prepare_only_qualifies_oldest_and_reuses_existing_prs(self):
        base = 'b' * 40
        current = 'v0.23.3'
        records = [release(current, 2), release('v0.23.4', 3), release('v0.24.0', 4)]
        observed = {current: {'revision': 'a' * 40}}
        revisions = {current: 'a' * 40, 'v0.23.4': 'c' * 40, 'v0.24.0': 'd' * 40}
        with (patch.multiple(pipeline, main_tip=lambda _repo: base, run=lambda *_args: base,
                            gh=lambda *_args, **_kwargs: records, resolve_tag=revisions.__getitem__,
                            assert_candidate=lambda *_args: None),
              patch.object(pipeline, 'history', return_value=(current, observed, observed, {})),
              patch.object(pipeline, 'load_observations', return_value=('', {})),
              patch.object(pipeline, 'record_observations'),
              patch.object(pipeline, 'generate', return_value='e' * 40) as generate,
              patch.object(pipeline, 'publish', side_effect=lambda _, item, *args: (item['tag'], args)) as publish):
            first = pipeline.prepare('fixture')
            self.assertEqual(first[0], 'v0.23.4')
            self.assertEqual([call.args[1]['tag'] for call in publish.call_args_list],
                             ['v0.23.4', 'v0.24.0'])
            self.assertEqual(set(generate.call_args_list[0].args[2]), {current, 'v0.23.4'})

            publish.reset_mock()
            open_prs = {'v0.23.4': {'number': 10}, 'v0.24.0': {'number': 11}}
            pipeline.history.return_value = current, observed, observed, open_prs
            pipeline.prepare('fixture')
            self.assertEqual(publish.call_count, 1)
            self.assertEqual(publish.call_args.args[-1], {'number': 10})

    def test_finalize_publishes_success_only_after_native_auto_merge_confirmed(self):
        candidate = {'pr': 4, 'tag': 'v0.23.4', 'revision': 'a' * 40,
                     'head': 'b' * 40, 'base': 'c' * 40}
        pin = {key: candidate[key] for key in ('head', 'base')}
        pr = {'node_id': 'api_node_id'}
        api = Mock()
        api.gh.return_value = {'data': {'enablePullRequestAutoMerge': {'pullRequest': {'number': 4}}}}
        live = [(pr, pin)] * 3
        with (patch.object(pipeline, 'live_candidate', side_effect=live),
              patch.object(pipeline, 'status', api.status),
              patch.object(pipeline, 'gh', api.gh),
              patch.object(pipeline, 'fetch_commit'),
              patch.object(pipeline, 'assert_candidate'),
              patch.object(pipeline, 'require_protection'),
              patch.object(pipeline, 'resolve_tag', return_value=candidate['revision'])):
            pipeline.finalize('fixture', candidate, 'success')
        self.assertEqual([call[0] for call in api.mock_calls], ['status', 'gh', 'status'])
        self.assertEqual(api.mock_calls[0].args[2], 'pending')
        self.assertEqual(api.mock_calls[-1].args[2], 'success')
        self.assertEqual(api.gh.call_args.kwargs['payload']['variables']['head'], candidate['head'])

    def test_finalize_blocks_failed_or_stale_qualification(self):
        candidate = {'pr': 4, 'head': 'b' * 40, 'base': 'c' * 40}
        pin = {key: candidate[key] for key in ('head', 'base')}
        for result, live, expected_status in [('failure', pin, 'failure'),
                                               ('success', {**pin, 'base': 'd' * 40}, None),
                                               ('success', {**pin, 'head': 'd' * 40}, None)]:
            with (self.subTest(result=result, live=live),
                  patch.object(pipeline, 'live_candidate', return_value=({}, live)),
                  patch.object(pipeline, 'status') as status,
                  patch.object(pipeline, 'gh') as api):
                with self.assertRaises(ValueError):
                    pipeline.finalize('fixture', candidate, result)
                api.assert_not_called()
                if expected_status:
                    self.assertEqual(status.call_args.args[2], expected_status)
                else:
                    status.assert_not_called()

    def test_candidate_rejects_unrelated_paths(self):
        required = ['sources.json', pipeline.HISTORY, pipeline.SDK + 'VERSION',
                    pipeline.SDK + 'sdkcraft.yaml']
        self.assertEqual(pipeline.changed_paths(required), set(required))
        for path in ('.github/workflows/releases.yml', 'sdks/hermes-execution/VERSION',
                     'sdks/hermes-rea/VERSION', 'sdks/sui-cli/VERSION', 'sdks/stripe-link-cli/VERSION',
                     'release/components.json', 'release/update_hermes_core.py',
                     pipeline.SDK + 'assets/wrappers/hermes'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                pipeline.changed_paths([*required, path])

    def test_paginated_github_cli_responses(self):
        self.assertEqual(pipeline.decode_pages('[{"id":1}]\n[]\n[{"id":2}]'), [{'id': 1}, {'id': 2}])
        with self.assertRaises(ValueError):
            pipeline.decode_pages('[{"id":1}]{"message":"invalid page"}')

    def test_retargets_one_existing_pr_on_a_new_base_with_expected_git_lease(self):
        item = {'tag': 'v0.23.4', 'id': 3, 'revision': 'a' * 40,
                'published_at': '2026-11-20T00:00:00Z'}
        old_base, base, old, head = (letter * 40 for letter in 'bcde')
        previous = {'number': 9, 'head': {'sha': old}}
        updated = {'number': 9, 'head': {'sha': head}}
        full_ref = 'refs/heads/' + pipeline.branch(item)
        with (patch.object(pipeline, 'recognized', return_value=True),
              patch.object(pipeline, 'branch_head', return_value=old),
              patch.object(pipeline, 'main_tip', return_value=base),
              patch.object(pipeline, 'fetch_commit'),
              patch.object(pipeline, 'assert_candidate') as assert_candidate,
              patch.object(pipeline, 'generate', return_value=old) as regenerate,
              patch.object(pipeline, 'run', side_effect=[old_base, '{}', '']) as git,
              patch.object(pipeline, 'gh', return_value=updated) as api):
            result = pipeline.publish('fixture', item, base, head, previous)

        self.assertEqual((result['pr'], result['head'], result['base']), (9, head, base))
        assert_candidate.assert_called_once_with(old_base, old, item)
        regenerate.assert_called_once_with(item, old_base, {})
        self.assertEqual(git.call_args.args[-4:], ('push', f'--force-with-lease={full_ref}:{old}',
                                                 'origin', f'{head}:{full_ref}'))
        api.assert_called_once_with('repos/fixture/pulls/9')

    def test_observation_is_recorded_before_a_failed_candidate_and_flags_future_tag_drift(self):
        base = 'a' * 40
        current, pending = 'v0.23.3', 'v0.23.4'
        observed = {current: {'revision': 'a' * 40}}
        records = [release(current, 2), release(pending, 3)]
        revisions = {current: 'a' * 40, pending: 'b' * 40}
        stored = {}
        calls = Mock()

        def record(_, old, new):
            self.assertEqual(old, stored)
            stored.update(new)
            calls.observation()

        calls.generate.side_effect = ValueError('simulated generator failure')
        with (patch.multiple(pipeline, main_tip=lambda _repo: base, run=lambda *_args: base,
                            gh=lambda *_args, **_kwargs: records, resolve_tag=revisions.__getitem__),
              patch.object(pipeline, 'history', return_value=(current, observed, observed, {})),
              patch.object(pipeline, 'load_observations', side_effect=lambda _repo: ('', stored.copy())),
              patch.object(pipeline, 'record_observations', side_effect=record),
              patch.object(pipeline, 'generate', calls.generate)):
            with self.assertRaisesRegex(ValueError, 'could not be prepared'):
                pipeline.prepare('fixture')
            self.assertEqual([call[0] for call in calls.mock_calls], ['observation', 'generate'])
            self.assertEqual(stored[pending]['revision'], revisions[pending])

            revisions[pending] = 'c' * 40
            with self.assertRaisesRegex(ValueError, 'Previously observed tag.*moved'):
                pipeline.prepare('fixture')
            self.assertEqual(calls.generate.call_count, 1)

    def test_observed_release_identity_cannot_be_replaced_by_pr_or_pin(self):
        original = {'v0.23.4': {'id': 3, 'revision': 'a' * 40,
                                'published_at': '2026-11-20T00:00:00Z'}}
        self.assertEqual(pipeline.combine_observations(original, {'v0.23.4': {'id': 3}}), original)
        with self.assertRaisesRegex(ValueError, 'Conflicting persisted'):
            pipeline.combine_observations(original, {'v0.23.4': {'id': 4}})

    def test_observation_ref_rejects_divergent_git_pushes(self):
        with tempfile.TemporaryDirectory() as scratch:
            repo = Path(scratch) / 'checkout'
            repo.mkdir()
            def git(*command, stdin=None):
                result = subprocess.run(command, cwd=repo, input=stdin, text=True,
                                        capture_output=True, check=True, timeout=15)
                return result.stdout.strip()

            git('git', 'init', '--bare', str(Path(scratch) / 'remote.git'))
            git('git', 'init')
            git('git', 'remote', 'add', 'origin', str(Path(scratch) / 'remote.git'))
            full_ref = 'refs/heads/' + pipeline.OBSERVATION_BRANCH

            def remote_head():
                row = git('git', 'ls-remote', 'origin', full_ref)
                return row.split()[0] if row else ''

            first = {'v0.23.3': {'id': 2, 'revision': 'a' * 40,
                                 'published_at': '2026-11-20T00:00:00Z'}}
            second = {**first, 'v0.23.4': {'id': 3, 'revision': 'b' * 40,
                                        'published_at': '2026-11-21T00:00:00Z'}}
            divergent = {**first, 'v0.24.0': {'id': 4, 'revision': 'c' * 40,
                                             'published_at': '2026-11-21T00:00:00Z'}}
            with (patch.object(pipeline, 'run', side_effect=git),
                  patch.object(pipeline, 'branch_head', side_effect=lambda *_args: remote_head())):
                pipeline.record_observations('', {}, first)
                head, observed = pipeline.load_observations('fixture')
                self.assertEqual(observed, first)
                pipeline.record_observations(head, observed, second)
                with self.assertRaises(subprocess.CalledProcessError):
                    pipeline.record_observations(head, observed, divergent)
                self.assertEqual(pipeline.load_observations('fixture')[1], second)
