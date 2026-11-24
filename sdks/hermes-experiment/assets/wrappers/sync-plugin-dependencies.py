"""Reconcile a committed native plugin dependency generation with this SDK."""

from pathlib import Path
import sys


def sync(project):
    from pm.environments import committed_venv
    from pm.install import venv_is_current

    # A fresh SDK uses its frozen environment. A committed generation must
    # match the active core locks, interpreter pin, and selected plugin inputs.
    # The direct upstream probe is read-only and never provisions a PM worker.
    if committed_venv(project) is None or venv_is_current(project_root=project):
        return

    from pm import sync_venv

    # Keep plugin sources, enabled state and the previous dependency selection
    # intact on failure. Native PM stages and publishes the dependency graph.
    print('Revalidating persistent Hermes plugin dependencies for this SDK.', file=sys.stderr)
    sync_venv(explicit=True)
    if not venv_is_current(project_root=project):
        raise RuntimeError('Hermes PM did not select the expected dependency generation')


if __name__ == '__main__':
    try:
        sync(Path(sys.argv[1]))
    except (OSError, RuntimeError, ValueError):
        sys.exit('Persistent Hermes plugin dependencies could not be reconciled with this SDK.')
