# NativeAOT validation fixture

The fixture was compiled on the disposable development host using unchanged upstream `scripts/generate-nativeaot-fixtures.mjs` at commit `51459cf203ae1eb6b586a95b21899eaa0f631823`. It uses .NET SDK 8.0.416, runtime 8.0.22, and clang on Linux x64. The SDK is a fixture compiler only and is not a Hermes runtime dependency.

Microsoft's official [8.0 release metadata](https://builds.dotnet.microsoft.com/dotnet/release-metadata/8.0/releases.json) supplied the SDK URL and SHA512. The downloaded archive matched `633cb85673e3519c825532f780f6750ff24ed248ef8df68885540e510b559b6adc2c8d940e4c349fc0cf2c9caf184f1efeaccbc5e952d6e435f3da027cae4188`. The temporary SDK, NuGet cache and intermediate outputs were removed after fixture generation.

Actual generation passed and produced an independent RTR 9.1 directory/symbol oracle. The symbol-bearing executable SHA256 is `f6d7ab48c5df2baf9dc313de4bd0fa842d54a417546a2c09bea1d3c6936761f2`. Generating the fixture does **not** prove that the packaged Ghidra extension runs.

Retained development artifacts:

- `/root/dev/rea-sdk/nativeaot-fixtures.tar.gz`: source-built symbol-bearing and stripped executables, independent `oracle.json`/`symbols.txt`, C# source, and ordinary/unsupported/malformed/ambiguous negative samples.
- `/root/dev/rea-sdk/nativeaot-proof-support.tar.gz`: unchanged pinned upstream verifier, helper modules, TypeScript source required by its resource-lifetime helper, and upstream MIT license.
- `/root/dev/rea-sdk/validation-logs/nativeaot-generate.log`: successful compiler/oracle result.
- `/root/dev/rea-sdk/nativeaot-fixture-toolchain/source.json`: Microsoft download provenance.

Extract those two archives in an owned writable validation directory in the fresh Workshop. `tests/nativeaot-proof.sh SDK_ROOT PROOF_SUPPORT FIXTURE_LINUX_X64 CAPTURE_DIR symbols` links the verifier to the installed package's real dependencies/build and runs upstream's complete positive proof. Run it inside the persistent validation tmux session. The optional final argument selects `stripped`, `ordinary`, `unsupported`, `malformed`, `ambiguous`, `loader-failure` or `default-native`.

The positive proof checks the exact extension JAR digest in producer Evidence, RTR version, nonempty recovered method tables, frozen objects, independently compiled class/interface/virtual-slot addresses, nonempty pseudocode, a source arithmetic witness, frozen strings, and slot bytes. It also checks target hashes and owned-resource cleanup. The negative lanes distinguish format rejection and JVM extension-loading failure from ordinary non-NativeAOT input. Add the resulting captured JSON and real invocation outcome to installed-SDK validation results before marking this extension functional. Optional `REA_NATIVEAOT_PROOF_CLI=1` additionally compares the CLI metadata result; the script does not enable it by default.

## Installed acceptance recipe

Run as the Workshop user in its persistent validation tmux window after the SDK
is Ready. Set `INTEGRATION` to the mounted directory containing the two archives,
and `TESTS` to the mounted SDK `tests` directory. These paths are explicit inputs;
the helper does not download or build a replacement engine. It checks both the
installed upstream commit and the exact independent symbol-fixture SHA256 before
starting a mode. It copies the installed package's complete unchanged
`package.json` into the owned support directory so upstream's `#dist/*` imports
resolve through the installed-build symlink.

```bash
SDK=/var/lib/workshop/sdk/hermes-rea
WORK=/var/lib/hermes-rea/work
PROOF="$WORK/nativeaot-proof-support"
FIXTURES="$WORK/nativeaot-fixtures"
CAPTURE=$(mktemp -d "$WORK/nativeaot-validation.XXXXXX")
mkdir -p "$PROOF" "$FIXTURES"
tar -xzf "$INTEGRATION/nativeaot-proof-support.tar.gz" -C "$PROOF"
tar -xzf "$INTEGRATION/nativeaot-fixtures.tar.gz" -C "$FIXTURES"
printf 'mode\texit\n' > "$CAPTURE/results.tsv"
failed=0
for mode in symbols stripped ordinary unsupported malformed ambiguous loader-failure default-native; do
    if bash "$TESTS/nativeaot-proof.sh" "$SDK" "$PROOF" \
        "$FIXTURES/linux-x64" "$CAPTURE/$mode" "$mode" \
        > "$CAPTURE/$mode.stdout" 2> "$CAPTURE/$mode.stderr"; then
        code=0
    else
        code=$?
        failed=1
    fi
    printf '%s\t%s\n' "$mode" "$code" >> "$CAPTURE/results.tsv"
done
cat "$CAPTURE/results.tsv"
test "$failed" = 0
```

