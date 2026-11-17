# Verified reuse of unchanged SDK build products

The full `sdkcraft.yaml` remains the normal cold-build recipe. A separately
retained temporary recipe may reuse the immutable build products from the prior
SDK while replacing the complete Frida package and matching native addon. This
is composition from prebuilt parts, supported by [Canonical SDK
parts](https://ubuntu.com/workshop/docs/explanation/sdks/parts.md) and the
[Craft Parts dump plugin](https://documentation.ubuntu.com/craft-parts/latest/common/craft-parts/reference/plugins/dump_plugin/).
It is not a first-class SDKcraft cache feature. Retain the temporary recipe,
its inputs, tool versions, build logs, and the comparison report alongside the
final artifact. The full recipe must encode the same Frida override.

The permitted base artifact has SHA256:

```text
c7373502e97f32c34be99ba7fd92e7ea5832caf31121aa79a747badd27cf22c5
```

The base is evidence of completed packaging and previously exercised unchanged
components; it is not proof that the final replacement passes acceptance. The
REA engine and original lock remain unchanged at upstream commit
`51459cf203ae1eb6b586a95b21899eaa0f631823` (6.9.0). The Frida compatibility
override is disclosed separately by `dependencies/frida-compatibility.json`.

## Inputs and archive comparison

Run the comparator on the host with Python 3.11+, PyYAML, and `zstd`. It never
extracts either SDK and never follows archive links. It streams decompressed
tar contents while retaining only inventories and small metadata/hook files in
memory. Supply the SDK source directory containing `hooks/` and `dependencies/`,
not the repository root. The report's parent directory must already exist.

```sh
python3 tests/compare-sdk-artifacts.py \
  /path/to/preserved-base.sdk /path/to/candidate.sdk \
  --sdk-source /path/to/sdks/hermes-rea \
  --frida-npm /path/to/frida-17.25.1.tgz \
  --frida-native /path/to/frida-v17.25.1-napi-v8-linux-x64.tar.gz \
  --report /path/to/evidence/sdk-artifact-comparison.json
```

The comparator embeds and checks the base SHA256 and both official input
SHA256 values before accepting any payload comparison:

| Official input | SHA256 |
| --- | --- |
| [Frida 17.25.1 npm tarball](https://registry.npmjs.org/frida/-/frida-17.25.1.tgz) | `81c475d3425a3748007efdc80ebd2c747a44694627e2aab11999675536f9ec04` |
| [Matching Linux x64 Node-API 8 native archive](https://github.com/frida/frida/releases/download/17.25.1/frida-v17.25.1-napi-v8-linux-x64.tar.gz) | `28f6bf3a8926288ffe79f415777256a37213c2d217cdab4ee81b225b096854bb` |

The JSON report records base and candidate hashes, input paths and sizes, the
full inventories, the expected Frida inventory, every changed path, and explicit
errors. Exit zero requires all checks to pass. Input, decoding, or comparison
failures return nonzero and are recorded when the report path is writable.

Each inventory records member type, SHA256 for regular files, mode, uid/gid,
size, literal symlink/hardlink target, device numbers, and extended PAX fields
including capabilities, ACLs, and xattrs. Duplicate or unsafe member paths fail.
Archive timestamps and textual owner names are intentionally excluded; numeric
ownership is checked. No missing or extra path is silently ignored.

Only these differences are accepted:

1. `rea/node_modules/frida/` must exactly match all 365 published npm files,
   plus `build/frida_binding.node` from the verified native archive and
   `hermes-rea-compatibility.json` byte-for-byte from the current SDK source.
   Published npm file modes are preserved. The binding is installed 0644 by both
   SDK recipes (`install -D -m644`), an explicit transformation of the official
   archive's 0755 shared-library mode; its bytes remain exact. Compatibility JSON
   is 0644, inferred directories 0755, and ownership is root:root. Unexpected
   Frida files, missing files, differing bytes, modes, owners, or xattrs fail.
2. `meta/sdk.yaml` may change serialization and its generated
   `sdkcraft-started-at` field only. Both timestamp values must be strings in
   canonical ISO 8601 UTC (`+00:00`) form; the candidate must not predate the
   immutable base or lie in the future. Both values are retained in the report.
   The entire remaining parsed dictionary must equal the base, including
   identity, base, version, architecture and interfaces. Missing timestamps,
   duplicate YAML keys and any other changed metadata fail. Other archive
   attributes remain unchanged.
3. Existing `sdk/hooks/*` files must have the same filenames as the base and
   current source, and exactly match source bytes and executable modes.
   Ownership, type and extended attributes remain unchanged.

All other paths, including original upstream source, lockfiles, provider
binaries, metadata files and the preserved source archive, must remain equal.
The malformed upstream symlink fixtures are compared as literal links.

## Build and acceptance boundaries

The temporary recipe must exclude the unpacked `upstream/rea` tree before
Craft's stage scan, then restore the unchanged checksum-verified source archive
during prime. Remove old generated metadata and hooks before SDKcraft generates
their replacements. Use explicit extraction for a plain `.sdk` input; default
dump behavior would copy that input file into the SDK. Preserve the base archive
unchanged, including where registrations share its inode through hard links.

This comparison establishes artifact equivalence within the stated change
boundary; it does not substitute for a fresh installation, readiness checks,
runtime policy proof, desktop acceptance, or the direct Frida sentinel and
mixed-provider MCP regressions. Record those results against the candidate
SHA256 reported by the comparator. Do not describe old-artifact test results as
new-artifact execution. Compilation is avoided, but Craft's expanded lifecycle
copies still require sufficient disk space.

For bounded local verification of the comparator itself:

```sh
python3 tests/compare-sdk-artifacts.py --self-test
```

These synthetic tests cover strict bidirectional changes, attributes, hashes,
malformed links without dereferencing, duplicate/unsafe names, exact Frida
inventory enforcement, semantic metadata changes, generated timestamp validation, duplicate YAML keys,
and source hook bytes/modes. They do not claim that any candidate SDK has passed.

## Independent recipe review

On 2026-11-17, the generated `frida-rebuild-project/sdkcraft.yaml` was compared
with the current full source recipe. Their complete metadata mappings outside
`parts` were equal, including SDK name, base, platforms, adoption of the REA
version and both mount interfaces. The `frida-runtime` and `frida-native` part
mappings were exactly equal. All three current executable hook files matched
by bytes and modes. The generated base part verifies the immutable artifact
checksum before explicit extraction, excludes the old Frida package and
SDKcraft-generated metadata/hooks, and restores the checksum-verified complete
upstream source during prime. The full source recipe removes its original
installed Frida package before staging the same complete matched replacement;
the engine and original lock remain retained.

The comparator was independently rerun under tmux: all ten focused tests passed
(`validation-logs/agent-c-comparator-recheck.log`, exit zero). Review found no
additional comparator or recipe defect requiring a change. This is source and
self-test evidence only: no final candidate archive had yet been supplied to
the comparator at this review. Archive equality, final build, fresh install,
and the required runtime regressions remain separate acceptance gates. Parent
coordination must also confirm adequate storage for the expanded Craft stages.

## Generated packaging timestamp correction

A follow-up review of installed official SDKcraft 0.9.4 found a required narrow
exception to full metadata equality. Its
`lib/python3.12/site-packages/sdkcraft/services/package.py` initializes
`PackageService._started_at` from `datetime.now(UTC)` when no timestamp is
supplied, emits it as `sdkcraft_started_at` in the metadata model, and formats it
with `dt.astimezone(UTC).isoformat()`. Therefore a later legitimate SDKcraft pack
naturally changes `sdkcraft-started-at` without changing SDK configuration.

The retained c737 artifact metadata in
`validation-logs/policy-artifact-content/meta/sdk.yaml` records
`2026-11-17T19:10:58.918254+00:00`. The earlier retained artifact metadata in
`validation-logs/final-artifact-content/meta/sdk.yaml` records
`2026-11-17T16:43:20.389218+00:00`; those values identify different packaging
runs and must not be conflated when inspecting installed cache volumes.

The comparator now validates and reports just this generated timestamp
exception, while continuing to compare every other metadata field exactly.
All eleven focused tests passed under tmux
(`validation-logs/agent-c-comparator-timestamp.log`, exit zero), including
missing, malformed, non-string, non-UTC, naive, backwards and future timestamp
refusals, plus simultaneous identity/extra-field changes. No build timestamp
was edited in an SDK artifact to make the comparison pass.

## First candidate rejected: root exclusion correction

The first reuse build completed SDKcraft packaging, but strict comparison
rejected artifact SHA256
`86deb4c23369a234fd65c08ba5097f0457181c5d37f992ed5e24f77632e774b6`
before registration or installation. Evidence, the rejected artifact and the
complete comparison inventory are retained under
`validation-logs/frida-rebuild-attempt1/`. `frida-rebuild.exit` is zero;
`sdk-artifact-comparison.exit` and the dependent acceptance exits are one.
`rejection.json` records the exact artifact and the no-installation boundary.

The comparator reported 32 removed paths outside the permitted Frida change:
AJV's nested JSON-schema `meta` directories and schema files, plus Zig's
`lib/std/meta` directory and `trailer_flags.zig`. GNU tar's unanchored
`--exclude=meta` matched these nested directories while trying to remove only
SDKcraft's root metadata. This was a packaging-reuse defect, not an upstream
REA defect or a permissible archive difference. The comparator correctly
rejected the omissions; its acceptance rules were not relaxed.

Both the primary context generator and generated SDKcraft recipe now put
`--anchored` before the explicit exclusions, limiting them to the archive root.
A focused synthetic archive regression exercises the actual GNU tar behavior:
the old unanchored extraction loses nested AJV/Zig metadata and is rejected by
the unchanged comparator; anchored extraction removes root metadata while
preserving both nested files exactly. All twelve comparator self-tests passed
under tmux (`validation-logs/agent-c-comparator-anchored.log`, exit zero).

The second official rebuild and its complete artifact comparison remain
pending at this review. Correct flags and a small regression fixture do not
replace that real archive comparison, nor any fresh installed-runtime test.
