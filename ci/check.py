"""Local/hosted validation; no SDKs, services or candidate packages are executed."""
import argparse
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


def validate_workflow(doc):
    if doc.get('permissions') != {'contents': 'read'}:
        raise ValueError('workflows must use read-only contents permission')
    events = doc.get('on', {})
    if not isinstance(events, dict) or set(events)-{'push', 'pull_request', 'schedule', 'workflow_dispatch'}:
        raise ValueError('unsupported/privileged workflow trigger')
    for job in doc.get('jobs', {}).values():
        if 'permissions' in job and job['permissions'] != {'contents':'read'}:
            raise ValueError('job cannot elevate workflow permissions')
        labels = job.get('runs-on', [])
        if isinstance(labels, str):
            labels = [labels]
        if 'self-hosted' in labels:
            if set(events) != {'workflow_dispatch'} or 'refs/heads/main' not in job.get('if', ''):
                raise ValueError('privileged runner requires manual dispatch of main')
        for step in job.get('steps', []):
            if 'uses' in step and not re.fullmatch(r'[\w.-]+/[\w./-]+@[0-9a-f]{40}', step['uses']):
                raise ValueError('action must have an immutable full commit pin')


def require_build_dispatch(branch, runner_ready):
    if branch != 'main':
        raise ValueError('SDK qualification is restricted to the reviewed main branch')
    if not runner_ready:
        raise ValueError('BLOCKED: verify and register an online disposable Ubuntu 26.04 AMD64 KVM runner, then acknowledge runner_ready')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-preflight', action='store_true')
    parser.add_argument('--branch', default='')
    parser.add_argument('--runner-ready', default='false')
    args = parser.parse_args()
    if args.build_preflight:
        require_build_dispatch(args.branch, args.runner_ready == 'true')
        return
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
        validate_workflow(yaml.load(path.read_text(), Loader=yaml.BaseLoader))
    if shell:
        subprocess.run(['shellcheck', '--severity=warning', *shell], check=True)
    print(json.dumps({'components':len(records), 'syntax_files':syntax_count,
                      'shell_scripts':len(shell), 'scope':'read-only source validation'}))


if __name__ == '__main__':
    main()
