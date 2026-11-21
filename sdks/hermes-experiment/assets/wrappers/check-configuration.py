"""Reject a missing or permissive operator configuration before Hermes starts.

PyYAML is already a pinned Hermes dependency. Ownership/path checks belong to
the shell wrapper; this check validates the native execution policy contents.
"""

import json
import sys



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
        if not isinstance(config, dict):
            raise ValueError('configuration must be a mapping')
        if not isinstance(config.get('agent', {}).get('disabled_toolsets', []), list):
            raise ValueError('invalid disabled toolsets')
        if config.get('terminal', {}).get('cwd') != '/project':
            raise ValueError('project context is required')
        limit = config.get('context_file_max_chars')
        if limit is not None and (type(limit) is not int or limit < 12000):
            raise ValueError('context cap would truncate the original charter')
    except (OSError, ValueError, TypeError, KeyError):
        print('Hermes requires the valid persistent configuration; refusing invalid configuration.', file=sys.stderr)
        return 78
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
