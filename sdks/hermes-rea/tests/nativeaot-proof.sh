#!/bin/bash
# Run the unchanged pinned upstream verifier against an installed SDK.
# Arguments: SDK_ROOT EXTRACTED_PROOF_SUPPORT FIXTURE_LINUX_X64 CAPTURE_DIR [MODE]
set -euo pipefail
if [[ $# -lt 4 || $# -gt 5 ]]; then
    echo 'Usage: nativeaot-proof.sh SDK_ROOT PROOF_SUPPORT FIXTURE_LINUX_X64 CAPTURE_DIR [symbols|stripped|ordinary|unsupported|malformed|ambiguous|loader-failure|default-native]' >&2
    exit 2
fi
sdk_dir=$(readlink -f "$1")
proof_dir=$(readlink -f "$2")
fixture_dir=$(readlink -f "$3")
capture_dir=$(realpath -m "$4")
mode=${5:-symbols}
case "$mode" in
    symbols|stripped|ordinary|unsupported|malformed|ambiguous|loader-failure|default-native) ;;
    *) echo "Unknown NativeAOT proof mode: $mode" >&2; exit 2 ;;
esac
package_root="$sdk_dir/rea/node_modules/rea-agents"
test "$(cat "$sdk_dir/rea/UPSTREAM_COMMIT")" = 51459cf203ae1eb6b586a95b21899eaa0f631823
test -r "$proof_dir/scripts/verify-real-ghidra-nativeaot.mjs"
test -r "$fixture_dir/oracle.json"
# Refuse a substituted sample before linking support files or starting REA.
test "$(sha256sum "$fixture_dir/symbols/NativeAotFixture" | cut -d ' ' -f 1)" = f6d7ab48c5df2baf9dc313de4bd0fa842d54a417546a2c09bea1d3c6936761f2
# The support archive's minimal manifest lacks upstream's #dist imports map.
# Copy the complete pinned installed metadata, leaving verifier/engine unchanged.
cp "$package_root/package.json" "$proof_dir/package.json"
for entry in node_modules dist; do
    if [[ "$entry" = node_modules ]]; then
        target="$sdk_dir/rea/node_modules"
    else
        target="$package_root/dist"
    fi
    if [[ -e "$proof_dir/$entry" || -L "$proof_dir/$entry" ]]; then
        test "$(readlink -f "$proof_dir/$entry")" = "$target"
    else
        ln -s "$target" "$proof_dir/$entry"
    fi
done
# shellcheck source=/dev/null
source "$sdk_dir/wrappers/rea-environment"
export REA_NATIVEAOT_PROOF_PACKAGE_ROOT="$package_root"
export REA_NATIVEAOT_PROOF_FIXTURE_ROOT="$fixture_dir"
export REA_NATIVEAOT_PROOF_CAPTURE_DIR="$capture_dir"
exec "$sdk_dir/node/bin/node" "$proof_dir/scripts/verify-real-ghidra-nativeaot.mjs" "$mode"
