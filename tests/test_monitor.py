import json
from pathlib import Path
import tempfile
import unittest

try:
    from release.monitor import inspect_component, monitor, write_reports
except ImportError:
    inspect_component = monitor = write_reports = None


class FixtureClient:
    def __init__(self, replies):
        self.replies = replies
        self.calls = []

    def get(self, url, *, raw=False):
        self.calls.append(url)
        for suffix, value in self.replies.items():
            if url.endswith(suffix):
                if isinstance(value, Exception):
                    raise value
                return value
        raise AssertionError('unexpected upstream request: '+url)


def component(**kwargs):
    return dict(name='test', kind='github-release', current='v1.0.0',
                repository='owner/project', pattern=r'v(\d+\.\d+\.\d+)',
                roles=['hermes-experiment'], inputs=['sdkcraft.yaml'], **kwargs)


def release(tag, **kwargs):
    return dict(tag_name=tag, draft=False, prerelease=False,
                published_at='2026-10-20T00:00:00Z', **kwargs)


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(monitor, 'complete upstream monitor is missing')

    def test_only_stable_releases_become_review_proposals(self):
        client = FixtureClient({'/releases?per_page=100': [release('main'),
            release('v2.0.0-rc1'), release('v1.0.1'),
            dict(release('v9.0.0'), draft=True)],
            '/git/ref/tags/v1.0.1': {'object': {'type': 'commit', 'sha': 'b'*40}}})
        result = inspect_component(component(), client)
        self.assertEqual(result['candidate']['tag'], 'v1.0.1')
        self.assertEqual(result['candidate']['revision'], 'b'*40)
        self.assertEqual(result['status'], 'review-required')
        self.assertIn('heartbeat', result['required_checks'])

    def test_retargeted_pinned_tag_is_drift_even_without_new_version(self):
        client = FixtureClient({'/releases?per_page=100': [release('v1.0.0')],
            '/git/ref/tags/v1.0.0': {'object': {'type': 'commit', 'sha': 'b'*40}}})
        result = inspect_component(component(revision='a'*40), client)
        self.assertEqual(result['status'], 'upstream-drift')

    def test_release_lists_without_stable_versions_are_errors(self):
        client = FixtureClient({'/releases?per_page=100': [release('main')]})
        with self.assertRaisesRegex(ValueError, 'stable'):
            inspect_component(component(), client)

    def test_partial_network_failure_makes_the_whole_report_incomplete(self):
        client = FixtureClient({'/releases?per_page=100': TimeoutError('upstream unavailable')})
        result = monitor([component()], client)
        self.assertFalse(result['complete'])
        self.assertEqual(result['errors'][0]['component'], 'test')
        self.assertEqual(result['checked_count'], 1)

    def test_npm_integrity_is_preserved_and_every_pinned_copy_is_compared(self):
        item = dict(name='npm:example', kind='npm', package='example', current='1.0.0, 2.0.0',
                    versions=['1.0.0', '2.0.0'], roles=['hermes-rea'], inputs=['package-lock.json'])
        client = FixtureClient({'/example/latest': {'version': '2.0.0',
            'dist': {'integrity': 'sha512-example', 'tarball': 'https://registry.npmjs.org/example.tgz'}}})
        result = inspect_component(item, client)
        self.assertEqual(result['status'], 'review-required')
        self.assertEqual(result['candidate']['integrity'], 'sha512-example')

    def test_prerelease_npm_latest_is_not_accepted(self):
        item = dict(name='npm:example', kind='npm', package='example', current='1.0.0',
                    roles=['ci'], inputs=['package-lock.json'])
        client = FixtureClient({'/example/latest': {'version': '2.0.0-rc.1'},
                                '/example': {'versions': {'2.0.0-rc.1': {'version':'2.0.0-rc.1'}}}})
        with self.assertRaisesRegex(ValueError, 'stable'):
            inspect_component(item, client)

    def test_npm_beta_dist_tag_falls_back_to_published_final_releases(self):
        item = dict(name='npm:example', kind='npm', package='example', current='1.0.0',
                    roles=['ci'], inputs=['package-lock.json'])
        client = FixtureClient({'/example/latest': {'version':'2.0.0-beta.1'},
            '/example': {'versions': {'1.1.0': {'version':'1.1.0',
                'dist':{'integrity':'sha512-example'}}}}})
        self.assertEqual(inspect_component(item, client)['candidate']['version'], '1.1.0')

    def test_existing_beta_only_dependencies_are_observed_without_approving_a_beta_update(self):
        item = dict(name='pypi:example', kind='pypi', package='example', current='0.1b1',
                    versions=['0.1b1'], roles=['hermes-experiment'], inputs=['requirements.txt'])
        client = FixtureClient({'/releases.xml':b'<rss><channel><item><title>0.2b1</title></item></channel></rss>',
            '/0.2b1/json': {'urls':[{'yanked':False,'digests':{'sha256':'a'*64}}], 'info':{}}})
        result = inspect_component(item, client)
        self.assertEqual(result['status'], 'prerelease-channel-review')
        self.assertFalse(result['candidate']['eligible'])

    def test_moved_current_tag_is_detected_even_when_a_new_release_exists(self):
        client = FixtureClient({'/releases?per_page=100':[release('v1.1.0')],
            '/git/ref/tags/v1.1.0': {'object':{'type':'commit','sha':'b'*40}},
            '/git/ref/tags/v1.0.0': {'object':{'type':'commit','sha':'c'*40}}})
        self.assertEqual(inspect_component(component(revision='a'*40), client)['status'], 'upstream-drift')

    def test_snap_selection_respects_architecture_track_and_risk(self):
        item = dict(name='snap:lxd', kind='snap', package='lxd', current='6.0',
                    revision=1, track='6', risk='stable', roles=['build-host'], inputs=['components.json'])
        def entry(track, risk, arch, rev):
            return dict(channel=dict(track=track, risk=risk, architecture=arch), revision=rev, version='6.1')
        client = FixtureClient({'/snaps/info/lxd': {'channel-map': [entry('latest','edge','amd64',50),
            entry('6','stable','arm64',60), entry('6','stable','amd64',2)]}})
        self.assertEqual(inspect_component(item, client)['candidate']['revision'], 2)

    def test_annotation_tag_resolves_to_an_immutable_commit(self):
        client = FixtureClient({'/releases?per_page=100': [release('v1.1.0')],
            '/git/ref/tags/v1.1.0': {'object': {'type':'tag','sha':'c'*40}},
            '/git/tags/'+('c'*40): {'object': {'type':'commit','sha':'b'*40}}})
        self.assertEqual(inspect_component(component(), client)['candidate']['revision'], 'b'*40)

    def test_unknown_source_kind_is_an_error(self):
        item = component()
        item['kind'] = 'unsupported'
        self.assertFalse(monitor([item], FixtureClient({}))['complete'])

    def test_reports_preserve_errors_and_do_not_edit_source_files(self):
        report = {'complete':False,'checked_count':1,'results':[],
                  'errors':[{'component':'test','error':'timeout'}]}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            write_reports(report, path)
            self.assertFalse(json.loads((path/'release-monitor.json').read_text())['complete'])
            self.assertIn('timeout', (path/'release-monitor.md').read_text())