Run modes sequentially because each can start a Ghidra JVM. Keep all stdout,
stderr and `linux-x64-<mode>.json` captures with the summary. Exit zero is valid
only when upstream's final `PASS real Ghidra NativeAOT` line and that mode's JSON
exist; capture files are written after upstream's resource-cleanup assertions.
The negative modes pass by asserting the expected behavior, not by accepting any
nonzero command exit.

| Mode | Required upstream assertion |
| --- | --- |
| `symbols` | Independent NativeAOT type/slot oracle, metadata, frozen strings and arithmetic pseudocode witness |
| `stripped` | The same independent proof without symbol assistance |
| `ordinary` | Extension loaded, `not_applicable`, no recovered method tables |
| `unsupported` | Typed refusal for unsupported RTR format |
| `malformed` | Typed refusal for reversed NativeAOT section |
| `ambiguous` | Typed refusal for ambiguous directory candidates |
| `loader-failure` | Source-built failing Java initializer observed at the real JVM loading boundary |
| `default-native` | Ordinary Ghidra load succeeds without metadata recovery when the extension is explicitly omitted |

The first installed run of all eight modes stopped before provider execution with
`ERR_PACKAGE_IMPORT_NOT_DEFINED` for `#dist/domain/evidenceBundle.js`. The support
archive carried a minimal manifest without upstream's imports map; the helper's
metadata copy corrected that fixture packaging issue without changing REA.
Those failed harness logs remain under `validation-logs/nativeaot-attempt1/`.

## Installed results, 2026-11-17

All eight modes passed sequentially in the installed Linux x64 Workshop, each
with exit 0, its upstream final `PASS` line and a retained JSON capture. The
overall run exited 0. The tested SDK artifact SHA256 was
`77fc26d1660fe359511d41a3cc06c76d6224be8dda9b80367261bed61cad5af3`, before the
subsequent SDK policy rebuild. That rebuild retains the same pinned NativeAOT
extension source and runtime configuration; acceptance of the rebuilt SDK
artifact remains a separate pending step.

The executing verifier matched pinned upstream byte-for-byte, SHA256
`af7a7c230398782761da814241915c897818a3e20deeef1373916b612163a8d8`.
No timeout adapter or semantic assertion change was needed. Positive captures
reported extension JAR SHA256
`8824d01812424d85201557aafcf5f29aa0f2d9b55346340515b8d12a9fd0ecc8`.

| Mode | Result | Observed behavior |
| --- | --- | --- |
| `symbols` | PASS | `complete`, RTR 9.1, symbol discovery, 1,364 method tables and 618/618 frozen-object candidates annotated |
| `stripped` | PASS | `complete`, signature-heuristic discovery, the same 1,364 tables and 618/618 annotated candidates |
| `ordinary` | PASS | Exact extension loaded; `not_applicable`, zero method tables, empty types |
| `unsupported` | PASS | `capability_unavailable` / `unsupported_provider`, explicitly identifying unsupported RTR 99.1 |
| `malformed` | PASS | `execution_failure` with the expected `Reversed NativeAOT section 207` diagnostic; no dedicated malformed-format error code is claimed |
| `ambiguous` | PASS | `capability_unavailable` / `unsupported_provider`, explicitly identifying directory candidates `00402020` and `00402048` |
| `loader-failure` | PASS | `execution_failure` retaining real JVM `ExceptionInInitializerError` caused by `REA_INITIALIZER_FIXTURE` from the deliberately failing test JAR |
| `default-native` | PASS | Ordinary native load-image result with metadata recovery absent when the extension is omitted |

Both positive modes passed the independently compiled derived/base/interface and
virtual-slot address assertions. Both produced the arithmetic witness
`return param_2 * 0xb + 5;`, nonempty dispatch pseudocode, frozen-string matches
and the exact slot-byte read. The stripped fixture SHA256 was
`40f789db121a2dcdfa8defec2afddd19fef545e4008a1a6e8115bb38b3e8321a`; the
symbol-bearing fixture digest is recorded above. All eight passed upstream's
unchanged-input, owned-runtime-directory and process-lineage cleanup assertions.
The optional additional CLI comparison was not enabled.

Evidence is archived at
`/root/dev/rea-sdk/validation-logs/installed-functional/nativeaot-evidence.tar.gz`,
SHA256 `aa51b16ab9530e828f0d77de1293d68b912ea78478b1de2a500a8e095d9829a6`.
It retains the eight captures, logs and exit summaries;
`nativeaot-summary.json` beside it records the tested artifact identity and
rebuilt-artifact acceptance boundary. Original logs are
`validation-logs/nativeaot-installed-<mode>.log`, with
`nativeaot-installed-exits.txt` and `nativeaot-installed.exit`.

`complete` is the extension's status for its reported metadata candidates. It
does not establish original C# source or names, custom field layouts, every
runtime object, or execution behavior. Generated type names and method
prototypes retain upstream's inference limitations. No unexpected engine
failure was observed in these eight fixtures.
