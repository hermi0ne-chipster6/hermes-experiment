"""Validate the Workshop profile and migrate the former read-only SDK layout."""

import ast
from collections.abc import Mapping
from contextlib import contextmanager
import fcntl
from io import StringIO
import json
import os
from pathlib import Path
import sys
import tempfile

from ruamel.yaml import YAML, YAMLError


LEGACY_DISABLED = [
    'terminal', 'file', 'browser', 'code_execution', 'computer_use', 'delegation',
    'skills', 'connections', 'kanban', 'catalog', 'project', 'desktop_ui',
]
RETIRED_TRANSFER_PLUGIN = 'hermes_artifacts'
LEGACY_EXTENSIONS = [
    'hermes_diary', 'hermes_notifications', RETIRED_TRANSFER_PLUGIN,
    'mcp-opensandbox', 'mcp-rea', 'mcp-link',
]
LEGACY_TOOLS = ['memory', 'todo', 'session_search', 'cronjob', 'clarify', *LEGACY_EXTENSIONS]
BUNDLED = ('hindsight', 'hermes_otel', 'rea', 'hermes_diary',
           'hermes_notifications')


def yaml_editor():
    # Hermes interprets its profile as YAML 1.1 and rejects duplicate keys.
    editor = YAML()
    editor.version = (1, 1)
    editor.preserve_quotes = True
    editor.width = 2**31 - 1
    return editor


def section(config, key):
    value = config.get(key)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError('expected a mapping')
    return value


def valid_toolset_row(value):
    # Older Hermes config writers stored a Python/JSON array in a YAML string.
    if isinstance(value, str):
        try:
            value = ast.literal_eval(value.strip())
        except (SyntaxError, ValueError):
            return False
        return isinstance(value, list)
    return value is None or isinstance(value, list)


def parse_config(original):
    editor = yaml_editor()
    config = editor.load(original)
    if not isinstance(config, Mapping):
        raise ValueError('expected a profile mapping')
    disabled = section(config, 'agent').get('disabled_toolsets')
    if disabled is not None and not isinstance(disabled, (str, list)):
        raise ValueError('invalid disabled toolsets')
    if not all(valid_toolset_row(value) for value in section(config, 'platform_toolsets').values()):
        raise ValueError('invalid platform toolsets')
    plugins = section(config, 'plugins')
    for key in ('enabled', 'disabled'):
        values = plugins.get(key)
        if values is not None and (not isinstance(values, list)
                                   or not all(isinstance(name, str) for name in values)):
            raise ValueError('invalid plugin names')
    provider = section(config, 'memory').get('provider')
    if provider is not None and not isinstance(provider, str):
        raise ValueError('invalid memory provider')
    if section(config, 'terminal').get('cwd') != '/project':
        raise ValueError('project context is required')
    limit = config.get('context_file_max_chars')
    if limit is not None and (type(limit) is not int or limit < 12000):
        raise ValueError('context cap would truncate the original charter')
    return editor, config


def cron_has_toolset_overrides(home):
    try:
        jobs = json.loads((home / 'cron/jobs.json').read_text(encoding='utf-8-sig'))
    except FileNotFoundError:
        return False
    except (OSError, ValueError):
        return True
    if isinstance(jobs, dict):
        jobs = jobs.get('jobs')
    if isinstance(jobs, dict):
        jobs = list(jobs.values())
    if not isinstance(jobs, list):
        return True
    return any(not isinstance(job, dict) or job.get('enabled_toolsets') is not None for job in jobs)


def remove_legacy_policy(home, config, keep_transfer):
    platforms = section(config, 'platform_toolsets')
    if platforms.get('cli') != LEGACY_TOOLS:
        return False
    agent = section(config, 'agent')
    unattended_is_legacy = all(platforms.get(name) == LEGACY_TOOLS for name in ('buzz', 'email', 'cron'))
    # Replace the CLI element (the legacy sequence can be aliased by other
    # platform rows). Keep global tool controls for edited unattended policies.
    platforms['cli'] = ['hermes-cli', *(name for name in LEGACY_EXTENSIONS
                                       if keep_transfer or name != RETIRED_TRANSFER_PLUGIN)]
    if (agent.get('disabled_toolsets') == LEGACY_DISABLED and unattended_is_legacy
            and not cron_has_toolset_overrides(home)):
        agent['disabled_toolsets'] = []
    return True


