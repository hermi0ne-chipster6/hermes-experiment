#!/bin/bash
# SDKcraft git-source part, source-commit 55596aa676a2756efb8d67034f31675170eabe48.
set -euo pipefail
cd "$CRAFT_PART_SRC"
test "$(git rev-parse HEAD)" = 55596aa676a2756efb8d67034f31675170eabe48
/usr/bin/python3 -m venv "$CRAFT_PART_BUILD/uv-tool"
"$CRAFT_PART_BUILD/uv-tool/bin/python" -m pip install \
    --disable-pip-version-check --only-binary=:all: --require-hashes \
    -r "$CRAFT_PROJECT_DIR/dependencies/uv-requirements.txt"
uv_command="$CRAFT_PART_BUILD/uv-tool/bin/uv"
export UV_PROJECT_ENVIRONMENT="$CRAFT_PART_INSTALL/providers/pwndbg-venv"
export UV_LINK_MODE=copy
export UV_CONCURRENT_BUILDS=1
"$uv_command" venv --relocatable --python /usr/bin/python3 --no-managed-python \
    "$UV_PROJECT_ENVIRONMENT"
"$uv_command" sync --project "$CRAFT_PART_SRC" --frozen --no-editable \
    --no-default-groups --python /usr/bin/python3 --no-managed-python
test -r "$UV_PROJECT_ENVIRONMENT/share/pwndbg/gdbinit.py"
install -Dm644 LICENSE.md "$CRAFT_PART_INSTALL/providers/licenses/pwndbg/LICENSE.md"
install -Dm644 uv.lock "$CRAFT_PART_INSTALL/providers/licenses/pwndbg/uv.lock"
"$UV_PROJECT_ENVIRONMENT/bin/python" -c \
    'from importlib.metadata import version; assert version("pwndbg") in ("2026.9.15", "2026.09.15")'
