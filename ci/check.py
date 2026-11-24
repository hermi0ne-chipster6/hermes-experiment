"""Local/hosted validation; no SDKs, services or candidate packages are executed."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from release.inventory import files, inventory  # noqa: E402


READ_ONLY = {'contents': 'read'}
TRUSTED_RELEASE_CALLER = (
    "github.workflow_ref == format('{0}/.github/workflows/releases.yml@refs/heads/main', "
    'github.repository)'
)
TRUSTED_HUMAN_CALLER = (
    "github.workflow_ref == format('{0}/.github/workflows/qualify-human-pr.yml@refs/heads/main', "
    'github.repository)'
)
RELEASE_WRITE_PERMISSIONS = {
    'prepare': {'contents': 'write', 'pull-requests': 'write'},
    'finalize': {'contents': 'write', 'pull-requests': 'write', 'statuses': 'write'},
}
RELEASE_REPOSITORY = "github.repository == 'hermi0ne-chipster6/hermes-experiment'"
RELEASE_BRANCH = "github.ref == 'refs/heads/main'"
TARGET_MAIN = f'{RELEASE_REPOSITORY} && {RELEASE_BRANCH}'
TRUSTED_SDK_CALLER = (
    f'{RELEASE_REPOSITORY} && (({TRUSTED_RELEASE_CALLER} && !inputs.human_candidate) || '
    f'({TRUSTED_HUMAN_CALLER} && inputs.human_candidate))'
)
HUMAN_INSPECT_PERMISSIONS = {'contents': 'read', 'pull-requests': 'read'}
HUMAN_PUBLISH_PERMISSIONS = {**HUMAN_INSPECT_PERMISSIONS, 'statuses': 'write'}
RUNNER_LABELS = ['self-hosted', 'linux', 'x64', 'hermes-sdk-build']


def validate_job_permissions(filename, name, job, events, permissions):
    guard = ' '.join(job.get('if', '').split())
    if job.get('runs-on') != 'ubuntu-24.04':
        raise ValueError(f'unsupported permissions for job {name}')
    if filename == 'releases.yml':
        expected = TARGET_MAIN
        if name == 'finalize':
            expected = ("always() && needs.prepare.result == 'success' && "
                        "needs.prepare.outputs.candidate != '' && " + expected)
        if (permissions == RELEASE_WRITE_PERMISSIONS.get(name) and guard == expected
                and set(events) == {'schedule', 'workflow_dispatch', 'push'}
                and events.get('push', {}).get('branches') == ['main']):
            return
    if filename == 'qualify-human-pr.yml' and set(events) == {'workflow_dispatch'}:
        if name == 'inspect' and permissions == HUMAN_INSPECT_PERMISSIONS and guard == TARGET_MAIN:
            return
        publish_guard = "always() && needs.inspect.result == 'success' && " + TARGET_MAIN
        if name == 'publish' and permissions == HUMAN_PUBLISH_PERMISSIONS and guard == publish_guard:
            return
    raise ValueError(f'unsupported permissions for job {name}')


def validate_workflow(doc, filename=None):
    if doc.get('permissions') != READ_ONLY:
        raise ValueError('workflow default permissions must be read-only')
    events = doc.get('on', {})
    if not isinstance(events, dict) or set(events) - {
        'push', 'pull_request', 'schedule', 'workflow_dispatch', 'workflow_call'
    }:
        raise ValueError('unsupported/privileged workflow trigger')
    for name, job in doc.get('jobs', {}).items():
        permissions = job.get('permissions', READ_ONLY)
        if permissions != READ_ONLY:
            validate_job_permissions(filename, name, job, events, permissions)
        labels = job.get('runs-on', [])
        if isinstance(labels, str):
            labels = [labels]
        if 'self-hosted' in labels:
            if (filename != 'sdk-qualification.yml' or name != 'sdk'
                    or set(events) != {'workflow_call'} or labels != RUNNER_LABELS
                    or ' '.join(job.get('if', '').split()) != TRUSTED_SDK_CALLER):
                raise ValueError('self-hosted runner requires the trusted release workflow or manual qualifier')
        if 'uses' in job and job['uses'] not in {
            './.github/workflows/checks.yml', './.github/workflows/sdk-qualification.yml'
        }:
            raise ValueError('unsupported reusable workflow')
        for step in job.get('steps', []):
            if 'uses' in step and not re.fullmatch(r'[\w.-]+/[\w./-]+@[0-9a-f]{40}', step['uses']):
                raise ValueError('action must have an immutable full commit pin')


def main():
    records = inventory(ROOT)
    syntax_count, shell = 0, []
    for path in files(ROOT):
        name = path.name
        if name.endswith('.json'):
            json.loads(path.read_text())
            syntax_count += 1
        if any(name.endswith(suffix) for suffix in ('.yaml', '.yml', '.yaml.example', '.yaml.in')):
            text = path.read_text().replace('@BASE@', 'ubuntu@26.04')
            yaml.safe_load(text)
            syntax_count += 1
        if name.endswith(('.toml', '.toml.example')):
            tomllib.loads(path.read_text())
            syntax_count += 1
        with path.open('rb') as source:
            header = source.read(32)
        if header.startswith((b'#!/bin/bash', b'#!/bin/sh')):
            shell.append(str(path))
    for path in (ROOT/'.github/workflows').glob('*.yml'):
        validate_workflow(yaml.load(path.read_text(), Loader=yaml.BaseLoader), path.name)
    if shell:
        subprocess.run(['shellcheck', '--severity=warning', *shell], check=True)
    print(json.dumps({'components':len(records), 'syntax_files':syntax_count,
                      'shell_scripts':len(shell), 'scope':'read-only source validation'}))


if __name__ == '__main__':
    main()
