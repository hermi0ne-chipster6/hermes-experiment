#!/bin/bash
# Upstream REA rejects other pyelftools/Unicorn versions, including base apt versions.
set -euo pipefail
target="$CRAFT_PART_INSTALL/providers/pwntools-venv"
/usr/bin/python3 -m venv --without-pip "$target"
/usr/bin/python3 -m pip --python "$target/bin/python" install \
    --disable-pip-version-check --only-binary=:all: --require-hashes \
    -r "$CRAFT_PROJECT_DIR/dependencies/pwntools-build-requirements.txt"
# Unicorn 2.1.2 has no CPython3.14 wheel: build its unchanged pinned sdist.
export THREADS="${PWNTOOLS_BUILD_JOBS:-2}"
/usr/bin/python3 -m pip --python "$target/bin/python" install \
    --disable-pip-version-check --require-hashes --no-build-isolation \
    --only-binary=:all: --no-binary=unicorn \
    -r "$CRAFT_PROJECT_DIR/dependencies/pwntools-requirements.txt"
# Keep generated console scripts usable after SDK relocation; preserve their bodies.
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
mkdir -p "$CRAFT_PART_INSTALL/providers/licenses/pwntools"
cp "$CRAFT_PROJECT_DIR/dependencies/pwntools-requirements.txt" \
    "$CRAFT_PART_INSTALL/providers/licenses/pwntools/requirements.txt"
"$target/bin/python" -I - <<'PY'
from importlib.metadata import version
for package, expected in {"pwntools": "4.15.0", "pyelftools": "0.33", "unicorn": "2.1.2"}.items():
    assert version(package) == expected, (package, version(package), expected)
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
from unicorn.x86_const import UC_X86_REG_RAX
engine = Uc(UC_ARCH_X86, UC_MODE_64)
engine.mem_map(0x1000, 0x1000)
engine.mem_write(0x1000, b"\x48\xc7\xc0\x2a\x00\x00\x00")
engine.emu_start(0x1000, 0x1007)
assert engine.reg_read(UC_X86_REG_RAX) == 42
print("Exact pwntools profile and real Unicorn x86-64 emulation passed")
PY
