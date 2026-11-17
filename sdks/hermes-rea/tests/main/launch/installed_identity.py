#!/usr/bin/env python3
"""Compare installed immutable SDK files with a caller-supplied build manifest."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--expected', required=True, type=Path)
parser.add_argument('--sdk', default='/var/lib/workshop/sdk/hermes-rea', type=Path)
args = parser.parse_args()
expected = json.loads(args.expected.read_text())
root = args.sdk.resolve(strict=True)
results = []
for name, digest in expected['files'].items():
    relative = Path(name)
    assert not relative.is_absolute() and '..' not in relative.parts, name
    path = (root / relative).resolve(strict=True)
    assert path.is_relative_to(root), name
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    results.append({'file': name, 'sha256': actual, 'matches': actual == digest})
assert all(row['matches'] for row in results), results
assert (root / 'rea/UPSTREAM_COMMIT').read_text().strip() == expected['upstream_commit']
print(json.dumps({'status': 'pass', 'upstream_commit': expected['upstream_commit'], 'files': results}, indent=2))
