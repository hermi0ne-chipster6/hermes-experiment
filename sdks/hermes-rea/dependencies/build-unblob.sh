#!/bin/bash
# SDKcraft override-build helper; Python ABI matches ubuntu@26.04 (CPython 3.14).
set -euo pipefail
/usr/bin/python3 -c 'import sys; assert sys.version_info[:2] == (3, 14), sys.version'
/usr/bin/python3 -m pip install --disable-pip-version-check --no-compile \
    --only-binary=:all: --require-hashes \
    --target "$CRAFT_PART_INSTALL/providers/unblob" \
    -r "$CRAFT_PROJECT_DIR/dependencies/unblob-requirements.txt"
PYTHONPATH="$CRAFT_PART_INSTALL/providers/unblob" \
    /usr/bin/python3 -m unblob.cli --version | grep -Fx '26.6.4'
# Keep extractor entrypoints (jefferson, ubireader_*, ...). Their generated
# shebangs refer to the build interpreter; invoke them through the runtime
# interpreter and scope PYTHONPATH to this provider's private dependency tree.
mkdir -p "$CRAFT_PART_INSTALL/providers/bin"
for entrypoint in "$CRAFT_PART_INSTALL/providers/unblob/bin/"*; do
    [[ -f "$entrypoint" ]] || continue
    name=$(basename "$entrypoint")
    [[ "$name" =~ ^[A-Za-z0-9_.-]+$ ]] || exit 1
    # The unblob launcher is owned by assets/wrappers and uses -m unblob.cli.
    [[ "$name" != unblob ]] || continue
    cat > "$CRAFT_PART_INSTALL/providers/bin/$name" <<EOF
#!/bin/bash
set -euo pipefail
sdk_dir=\$(dirname "\$(dirname "\$(dirname "\$(readlink -f "\$0")")")")
export PYTHONPATH="\$sdk_dir/providers/unblob"
exec /usr/bin/python3 "\$sdk_dir/providers/unblob/bin/$name" "\$@"
EOF
    chmod 755 "$CRAFT_PART_INSTALL/providers/bin/$name"
done
