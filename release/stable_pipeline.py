"""Prepare and qualify official Hermes stable releases from trusted main."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from release.detect import REVISION, VERSION, resolve_tag as resolve_upstream_tag, version

UPSTREAM = 'NousResearch/hermes-agent'
ROOT = Path(__file__).resolve().parents[1]
BOT_ID = 41898282
BOT_LOGIN = 'github-actions[bot]'
ACTIONS_APP_ID = 15368
STATUS_CONTEXT = 'Hermes stable release qualification'
HISTORY = 'release/hermes-stable-history.json'
SDK = 'sdks/hermes-experiment/'
SCOPE = {'sources.json', HISTORY, 'release/upstream-locks/provenance.json', 'release/upstream-locks/hermes/pm/lock.json',
         *(SDK + name for name in ('VERSION', 'sdkcraft.yaml', 'core-requirements.txt',
                                    'plugin-requirements.txt'))}
CAPTURED = re.compile(
    r'release/upstream-locks/hermes/(?:[A-Za-z0-9_.-]+/)*'
    r'(?:package\.json|pnpm-lock\.yaml|pnpm-workspace\.yaml|uv\.lock|pyproject\.toml)\Z')


def run(*command, cwd=ROOT, env=None, stdin=None):
    result = subprocess.run(command, cwd=cwd, env=env, input=stdin, text=True, check=True,
                            stdout=subprocess.PIPE, timeout=900)
    return result.stdout.strip()


def gh(endpoint, *, pages=False, method='GET', payload=None):
    args = ['gh', 'api', '--method', method]
    if pages:
        args.append('--paginate')
    if payload is not None:
        args.extend(('--input', '-'))
    result = run(*args, endpoint, stdin=None if payload is None else json.dumps(payload))
    if not result:
        return None
    return decode_pages(result) if pages else json.loads(result)


def decode_pages(raw):
    decoder = json.JSONDecoder()
    items = []
    while raw:
        page, end = decoder.raw_decode(raw)
        if not isinstance(page, list):
            raise ValueError('GitHub pagination returned an invalid page')
        items.extend(page)
        raw = raw[end:].lstrip()
    return items


def resolve_tag(tag):
    return resolve_upstream_tag(tag, fetcher=lambda path: gh(f'repos/{UPSTREAM}{path}'))


def discover(releases, current_tag, observed, resolve):
    current = version(current_tag)
    published = {}
    ids = set()
    for release in releases:
        tag = release['tag_name']
        if not VERSION.fullmatch(tag):
            continue
        if type(release['draft']) is not bool or type(release['prerelease']) is not bool:
            raise ValueError(f'{tag} lacks release state metadata')
        if release['draft'] or release['prerelease']:
            continue
        if tag not in observed and version(tag) <= current:
            continue
        release_id = release['id']
        timestamp = release['published_at']
        if (type(release_id) is not int or release_id <= 0 or
                not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', timestamp)):
            raise ValueError(f'{tag} lacks release identity or publication date')
        datetime.fromisoformat(timestamp)
        if tag in published or release_id in ids:
            raise ValueError(f'duplicate release metadata for {tag}')
        published[tag] = {'tag': tag, 'id': release_id, 'published_at': timestamp}
        ids.add(release_id)
    if missing := observed.keys() - published.keys():
        raise ValueError('Previously observed stable releases missing: ' + ', '.join(sorted(missing)))
    for tag, item in published.items():
        revision = resolve(tag)
        if not REVISION.fullmatch(revision):
            raise ValueError(f'{tag} lacks an immutable commit')
        recorded = observed.get(tag, {})
        if recorded.get('id', item['id']) != item['id']:
            raise ValueError(f'{tag} has a different GitHub release ID')
        if recorded.get('revision', revision) != revision:
            raise ValueError(f'Previously observed tag {tag} moved')
        if recorded.get('published_at', item['published_at']) != item['published_at']:
            raise ValueError(f'{tag} publication timestamp changed')
        item['revision'] = revision
    return [published[tag] for tag in sorted(published, key=version) if version(tag) > current]


def branch(release):
    version(release['tag'])
    return 'release/hermes/' + release['tag']


def pr_body(release):
    pin = {key: release[key] for key in ('tag', 'id', 'revision', 'published_at')}
    return ('Automated Workshop A update for the official Hermes stable release.\n\n'
            'The exact candidate and target commits require full SDK qualification. '
            'SDK Store publication and Workshop refresh require separate authorization.\n\n'
            '<!-- hermes-stable:' + json.dumps(pin, sort_keys=True, separators=(',', ':')) + ' -->')


def recognized(pr, release, repo, *, open_only=True):
    user = pr.get('user') or {}
    head = pr.get('head') or {}
    base = pr.get('base') or {}
    return (type(pr.get('number')) is int and pr['number'] != 3
            and user.get('id') == BOT_ID and user.get('login') == BOT_LOGIN and user.get('type') == 'Bot'
            and ((pr.get('state') == 'open' and pr.get('draft') is False) or not open_only)
            and head.get('ref') == branch(release) and base.get('ref') == 'main'
            and ((head.get('repo') or {}).get('full_name', '').casefold() == repo.casefold()
                 or (not open_only and head.get('repo') is None))
            and (base.get('repo') or {}).get('full_name', '').casefold() == repo.casefold()
            and bool(REVISION.fullmatch(head.get('sha', ''))) and pr.get('body') == pr_body(release))


def protection_ready(rules, settings):
    pr_rulesets = {rule['ruleset_id'] for rule in rules if rule['type'] == 'pull_request'}
    if not any(rule['type'] == 'non_fast_forward' for rule in rules):
        return False
    for rule in rules:
        if rule['type'] != 'required_status_checks' or rule['ruleset_id'] not in pr_rulesets:
            continue
        config = settings[rule['ruleset_id']]
        params = rule['parameters']
        # GitHub hides this field from tokens without ruleset write access.
        # Native auto-merge uses its ordinary required-check path.
        if (config.get('enforcement') == 'active' and config.get('bypass_actors', []) == []
                and params.get('strict_required_status_checks_policy') is True
                and any(check['context'] == STATUS_CONTEXT and check.get('integration_id') == ACTIONS_APP_ID
                        for check in params['required_status_checks'])):
            return True
    return False


def qualified(result, expected, live):
    return result == 'success' and expected == live and all(
        REVISION.fullmatch(expected.get(key, '')) for key in ('head', 'base'))


def main_tip(repo):
    sha = gh(f'repos/{repo}/git/ref/heads/main')['object']['sha']
    if not REVISION.fullmatch(sha):
        raise ValueError('Invalid target branch revision')
    return sha


def history(repo):
    sources = json.loads((ROOT/'sources.json').read_text())
    current = sources['hermes']['tag']
    installed = sources['hermes_commit']
    ledger = json.loads((ROOT/HISTORY).read_text()) if (ROOT/HISTORY).exists() else {}
    initial = {'revision': installed}
    if 'release_id' in sources['hermes']:
        initial.update(id=sources['hermes']['release_id'],
                       published_at=sources['hermes']['published_at'])
    ledger.setdefault(current, initial)
    if ledger[current]['revision'] != installed:
        raise ValueError('Installed core pin disagrees with the release ledger')
    installed_history = dict(ledger)
    proposals = {}
    for pr in gh(f'repos/{repo}/pulls?state=all&base=main&per_page=100', pages=True):
        ref = (pr['head'] or {}).get('ref', '')
        if not ref.startswith('release/hermes/') or pr['user']['id'] != BOT_ID:
            continue
        body = re.search(r'<!-- hermes-stable:(\{[^\n]+\}) -->\Z', pr.get('body') or '')
        if not body:
            raise ValueError(f'Release PR #{pr["number"]} lacks release identity')
        release = json.loads(body[1])
        if not recognized(pr, release, repo, open_only=False):
            raise ValueError(f'Release PR #{pr["number"]} has inconsistent origin or identity')
        tag = release['tag']
        previous = ledger.get(tag, {})
        if any(release[key] != value for key, value in previous.items()):
            raise ValueError(f'Release PR #{pr["number"]} disagrees with persisted identity')
        ledger[tag] = {key: release[key] for key in ('id', 'revision', 'published_at')}
        if tag in proposals:
            raise ValueError(f'Multiple existing release PRs for {tag}')
        proposals[tag] = pr
    return current, installed_history, ledger, proposals


def changed_paths(paths):
    files = set(paths)
    unexpected = {path for path in files - SCOPE if not CAPTURED.fullmatch(path)}
    if unexpected or not {'sources.json', HISTORY, SDK + 'VERSION', SDK + 'sdkcraft.yaml'} <= files:
        raise ValueError(f'Unexpected change scope: {sorted(files)}')
    return files


def pin_in_tree(tree, release):
    expected = {key: release[key] for key in ('id', 'revision', 'published_at')}
    source = json.loads(run('git', 'show', f'{tree}:sources.json'))
    ledger = json.loads(run('git', 'show', f'{tree}:{HISTORY}'))
    return (source['hermes']['tag'] == release['tag'] and source['hermes_commit'] == release['revision']
            and source['hermes']['release_id'] == release['id']
            and source['hermes']['published_at'] == release['published_at']
            and ledger.get(release['tag']) == expected)


def generate(release, base, ledger):
    with tempfile.TemporaryDirectory(prefix='hermes-candidate-') as directory:
        checkout = Path(directory)/'upstream'
        worktree = Path(directory)/'candidate'
        run('git', 'init', '-q', str(checkout))
        ref = 'refs/tags/' + release['tag']
        run('git', 'fetch', '--depth=1', f'https://github.com/{UPSTREAM}.git', ref, cwd=checkout)
        if run('git', 'rev-parse', 'FETCH_HEAD^{commit}', cwd=checkout) != release['revision']:
            raise ValueError('Upstream tag changed before candidate generation')
        run('git', 'checkout', '--detach', release['revision'], cwd=checkout)
        run('git', 'worktree', 'add', '--detach', str(worktree), base)
        try:
            env = {key: value for key, value in os.environ.items()
                   if key not in {'GH_TOKEN', 'GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN'}}
            run('python3', str(ROOT/'release/update_hermes_core.py'), '--tag', release['tag'],
                '--commit', release['revision'], '--release-id', str(release['id']),
                '--published-at', release['published_at'], '--checkout', str(checkout),
                '--root', str(worktree), cwd=worktree, env=env)
            (worktree/HISTORY).write_text(json.dumps(ledger, indent=2, sort_keys=True)+'\n')
            run('git', 'add', '-A', cwd=worktree)
            changed_paths(run('git', 'diff', '--cached', '--name-only', '--no-renames', cwd=worktree).splitlines())
            tree = run('git', 'write-tree', cwd=worktree)
            if not pin_in_tree(tree, release):
                raise ValueError('Generated source pins are inconsistent')
            author = f'{BOT_ID}+{BOT_LOGIN}@users.noreply.github.com'
            env.update(GIT_AUTHOR_NAME=BOT_LOGIN, GIT_AUTHOR_EMAIL=author,
                       GIT_COMMITTER_NAME=BOT_LOGIN, GIT_COMMITTER_EMAIL=author,
                       GIT_AUTHOR_DATE=release['published_at'], GIT_COMMITTER_DATE=release['published_at'])
            return run('git', '-c', 'commit.gpgsign=false', 'commit-tree', tree, '-p', base,
                       '-m', f"Update Hermes core to {release['tag']}", env=env)
        finally:
            run('git', 'worktree', 'remove', '--force', str(worktree))


def assert_candidate(base, head, release):
    if run('git', 'rev-list', '--parents', '-n', '1', head).split() != [head, base]:
        raise ValueError('Candidate must have exactly one commit on the tested target')
    changed_paths(run('git', 'diff', '--name-only', '--no-renames', base, head).splitlines())
    for row in run('git', 'diff', '--raw', '--no-renames', base, head).splitlines():
        modes = row.split()[:2]
        if any(mode.removeprefix(':') not in {'000000', '100644'} for mode in modes):
            raise ValueError('Candidate changes a non-regular source file or file mode')
    if not pin_in_tree(head, release):
        raise ValueError('Candidate does not carry the exact official release identity')


def branch_head(repo, ref):
    rows = gh(f'repos/{repo}/git/matching-refs/heads/{ref}')
    return next((row['object']['sha'] for row in rows if row['ref'] == 'refs/heads/' + ref), '')


def fetch_commit(sha):
    if not REVISION.fullmatch(sha):
        raise ValueError('Invalid candidate or target commit')
    run('git', '-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential',
        'fetch', '--no-tags', 'origin', sha)


def publish(repo, release, base, head, existing):
    ref = branch(release)
    old = branch_head(repo, ref)
    if existing is not None:
        if not recognized(existing, release, repo):
            raise ValueError(f'Existing PR #{existing["number"]} must be open and have an unchanged release identity')
        if existing['head']['sha'] != old:
            raise ValueError('Candidate head changed during preparation')
        if old != head:
            fetch_commit(old)
            old_base = run('git', 'rev-parse', old + '^')
            if old_base == base:
                raise ValueError('Existing candidate differs from deterministic generation on the same base')
            assert_candidate(old_base, old, release)
            old_ledger = json.loads(run('git', 'show', f'{old}:{HISTORY}'))
            if generate(release, old_base, old_ledger) != old:
                raise ValueError('Existing candidate differs from deterministic generation on its prior base')
    elif old and old != head:
        raise ValueError(f'Unrecognized branch {ref} already exists')
    if main_tip(repo) != base:
        raise ValueError('Target changed during preparation. The next run will regenerate candidates.')
    if old != head:
        full_ref = 'refs/heads/' + ref
        run('git', '-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential',
            'push', f'--force-with-lease={full_ref}:{old}', 'origin', f'{head}:{full_ref}')
    if existing is None:
        existing = gh(f'repos/{repo}/pulls', method='POST', payload={
            'head': ref, 'base': 'main', 'title': f"Update Hermes core to {release['tag']}",
            'body': pr_body(release), 'draft': False, 'maintainer_can_modify': False})
    pr = gh(f'repos/{repo}/pulls/{existing["number"]}')
    if not recognized(pr, release, repo) or pr['head']['sha'] != head:
        raise ValueError('GitHub did not confirm the expected release PR')
    print(f"Release {release['tag']}, PR #{pr['number']}, candidate {head}, target {base}", flush=True)
    return {**release, 'pr': pr['number'], 'head': head, 'base': base}


def prepare(repo):
    base = main_tip(repo)
    if run('git', 'rev-parse', 'HEAD') != base:
        raise ValueError('Trusted main checkout is stale. Run release discovery on the current main tip.')
    current, installed_history, ledger, existing = history(repo)
    releases = gh(f'repos/{UPSTREAM}/releases?per_page=100', pages=True)
    queue = discover(releases, current, ledger, resolve_tag)
    print('Stable releases awaiting qualification:', ', '.join(item['tag'] for item in queue) or 'none',
          flush=True)
    if not queue:
        return None

    # The generated PR preserves its own identity even if qualification fails.
    # Keep the commit on the same base identical when new releases arrive later.
    published_current = next(item for item in releases if item['tag_name'] == current
                             and not item['prerelease'] and not item['draft'])
    installed_history[current] = {'id': published_current['id'],
                                  'published_at': published_current['published_at'],
                                  'revision': ledger[current]['revision']}
    oldest = None
    for index, item in enumerate(queue):
        prior = existing.get(item['tag'])
        if index and prior is not None:
            print(f"Release {item['tag']} already has PR #{prior['number']}", flush=True)
            continue
        try:
            candidate_history = {**installed_history, item['tag']: {
                key: item[key] for key in ('id', 'published_at', 'revision')}}
            head = generate(item, base, candidate_history)
            assert_candidate(base, head, item)
            candidate = publish(repo, item, base, head, prior)
            if index == 0:
                oldest = candidate
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            print(f"::warning title=Release candidate {item['tag']}::Preparation blocked: {error}", flush=True)
    if oldest is None:
        raise ValueError('Oldest outstanding release could not be prepared. Later releases cannot merge.')
    return oldest


def live_candidate(repo, candidate):
    pr = gh(f"repos/{repo}/pulls/{candidate['pr']}")
    if not recognized(pr, candidate, repo):
        raise ValueError('PR does not match the authenticated release bot and expected release identity')
    return pr, {'head': pr['head']['sha'], 'base': main_tip(repo)}


def status(repo, candidate, state, description):
    run_url = f"https://github.com/{repo}/actions/runs/{int(os.environ['GITHUB_RUN_ID'])}"
    gh(f"repos/{repo}/statuses/{candidate['head']}", method='POST',
       payload={'state': state, 'context': STATUS_CONTEXT, 'description': description,
                'target_url': run_url})


def require_protection(repo):
    settings = gh(f'repos/{repo}')
    if not settings.get('allow_auto_merge') or not settings.get('allow_squash_merge'):
        raise ValueError('Repository must allow GitHub auto-merge and squash merges')
    rules = gh(f'repos/{repo}/rules/branches/main', pages=True)
    configs = {rule_id: gh(f'repos/{repo}/rulesets/{rule_id}') for rule_id in
               {rule['ruleset_id'] for rule in rules if rule['type'] == 'required_status_checks'}}
    if not protection_ready(rules, configs):
        raise ValueError('Main requires an active strict qualification ruleset and a force-push block')


def finalize(repo, candidate, result):
    if not candidate:
        raise ValueError('Missing candidate from preparation')
    expected = {key: candidate[key] for key in ('head', 'base')}
    pr, live = live_candidate(repo, candidate)
    if live != expected:
        raise ValueError('Candidate or target changed. Fresh qualification is required.')
    if not qualified(result, expected, live):
        status(repo, candidate, 'failure', 'Full source and SDK qualification did not pass')
        raise ValueError(f'Full source and SDK qualification did not pass: {result}')
    fetch_commit(candidate['head'])
    assert_candidate(candidate['base'], candidate['head'], candidate)
    if resolve_tag(candidate['tag']) != candidate['revision']:
        raise ValueError('Official release tag moved during qualification')
    require_protection(repo)
    auto = pr.get('auto_merge')
    if auto and (auto.get('enabled_by') or {}).get('id') != BOT_ID:
        raise ValueError('This PR already has auto-merge enabled by another actor')
    # Hold the required context pending so GitHub queues native auto-merge.
    # Strict protection prevents this exact-head result from applying on an older base.
    status(repo, candidate, 'pending', 'Enabling GitHub auto-merge for the tested candidate')
    pr, live = live_candidate(repo, candidate)
    if not qualified(result, expected, live):
        raise ValueError('Candidate or target changed before auto-merge could be enabled')
    if not pr.get('auto_merge'):
        request = gh('graphql', method='POST', payload={
            'query': ('mutation($id: ID!, $head: GitObjectID!) { enablePullRequestAutoMerge(input: '
                      '{pullRequestId: $id, expectedHeadOid: $head, mergeMethod: SQUASH}) '
                      '{pullRequest { number }}}'),
            'variables': {'id': pr['node_id'], 'head': candidate['head']}})
        if request['data']['enablePullRequestAutoMerge']['pullRequest']['number'] != candidate['pr']:
            raise ValueError('GitHub did not confirm auto-merge for the expected PR')
    pr, live = live_candidate(repo, candidate)
    if not qualified(result, expected, live):
        raise ValueError('Candidate or target changed while awaiting auto-merge')
    status(repo, candidate, 'success', 'Full source and SDK qualification passed for the tested target')
    print(f"GitHub auto-merge enabled for PR #{candidate['pr']} at {candidate['head']}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'finalize'))
    parser.add_argument('--candidate', type=json.loads)
    parser.add_argument('--qualification-result')
    args = parser.parse_args()
    repo = os.environ['GITHUB_REPOSITORY']
    if repo != 'hermi0ne-chipster6/hermes-experiment' or os.environ['GITHUB_REF'] != 'refs/heads/main':
        raise ValueError('The stable repository pipeline must run from trusted main')
    if args.command == 'prepare':
        candidate = prepare(repo)
        if candidate:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                for key in ('head', 'base'):
                    print(f'{key}={candidate[key]}', file=output)
                print('candidate=' + json.dumps(candidate, separators=(',', ':')), file=output)
    else:
        finalize(repo, args.candidate, args.qualification_result)


if __name__ == '__main__':
    main()
