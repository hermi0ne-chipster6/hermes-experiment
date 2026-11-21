from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from release.detect import candidate, fetch_releases, select_stable
except ImportError:
    candidate = select_stable = None


def release(tag, **changes):
    return {'tag_name':tag, 'draft':False, 'prerelease':False, 'published_at':'2026-10-20T00:00:00Z', **changes}


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(candidate, 'release detector is not implemented')

    def test_chooses_newest_final_release_excluding_main_and_prereleases(self):
        items = [release('main'), release('v1.3.0-rc1'), release('v1.2.0',published_at='2026-10-23T00:00:00Z'), release('v1.4.0',prerelease=True), release('v1.3.0',draft=True), release('v1.1.9')]
        self.assertEqual(select_stable(items)['tag_name'], 'v1.2.0')

    def test_historical_calendar_tag_does_not_outrank_a_newer_release(self):
        items=[release('v2026.9.24',published_at='2026-09-24T00:00:00Z'),release('v0.22.5',published_at='2026-10-23T00:00:00Z')]
        self.assertEqual(select_stable(items)['tag_name'],'v0.22.5')

    def test_republished_legacy_calendar_tag_is_not_a_semver_release(self):
        items=[release('v2026.9.24',published_at='2026-10-31T00:00:00Z'),release('v0.22.5',published_at='2026-10-23T00:00:00Z')]
        self.assertEqual(select_stable(items)['tag_name'],'v0.22.5')

    def test_unchanged_release_produces_no_candidate(self):
        self.assertIsNone(candidate('v1.2.0', 'a'*40, release('v1.2.0'), 'a'*40))

    def test_moved_existing_tag_is_an_error(self):
        with self.assertRaises(ValueError):
            candidate('v1.2.0', 'a'*40, release('v1.2.0'), 'b'*40)

    def test_candidate_requires_review_and_never_changes_runtime(self):
        value = candidate('v1.2.0', 'a'*40, release('v1.2.1'), 'b'*40)
        self.assertEqual(value['promotion'], 'requires-review')
        self.assertEqual(value['source_revision'], 'b'*40)
        self.assertEqual(value['required_checks'], ['unit', 'sdk-a', 'sdk-b', 'sdk-c', 'bridge', 'routing', 'memory', 'heartbeat', 'native-gateways'])

    def test_malformed_version_or_revision_cannot_be_promoted(self):
        for tag, sha in [('v01.2.1','b'*40), ('main','b'*40), ('v1.2.1','main'), ('v1.2.1','b'*39)]:
            with self.subTest(tag=tag, sha=sha):
                with self.assertRaises(ValueError):
                    candidate('v1.2.0', 'a'*40, release(tag), sha)

    def test_release_api_detection_paginates(self):
        first = [release(f'v0.23.{i}') for i in range(100)]
        second = [release('v0.24.0')]
        payloads = {'/releases?per_page=100&page=1': first, '/releases?per_page=100&page=2': second}
        self.assertEqual(fetch_releases(payloads.__getitem__), first + second)
