"""Verify executed Spread jobs and identify their separately rebuilt SDK."""

import argparse
from collections import Counter
from hashlib import file_digest
import json
from pathlib import Path
import re


TIMESTAMP = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (.*)$')
EXECUTING = re.compile(r'Executing (\S+) \(.+\) \((\d+)/(\d+)\)\.\.\.')


def verify_receipt(lines, jobs, archive):
    """Read the pinned SDKcraft/Spread console format after a zero command exit."""
    messages = [match[1] for line in lines if (match := TIMESTAMP.fullmatch(line))]
    starts = [match.groups() for message in messages if (match := EXECUTING.fullmatch(message))]
    names = [name for name, _, _ in starts]
    if not jobs or len(set(jobs)) != len(jobs) or Counter(names) != Counter(jobs):
        raise ValueError(f'Expected exactly {sorted(jobs)}, observed executions {sorted(names)}')
    if sorted(int(index) for _, index, _ in starts) != list(range(1, len(jobs) + 1)):
        raise ValueError('Spread execution ordinals do not match the required job count')
    if any(int(total) != len(jobs) for _, _, total in starts):
        raise ValueError('Spread scheduled a different number of jobs')
    summary = [message for message in messages if message.startswith(('Successful tasks:', 'Aborted tasks:'))]
    if summary != [f'Successful tasks: {len(jobs)}', 'Aborted tasks: 0']:
        raise ValueError(f'Expected one complete, successful Spread summary, observed {summary}')
    if any(message.startswith(('Failed task', 'Failed suite', 'Failed backend', 'Failed project'))
           for message in messages):
        raise ValueError('Spread reported a lifecycle failure')

    if archive.is_symlink() or not archive.is_file() or not (size := archive.stat().st_size):
        raise ValueError(f'Missing fresh regular Spread build: {archive}')
    with archive.open('rb') as source:
        digest = file_digest(source, 'sha256').hexdigest()
    return {'jobs': sorted(names), 'archive': {'name': archive.name, 'bytes': size, 'sha256': digest}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('archive', type=Path)
    parser.add_argument('jobs', nargs='+')
    options = parser.parse_args()
    try:
        receipt = verify_receipt(options.log.read_text().splitlines(), options.jobs, options.archive)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Spread receipt rejected: {error}\n')
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
