"""Verify the running SDK's interpreter, install stamp and native CLI identity."""

import json
from pathlib import Path
import platform
import re
import subprocess
import sys


def check(sdk, launcher):
    pin = json.loads((sdk / 'share/hermes/core-pin.json').read_text(encoding='utf-8'))
    source = sdk / 'hermes-src'
    stamp = json.loads((source / 'install-stamp.json').read_text(encoding='utf-8'))
    if not (isinstance(pin, dict) and isinstance(stamp, dict)):
        raise ValueError('invalid identity')
    version = pin.get('baseVersion')
    commit = pin.get('commit')
    if (not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+', version)
            or not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit)
            or commit == '0' * 40 or stamp.get('baseVersion') != version
            or stamp.get('commit') != commit or stamp.get('distribution') != 'sdkcraft'
            or stamp.get('updateMechanism') != 'external'
            or pin.get('pythonVersion') != platform.python_version()):
        raise ValueError('installed identity differs from SDK pins')
    if launcher is not None:
        result = subprocess.run([launcher, '--version'], check=True, capture_output=True,
                                text=True, timeout=120)
        lines = result.stdout.splitlines()
        if (not any(line.startswith(f'Hermes Agent v{version} (') for line in lines)
                or f'Install directory: {source.resolve()}' not in lines
                or f'Python: {pin["pythonVersion"]}' not in lines):
            raise ValueError('reported CLI identity differs from SDK pins')


if __name__ == '__main__':
    try:
        check(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) == 3 else None)
    except (OSError, ValueError, subprocess.SubprocessError):
        sys.exit('Pinned Hermes SDK identity check failed.')
