import hashlib
from pathlib import Path
import tempfile
import unittest

from ci.spread_receipt import verify_receipt


JOBS = (
    'lxd:ubuntu-24.04:main/launch:resolute',
    'lxd:ubuntu-24.04:main/missing-secret:resolute',
    'lxd:ubuntu-24.04:main/persistence:resolute',
)
STAMP = '2026-11-24 04:00:00 '


def spread_log(jobs=JOBS, successful=3, aborted=0):
    return [
        *(f'{STAMP}Executing {job} (lxd:ubuntu-24.04) ({index}/3)...'
          for index, job in enumerate(jobs, start=1)),
        f'{STAMP}Successful tasks: {successful}',
        f'{STAMP}Aborted tasks: {aborted}',
    ]


class SpreadReceiptTests(unittest.TestCase):
    def test_exact_jobs_and_distinct_build_digest(self):
        with tempfile.TemporaryDirectory() as scratch:
            archive = Path(scratch) / 'hermes-experiment_amd64_ubuntu@26.04.sdk'
            payload = b'archive rebuilt by sdkcraft test'
            archive.write_bytes(payload)
            receipt = verify_receipt(spread_log(JOBS[::-1]), JOBS, archive)
            self.assertEqual(receipt['jobs'], sorted(JOBS))
            self.assertEqual(receipt['archive']['name'], archive.name)
            self.assertEqual(receipt['archive']['sha256'], hashlib.sha256(payload).hexdigest())
            self.assertEqual(receipt['archive']['bytes'], len(payload))

    def test_zero_missing_duplicate_or_aborted_jobs_fail(self):
        with tempfile.TemporaryDirectory() as scratch:
            archive = Path(scratch) / 'spread.sdk'
            archive.write_bytes(b'pack was built')
            for lines in (
                ['No tests to run.'], spread_log((), successful=0),
                spread_log(JOBS[:2]), spread_log(JOBS[:2] + JOBS[:1]),
                spread_log(JOBS[:2] + ('lxd:ubuntu-24.04:main/other:resolute',)),
                spread_log(successful=2), spread_log(aborted=1),
                spread_log() + [f'{STAMP}Failed suite restore: 1'],
                spread_log() + [f'{STAMP}Successful tasks: 3'],
                spread_log()[:-1],
            ):
                with self.subTest(lines=lines), self.assertRaises(ValueError):
                    verify_receipt(lines, JOBS, archive)

    def test_missing_empty_and_symlink_builds_fail(self):
        with tempfile.TemporaryDirectory() as scratch:
            archive = Path(scratch) / 'spread.sdk'
            with self.assertRaises(ValueError):
                verify_receipt(spread_log(), JOBS, archive)
            archive.touch()
            with self.assertRaises(ValueError):
                verify_receipt(spread_log(), JOBS, archive)
            archive.unlink()
            target = Path(scratch) / 'substitute.sdk'
            target.write_bytes(b'a different build')
            archive.symlink_to(target)
            with self.assertRaises(ValueError):
                verify_receipt(spread_log(), JOBS, archive)
