import unittest
from unittest.mock import Mock, patch

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
