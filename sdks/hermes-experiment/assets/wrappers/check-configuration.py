"""Reject a missing or permissive operator configuration before Hermes starts.

PyYAML is already a pinned Hermes dependency. Ownership/path checks belong to
the shell wrapper; this check validates the native execution policy contents.
"""

import json
import sys

DISABLED = {'terminal', 'file', 'browser', 'code_execution', 'computer_use', 'delegation',
            'skills', 'connections', 'kanban', 'catalog', 'project', 'desktop_ui'}
ALLOWED = {'memory', 'todo', 'session_search', 'cronjob', 'clarify', 'hermes_diary',
           'hermes_notifications', 'hermes_artifacts', 'mcp-opensandbox', 'mcp-rea', 'mcp-link'}


def main(path):
    try:
        with open(path) as stream:
            text = stream.read()
        try:
            config = json.loads(text)
        except json.JSONDecodeError:
            import yaml
            try:
                config = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                raise ValueError('invalid operator YAML') from exc
        disabled = config['agent']['disabled_toolsets']
        if not isinstance(disabled, list) or not DISABLED <= set(disabled):
            raise ValueError('missing execution restrictions')
        platforms = config['platform_toolsets']
        for platform in ('cli', 'buzz', 'email', 'cron'):
            tools = platforms[platform]
            if not isinstance(tools, list) or not set(tools) <= ALLOWED:
                raise ValueError('unsupported platform toolset')
        if config.get('terminal', {}).get('cwd') != '/project':
            raise ValueError('project context is required')
        limit = config.get('context_file_max_chars')
        if limit is not None and (type(limit) is not int or limit < 12000):
            raise ValueError('context cap would truncate the original charter')
    except (OSError, ValueError, TypeError, KeyError):
        print('Hermes requires the reviewed restrictive operator configuration; refusing local fallback.', file=sys.stderr)
        return 78
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
