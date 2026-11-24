"""Read-only release discovery. A proposal is never compatibility acceptance."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import HTTPError
import xml.etree.ElementTree as ET

from packaging.version import InvalidVersion, Version
import yaml

try:
    from release.inventory import ROOT, inventory
except ModuleNotFoundError:
    from inventory import ROOT, inventory

HOSTS = {'api.github.com', 'raw.githubusercontent.com', 'pypi.org',
         'registry.npmjs.org', 'nodejs.org', 'hub.docker.com',
         'api.snapcraft.io', 'ubuntu.com', 'download.docker.com'}
SHA = re.compile(r'[0-9a-f]{40}\Z')
COMMON_CHECKS = ['bridge', 'routing', 'memory', 'heartbeat', 'native-gateways',
                 'MCP-protocol-and-authorization', 'refresh-and-rollback']
ROLE_CHECKS = {'hermes-experiment': 'sdk-a', 'hermes-execution': 'sdk-b', 'hermes-rea': 'sdk-c'}


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).scheme != 'https' or urlparse(newurl).hostname not in HOSTS:
            raise ValueError('unapproved metadata redirect')
        result = super().redirect_request(req, fp, code, msg, headers, newurl)
        if result is not None and urlparse(req.full_url).hostname != urlparse(newurl).hostname:
            result.remove_header('Authorization')
        return result


class Client:
    @lru_cache(maxsize=8)
    def get(self, url, *, raw=False):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname not in HOSTS:
            raise ValueError('unapproved metadata host')
        headers = {'User-Agent': 'hermes-sdk-release-monitor/1', 'Accept': 'application/json'}
        if parsed.hostname == 'api.github.com' and os.environ.get('GITHUB_TOKEN'):
            headers['Authorization'] = 'Bearer '+os.environ['GITHUB_TOKEN']
        if parsed.hostname == 'api.snapcraft.io':
            headers['Snap-Device-Series'] = '16'
        for attempt in range(2):
            try:
                with build_opener(SafeRedirect()).open(Request(url, headers=headers), timeout=20) as response:
                    body = response.read(16*1024*1024+1)
                if len(body) > 16*1024*1024:
                    raise ValueError('metadata response exceeds 16 MiB')
                return body if raw else json.loads(body)
            except (OSError, TimeoutError):
                if attempt:
                    raise
                time.sleep(1)


def stable(value):
    version = Version(value)
    if version.is_prerelease or version.is_devrelease:
        raise ValueError('not a stable version: '+value)
    return version


def api(repository):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('invalid upstream repository')
    return 'https://api.github.com/repos/'+repository


def resolve_tag(repository, tag, client):
    base = api(repository)
    value = client.get(base+'/git/ref/tags/'+quote(tag, safe=''))['object']
    for _ in range(5):
        if not SHA.fullmatch(value.get('sha', '')):
            raise ValueError('tag lacks an immutable revision')
        if value['type'] == 'commit':
            return value['sha']
        if value['type'] != 'tag':
            break
        value = client.get(base+'/git/tags/'+value['sha'])['object']
    raise ValueError('tag does not resolve to an immutable commit')


def github_release(record, client):
    items = client.get(api(record['repository'])+'/releases?per_page='+str(record.get('release_page_size', 100)))
    choices = []
    for item in items:
        match = re.fullmatch(record.get('pattern', r'v(\d+\.\d+\.\d+)'), item.get('tag_name', ''))
        if match and not item.get('draft') and not item.get('prerelease'):
            try:
                choices.append((stable(match[1]), item))
            except (InvalidVersion, ValueError):
                continue
    if not choices:
        raise ValueError('no stable published release found in upstream release window')
    if record.get('chronological'):
        version, item = max(choices, key=lambda choice: choice[1]['published_at'])
    else:
        version, item = max(choices, key=lambda choice: choice[0])
    result = {'version': str(version), 'tag': item['tag_name'],
              'revision': resolve_tag(record['repository'], item['tag_name'], client)}
    result['url'] = 'https://github.com/'+record['repository']+'/releases/tag/'+quote(item['tag_name'], safe='')
    return result


def latest(record, client, root):
    kind = record['kind']
    if kind in ('github-release', 'github-action'):
        return github_release(record, client)
    if kind == 'github-tags':
        entries = client.get(api(record['repository'])+'/tags?per_page=100')
        choices = [(stable(match[1]), item) for item in entries
                   if (match := re.fullmatch(record['pattern'], item['name']))]
        if not choices:
            raise ValueError('no stable upstream tag found')
        version, item = max(choices, key=lambda entry: entry[0])
        if not SHA.fullmatch(item['commit']['sha']):
            raise ValueError('tag lacks immutable revision')
        return dict(version=str(version), tag=item['name'], revision=item['commit']['sha'])
    if kind == 'npm':
        base = 'https://registry.npmjs.org/'+quote(record['package'], safe='')
        item = client.get(base+'/latest')
        beta_only = False
        try:
            stable(item['version'])
        except (InvalidVersion, ValueError):
            versions = client.get(base).get('versions', {})
            choices = []
            for value, entry in versions.items():
                try:
                    choices.append((stable(value), entry))
                except (InvalidVersion, ValueError):
                    continue
            if not choices:
                if not all(Version(v).is_prerelease for v in record.get('versions', [record['current']])):
                    raise ValueError('npm has no stable published version')
                beta_only = True
            else:
                _, item = max(choices, key=lambda entry: entry[0])
        dist = item['dist']
        if not dist.get('integrity'):
            raise ValueError('npm candidate lacks integrity metadata')
        return dict(version=item['version'], integrity=dist['integrity'], url=dist.get('tarball'), eligible=not beta_only)
    if kind == 'pypi':
        feed = ET.fromstring(client.get('https://pypi.org/rss/project/'+quote(record['package'], safe='')+'/releases.xml', raw=True))
        choices, prereleases = [], []
        for item in feed.findall('./channel/item'):
            value = item.findtext('title')
            try:
                parsed = Version(value)
                if parsed.is_prerelease or parsed.is_devrelease:
                    prereleases.append((parsed, value))
                else:
                    choices.append((parsed, value))
            except (InvalidVersion, ValueError, TypeError):
                continue
        beta_only = not choices and all(Version(v).is_prerelease for v in record.get('versions', [record['current']]))
        if beta_only:
            choices = prereleases
        for version, original in sorted(set(choices), reverse=True):
            try:
                item = client.get('https://pypi.org/pypi/'+quote(record['package'], safe='')+'/'+quote(original, safe='')+'/json')
            except HTTPError as error:
                if error.code == 404:
                    continue  # A release may have been removed after the RSS item was cached.
                raise
            releases = [entry for entry in item['urls'] if not entry.get('yanked')]
            if releases:
                return {'version': str(version), 'requires_python': item['info'].get('requires_python'),
                        'sha256': sorted({entry['digests']['sha256'] for entry in releases}),
                        'eligible':not beta_only}
        raise ValueError('no stable non-yanked PyPI release found')
    if kind == 'node':
        entries = client.get('https://nodejs.org/dist/index.json')
        choices = [(stable(item['version']), item) for item in entries
                   if re.fullmatch(r'v\d+\.\d+\.\d+', item['version'])]
        version, item = max(choices, key=lambda entry: entry[0])
        return dict(version=str(version), lts=item.get('lts'),
                    checksums_url='https://nodejs.org/dist/'+item['version']+'/SHASUMS256.txt')
    if kind == 'hermes-catalog':
        hermes = github_release(dict(repository='NousResearch/hermes-agent',
            pattern=r'v(\d{1,3}\.\d+\.\d+)', chronological=True), client)
        url = ('https://raw.githubusercontent.com/NousResearch/hermes-agent/'+hermes['revision']+
               '/plugin-catalog/'+record['catalog']+'.yaml')
        item = yaml.safe_load(client.get(url, raw=True))
        if not SHA.fullmatch(item['sha']):
            raise ValueError('plugin catalog does not pin an immutable commit')
        return dict(revision=item['sha'], repository=item['repo'], subdir=item.get('subdir'),
                    version=item.get('version'), hermes_tag=hermes['tag'], url=url)
    if kind == 'snap':
        item = client.get('https://api.snapcraft.io/v2/snaps/info/'+record['package'])
        entries = [entry for entry in item['channel-map']
                   if all(entry['channel'].get(k) == v for k, v in
                          [('architecture', 'amd64'), ('track', record['track']), ('risk', record['risk'])])]
        if len(entries) != 1:
            raise ValueError('stable snap channel/architecture not uniquely available')
        return dict(version=entries[0]['version'], revision=entries[0]['revision'])
    if kind == 'docker-image':
        base = 'https://hub.docker.com/v2/repositories/'+record['image']+'/tags/'
        pinned = client.get(base+quote(record['current'], safe=''))
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', pinned.get('digest', '')):
            raise ValueError('pinned image metadata lacks a valid digest')
        if pinned.get('digest') != record['digest']:
            return dict(tag=record['current'], digest=pinned.get('digest'), drift=True)
        entries = client.get(base+'?page_size=100')['results']
        choices = [(stable(match[1]), item) for item in entries
                   if (match := re.fullmatch(r'v?(\d+\.\d+\.\d+)', item['name']))]
        if not choices:
            raise ValueError('no stable image tag found in registry window')
        version, item = max(choices, key=lambda entry: entry[0])
        item = client.get(base+quote(item['name'], safe=''))
        amd64 = [image['digest'] for image in item.get('images', [])
                 if image.get('architecture') == 'amd64' and image.get('os') == 'linux']
        if not item.get('digest') or not amd64:
            raise ValueError('image candidate lacks index/AMD64 digest')
        return dict(version=str(version), tag=item['name'], digest=item['digest'], amd64_digest=amd64[0])
    if kind == 'github-file':
        # A publisher track is discovery evidence, never proof of Store promotion.
        item = client.get(api(record['repository'])+'/contents/'+record['file']+'?ref='+record['ref'])
        version = base64.b64decode(item['content'], validate=False).decode().strip()
        stable(version)
        return dict(version=version, source_blob=item['sha'], publication='requires SDK Store verification')
    if kind == 'upstream-lock':
        body = client.get('https://raw.githubusercontent.com/'+record['repository']+'/'+
                          record['revision']+'/'+record['path'], raw=True)
        digest = hashlib.sha256(body).hexdigest()
        if digest != record['current']:
            raise ValueError('captured dependency input differs from its immutable upstream source')
        return dict(digest=digest, version='verified immutable dependency input')
    if kind == 'docker-apt':
        body = client.get('https://download.docker.com/linux/ubuntu/dists/resolute/stable/binary-amd64/Packages.gz', raw=True)
        entries = []
        for paragraph in gzip.decompress(body).decode().split('\n\n'):
            fields = dict(line.split(': ', 1) for line in paragraph.splitlines() if ': ' in line and not line.startswith(' '))
            if fields.get('Package') == 'docker-ce':
                match = re.match(r'(?:\d+:)?(\d+\.\d+\.\d+)', fields['Version'])
                if match:
                    entries.append((stable(match[1]), fields))
        if not entries:
            raise ValueError('Docker stable apt metadata contained no docker-ce package')
        version, item = max(entries, key=lambda entry: entry[0])
        return dict(version=str(version), debian_version=item['Version'], sha256=item.get('SHA256'))
    if kind == 'ubuntu-security':
        baseline = json.loads((root/'release/platform-packages.json').read_text())
        packages = {entry[key].split(':')[0] for entries in baseline['packages'].values()
                    for entry in entries for key in ('package', 'source') if entry.get(key)}
        notices = []
        for offset in range(0, 2000, 20):
            page = client.get(f'https://ubuntu.com/security/notices.json?limit=20&offset={offset}')['notices']
            if not page:
                return dict(notices=notices, version=record['current'])
            reached_cutoff = False
            for notice in page:
                if notice['published'][:19] < record['current'][:19]:
                    reached_cutoff = True
                    continue
                affected = [entry for entry in notice.get('release_packages', {}).get('resolute', [])
                            if entry['name'] in packages]
                if affected:
                    notices.append(dict(id=notice['id'], packages=affected,
                        url='https://ubuntu.com/security/notices/'+notice['id']))
            if reached_cutoff:
                return dict(notices=notices, version=record['current'])
        raise ValueError('Ubuntu notice pagination did not reach the reviewed baseline')
    raise ValueError('unsupported metadata source: '+kind)


def inspect_component(record, client, root=ROOT):
    result = dict(component=record['name'], kind=record['kind'], current=record['current'],
                  roles=record['roles'], inputs=record['inputs'], status='current')
    candidate = latest(record, client, Path(root))
    result['candidate'] = candidate
    result['qualification'] = record.get('qualification', record.get('compatibility', 'requires compatibility review'))
    roles = set(record['roles'])
    result['required_checks'] = ['hosted-checks']
    if roles-{'ci'}:
        result['required_checks'] += [check for role, check in ROLE_CHECKS.items() if role in roles]
        result['required_checks'] += COMMON_CHECKS
    kind = record['kind']
    if candidate.get('eligible') is False:
        result['status'] = 'prerelease-channel-review'
    elif candidate.get('drift'):
        result['status'] = 'upstream-drift'
    elif kind == 'hermes-catalog':
        if candidate['revision'] != record['current'] or candidate['repository'].removeprefix('https://github.com/') != record['repository'] or candidate.get('subdir') != record['subdir']:
            result['status'] = 'review-required'
    elif kind == 'github-action':
        if candidate['revision'] != record['current']:
            result['status'] = 'review-required'
    elif kind == 'snap':
        if candidate['revision'] != record['revision']:
            result['status'] = 'review-required'
    elif kind == 'ubuntu-security':
        if candidate['notices']:
            result['status'] = 'advisory-review-required'
    elif kind == 'upstream-lock':
        pass  # latest() verified both the immutable source and its captured digest.
    else:
        current = record.get('versions', [record['current']])
        pattern = record.get('pattern', r'v?(\d+\.\d+\.\d+)')
        values = []
        for value in current:
            match = re.fullmatch(pattern, value)
            values.append(Version(match[1] if match else value))
        version = Version(candidate['version'])
        if any(value < version for value in values):
            result['status'] = 'review-required'
    if kind == 'github-release' and record.get('revision'):
        pinned_revision = resolve_tag(record['repository'], record['current'], client)
        result['observed_pinned_revision'] = pinned_revision
        if pinned_revision != record['revision']:
            result['status'] = 'upstream-drift'
    return result


def monitor(records, client=None, root=ROOT):
    client = client or Client()
    def check(record):
        try:
            return inspect_component(record, client, root), None
        except Exception as error:
            return None, {'component': record['name'], 'error': type(error).__name__+': '+str(error)[:300]}
    results, errors = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result, error in pool.map(check, records):
            if result is not None:
                results.append(result)
            if error is not None:
                errors.append(error)
    return dict(generated_at=datetime.now(timezone.utc).isoformat(),
                complete=not errors, checked_count=len(records), results=results, errors=errors,
                promotion='operator-review-required', compatibility='not established by release discovery')


def write_reports(report, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output/'release-monitor.json').write_text(json.dumps(report, indent=2)+'\n')
    changes = [item for item in report['results'] if item['status'] != 'current']
    lines = ['# SDK upstream review', '',
             f"Metadata coverage: {'complete' if report['complete'] else 'INCOMPLETE'}; {report['checked_count']} components checked.",
             f'{len(changes)} review items; {len(report["errors"])} metadata errors.', '',
             'Release discovery does not establish compatibility or authorize promotion.', '',
             '| Component | Current | Candidate | Status |', '| --- | --- | --- | --- |']
    for item in changes:
        candidate = item['candidate']
        value = candidate.get('tag') or candidate.get('version') or candidate.get('revision')
        lines.append(f"| {item['component']} | {item['current']} | {value} | {item['status']} |")
    if report['errors']:
        lines.extend(['', '## Incomplete checks', ''])
        lines.extend(f"- {item['component']}: {item['error']}" for item in report['errors'])
    (output/'release-monitor.md').write_text('\n'.join(lines)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    report = monitor(inventory(args.root), root=args.root)
    write_reports(report, args.output)
    print(json.dumps({'complete':report['complete'], 'checked':report['checked_count'],
                      'review_items':sum(item['status'] != 'current' for item in report['results']),
                      'errors':report['errors']}))
    return 0 if report['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