@contextmanager
def private_file(destination, content):
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=f'.{destination.name}.',
                                     delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            yield temporary
        finally:
            temporary.unlink(missing_ok=True)


def preserve_original(backup, content):
    # A recovery copy already present is the original record. Never replace it.
    with private_file(backup, content) as temporary:
        try:
            os.link(temporary, backup)
        except FileExistsError:
            if backup.is_symlink() or not backup.is_file():
                raise ValueError('invalid recovery path')


def link_if_missing(path, target):
    try:
        path.symlink_to(target)
    except FileExistsError:
        # Native installs, updates, provisioning, and user-managed links win.
        pass


def prepare_profile(home, source, sdk):
    profile = home / 'config.yaml'
    with (home / '.sdk-profile.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        retired = home / 'plugins' / RETIRED_TRANSFER_PLUGIN
        sdk_transfer = sdk / 'plugins' / RETIRED_TRANSFER_PLUGIN
        managed_transfer = retired.is_symlink() and retired.readlink() == sdk_transfer
        keep_transfer = not managed_transfer and (retired.is_dir() or retired.is_symlink())
        legacy_link = profile.is_symlink()
        if legacy_link and profile.resolve() != source.resolve():
            raise ValueError('unexpected configuration symlink')
        if not legacy_link and profile.exists():
            _, config = parse_config(profile.read_bytes())
        elif source.is_file():
            original = source.read_bytes()
            editor, config = parse_config(original)
            content = original
            if remove_legacy_policy(home, config, keep_transfer):
                preserve_original(home / 'config.yaml.pre-sdk-migration', original)
                output = StringIO()
                editor.dump(config, output)
                content = output.getvalue().encode('utf-8')
            elif legacy_link:
                preserve_original(home / 'config.yaml.pre-sdk-migration', original)
            with private_file(profile, content) as temporary:
                if legacy_link:
                    # The old symlink remains usable up to the atomic handoff.
                    os.replace(temporary, profile)
                else:
                    os.link(temporary, profile)
        elif legacy_link:
            raise ValueError('legacy configuration seed is missing')
        else:
            return  # An operator can provide the charter and configuration after provisioning.

        plugins = section(config, 'plugins')
        enabled = set(plugins.get('enabled') or [])
        disabled = set(plugins.get('disabled') or [])
        provider = section(config, 'memory').get('provider')
        if provider:
            enabled.add(provider.strip())
        plugins_dir = home / 'plugins'
        plugins_dir.mkdir(exist_ok=True)
        # Retire only the former SDK-managed link. Keep an operator-managed
        # plugin of the same name and leave profile configuration untouched.
        if managed_transfer and retired.is_symlink() and retired.readlink() == sdk_transfer and not sdk_transfer.exists():
            retired.unlink(missing_ok=True)
        for name in BUNDLED:
            if name in enabled and name not in disabled:
                target = sdk / 'plugins' / name
                if not target.is_dir():
                    raise ValueError('bundled plugin is missing')
                link_if_missing(plugins_dir / name, target)
        features = sdk / 'share/hermes/enabled-features.json'
        if not features.is_file():
            raise ValueError('packaged dependency feature inventory is missing')
        link_if_missing(home / features.name, features)


def main(arguments):
    setup = arguments[0] == '--setup'
    try:
        if setup:
            prepare_profile(*map(Path, arguments[1:]))
        else:
            parse_config(Path(arguments[0]).read_bytes())
    except (OSError, ValueError, YAMLError):
        detail = 'migration or setup failed' if setup else 'invalid profile'
        print(f'Hermes requires a valid persistent configuration: {detail}.', file=sys.stderr)
        return 78
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
