"""Read-only upstream detector: proposes pins; never installs or promotes them."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

API = 'https://api.github.com/repos/NousResearch/hermes-agent'
# Match upstream's release-identity rule: calendar-year majors are legacy tags.
VERSION = re.compile(r'v(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z')
REVISION = re.compile(r'[0-9a-f]{40}\Z')


def version(tag):
    match = VERSION.fullmatch(tag) if isinstance(tag, str) else None
    if not match:
        raise ValueError('a stable vMAJOR.MINOR.PATCH tag is required')
    return tuple(map(int, match.groups()))


def select_stable(releases):
    stable = [r for r in releases if isinstance(r, dict) and not r.get('draft')
              and not r.get('prerelease') and VERSION.fullmatch(r.get('tag_name', ''))]
    if not stable:
        raise ValueError('no stable upstream release found')
    # Hermes has historical calendar tags as well as v0.x tags. Publication
    # chronology is authoritative; numeric sorting would select old releases.
    return max(stable, key=lambda r: datetime.fromisoformat(r['published_at'].replace('Z','+00:00')))


def candidate(current_tag, current_revision, release, revision):
    old, new = version(current_tag), version(release.get('tag_name'))
    if release.get('draft') or release.get('prerelease'):
        raise ValueError('drafts and prereleases cannot be candidates')
    if not REVISION.fullmatch(revision) or not REVISION.fullmatch(current_revision):
        raise ValueError('an immutable source commit is required')
    if old == new and current_revision != revision:
        raise ValueError('previously pinned tag moved; operator review required')
    if new <= old:
        return None
    return {'tag':release['tag_name'], 'source_revision':revision, 'previous_tag':current_tag,
            'promotion':'requires-review', 'required_checks':[
                'unit', 'sdk-a', 'sdk-b', 'sdk-c', 'bridge', 'routing', 'memory', 'heartbeat', 'native-gateways']}


def fetch(path):
    request = Request(API+path, headers={'Accept':'application/vnd.github+json', 'User-Agent':'hermes-sdk-release-detector'})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def resolve_tag(tag):
    version(tag)  # also prevents path/query injection
    item = fetch('/git/ref/tags/'+tag)['object']
    for _ in range(5):
        if item['type'] == 'commit':
            return item['sha']
        if item['type'] != 'tag' or not REVISION.fullmatch(item['sha']):
            break
        item = fetch('/git/tags/'+item['sha'])['object']
    raise ValueError('release tag does not resolve to an immutable commit')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, default=Path(__file__).resolve().parents[1]/'sources.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sources = json.loads(args.sources.read_text())
    stable = select_stable(fetch('/releases?per_page=100'))
    proposal = candidate(sources['hermes']['tag'], sources['hermes_commit'], stable, resolve_tag(stable['tag_name']))
    # Only the requested proposal is written. Source pins and SDK definitions are untouched.
    args.output.write_text(json.dumps(proposal, indent=2)+'\n')
    print('Review candidate written' if proposal else 'No newer stable release')


if __name__ == '__main__':
    main()
