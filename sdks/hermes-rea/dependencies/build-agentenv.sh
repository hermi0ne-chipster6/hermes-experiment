#!/bin/bash
# Client library only: no Docker daemon, model endpoint or remote configuration.
set -euo pipefail
target="$CRAFT_PART_INSTALL/providers/agentenv-venv"
/usr/bin/python3 -m venv --without-pip "$target"
/usr/bin/python3 -m pip --python "$target/bin/python" install \
    --disable-pip-version-check --only-binary=:all: --require-hashes \
    -r "$CRAFT_PROJECT_DIR/dependencies/agentenv-requirements.txt"
/usr/bin/python3 - "$target" <<'PY'
import pathlib
import shlex
import sys

root = pathlib.Path(sys.argv[1])
for executable in (root / "bin").iterdir():
    if executable.is_symlink() or not executable.is_file():
        continue
    data = executable.read_bytes()
    if not data.startswith(("#!" + str(root) + "/bin/python").encode()):
        continue
    script = root / "libexec" / (executable.name + ".py")
    script.parent.mkdir(exist_ok=True)
    script.write_bytes(data)
    executable.write_text('#!/bin/sh\n'
                          'venv_dir=$(dirname "$(dirname "$(readlink -f "$0")")")\n'
                          'exec "$venv_dir/bin/python" -P "$venv_dir/libexec/"'
                          + shlex.quote(script.name) + ' "$@"\n')
    executable.chmod(0o755)
PY
mkdir -p "$CRAFT_PART_INSTALL/providers/bin" "$CRAFT_PART_INSTALL/providers/licenses/agentenv"
ln -sfn ../agentenv-venv/bin/agent-env "$CRAFT_PART_INSTALL/providers/bin/agent-env"
cp "$CRAFT_PROJECT_DIR/dependencies/agentenv-requirements.txt" \
    "$CRAFT_PART_INSTALL/providers/licenses/agentenv/requirements.txt"
chmod -R a+rX "$target"
"$target/bin/python" -I -c 'from importlib.metadata import version; import agent_env, agentenv_protocol; assert version("agentenv-framework") == "0.9.1485"; assert version("agentenv-framework-protocol") == "0.1.500"'
"$target/bin/agent-env" --version
