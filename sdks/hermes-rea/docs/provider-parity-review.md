# Provider parity review — 2026-11-17

The SDK preserves the whole pinned REA engine and has substantial real installed-Workshop execution evidence. **Final artifact acceptance is pending.** This review retains checkpoint `af31bf3722ea535609c11893c0ef5d2ef18fb453` evidence and adds fresh policy/HOME-corrected artifact `c7373502e97f32c34be99ba7fd92e7ea5832caf31121aa79a747badd27cf22c5` results. The latter built and installed successfully but exposed a Frida sequencing defect. A corrected official Frida override passes controlled scratch tests; its artifact acceptance remains pending. Supplemental NativeAOT, SSH, refresh and reconstruction results retain their original runtime identities.

## What the evidence establishes

| Claim | Exact evidence and boundary |
| --- | --- |
| Unchanged source identity | `SOURCE.json`, `sdkcraft.yaml` and the installed `full-source` result identify REA `51459cf203ae1eb6b586a95b21899eaa0f631823`, version 6.9.0. This is newer than npm's 6.9.0 release commit. The original SDK repository/Store identity remains `hermes-rea`; its history remains in the repository. |
| Whole source, not only registration | Installed `full-source` checked 14,149 tracked entries and 135,520,255 bytes using SHA256/Git blob hashes, checked executable entries and symlink targets, all six repository inventories, and three derived runtime links. It then invoked the original source CLI and asserted a real JavaScript module/IPC graph. The SDK includes the source tree and archive; `.git` history and development caches are intentionally not runtime contents. |
| Exhaustive source mapping | [Capability map](capability-coverage.json) matches all 78 keys in `src/composition/capabilityDeclarations.ts` and all 48 format IDs in `src/domain/artifactGraph.ts`. Shared workflows, Windows native controls and optional NativeAOT/ILSpy lanes are explicit, not invented capability declarations. Source completeness does not imply exhaustive execution. |
| Catalog equality | `mcp-catalog`, first installed run: all 259 tools match packaged canonical contracts and `binary_session` inventory. This is contract/registration evidence only. |
| Representative execution | The historical 93-case aggregate is retained. Fresh c7373502 has passing observations for all 99 selected individual cases across runs, but the first single-session suite failed after Frida and must not be called passing. Of 78 groups, the reconciled matrix has 71 fully functional at representative scope, three partial (Frida, ADB/device boundary, desktop/model boundary), three untested licensed providers, and one macOS-only group. |
| Native providers | Real Ghidra, Rizin, GDB, Cutter, Kuna, pwntools, Frida injection, JADX, Apktool, WABT, Wakaru, firmware extraction and signal decoding cases have semantic assertions. A Ghidra success is not evidence for another provider. `provider-no-fallback` explicitly refused unavailable selected Ghidra without opening a substitute. |
| Lifecycle and environment | Ghidra snapshot close/reopen passed; same-environment Evidence export/reset/import passed; real browser/Electron/V8, local PTY and desktop capture passed. Exported environment tooling was actually invoked over loopback HTTP MCP. Subsequent supplemental tests proved actual refresh replay and authenticated SSH. Fresh c7373502 also passed real no-model Docker/AgentEnv desktop creation, typing, retained file changes, screenshot decoding and teardown. Corrected-Frida artifact reinstall and external model operations remain pending. |
| Packet fix | Two packet cases initially failed because the selected tshark produced no captured version output. Both passed real DNS packet assertions after a scoped AppArmor fix. That policy is now verified inside c7373502 and passed again in a fresh installation, including enforced allowed-path roundtrip and DAC-writable outside-work denial. Corrected-Frida replacement acceptance remains separate. |
| Official test runner | `sdkcraft test` packed/linted, then exited 1 at VM allocation: absent `/dev/kvm`, 0 successful and 91 aborted tasks. The 93 selected installed functional cases are a separate manual route, not 93 official Spread passes. |

The complete source includes these original submodule revisions:

| Submodule | Commit |
| --- | --- |
| `third_party/binwalk` | `4fdab3d464d97b68e0af9088df3f9e2e1545b21c` |
| `third_party/ghidra-nativeaot` | `effeb734fc570c32650f88b159608979dc7b423e` |
| `third_party/jadx-headless-mcp` | `5844800a486d2248fa949b74c9896285f5b54de2` |
| `third_party/unblob` | `1fcc7a0a584a70a96c31f5a276c20944d199a089` |
| `third_party/wakaru` | `8219bf5016a063d7fb215101a8c45d5959ec733f` |

## Remaining reasons, kept separate

| Category | Remaining scope | Owning source / next evidence |
| --- | --- | --- |
| Upstream Frida subprocess defect; corrected package pending | Original Frida17.23.2 can instrument successfully yet leave later Node children unreaped. Official matched17.25.1 passes the direct regression and mixed REA session in scratch runtime. | [Frida compatibility](frida-compatibility.md): 15 of 37 baseline diagnostic records fail; all 37 candidate records and five mixed-session cases pass. Require corrected SDK build, strict artifact comparison, installed lifecycle regression and full single-session suite. |
| Pending replacement-artifact acceptance | c7373502 clean installation and actual Docker/AgentEnv desktop lifecycle passed. The corrected Frida artifact, complete single-session run and independent fresh reinstall remain outstanding. Eight NativeAOT modes, SSH and refresh passed on the earlier artifact. | Preserve each artifact identity and rerun relevant installed checks; do not transfer live/scratch proofs into final package acceptance. |
| External licensed/provisioned providers | Hopper, IDA and JEB engines/registrations are not supplied or exercised here. | `docs/providers/ida-provider.md`, `docs/providers/jeb-analysis.md`, `src/hopper/`. REA intentionally adapts supplied engines; licensing/activation, GUI/headless mode and supported engine tools remain caller-specific. JEB CE native verification does not establish licensed Android decompilation or `open_project`. |
| External device/process inputs | ADB device operations need a selected attached/emulated Android device. Runtime instrumentation needs an owned accessible process/device; browser/Electron/V8 endpoints and targets must be supplied. | ADB daemon/key-directory initialization and direct/MCP empty-device enumeration passed, including in fresh c7373502; actual device operations remain untested. Browser/Electron/V8 and local Frida targets have representative passes; these do not qualify arbitrary targets, versions, permissions or physical devices. |
| External model/service configuration | Model-driven desktop solve/measure and screen/model workflows need configured model service, credentials and budget. | `docs/desktop-build-computer.md` requires `LITELLM_BASE_URL` / `LITELLM_API_KEY` or the documented model configuration. A model-free lifecycle would not establish solver/model parity. No credentials are bundled or test model replies fabricated. |
| Host OS restriction | macOS native UI/runtime/LLDB; DMG entry reading; Mach-O universal slice reader; Windows x64 native filesystem/Job Object controls. | `src/native/`, `src/artifacts/NativeDmgArtifactReader.ts`, `src/artifacts/MachOSliceArtifactReader.ts`, `src/windows/WindowsNativeLoader.ts`. Static thin Mach-O, PE, LNK, Apple IPS and recorded NTFS analysis remain separate portable lanes. |
| Hardware/host test-runner restriction | Official VM Spread allocation lacks KVM. Physical-device behavior is untested. GPU/model artifact cases inspect static metadata, not inference or GPU execution. | `official-sdkcraft-test.log`; do not relabel aborted jobs as provider failures or modify upstream to bypass platform admission. |
| Upstream operation/admission boundary | `pkg` is recognized without an artifact `createReader`; format/version/architecture admission and provider-specific unsupported operations remain upstream limits. | `src/artifacts/artifactFormats.ts`, provider operation metadata and contract schemas. Complete source/package installation cannot create functionality upstream does not implement. |
| Bounded test coverage | All 48 format IDs are inventoried, but numerous archive/container variants remain unexecuted; full extraction semantics, mutations/xrefs, cancellation/fault/leak paths, general runtime hypotheses and finite reconstruction verification are not exhaustive; the supplemental structural-artifact fixture now verifies all verifier outcomes and residual Unknown propagation. | Matrix per-format table and JSON per-case semantic results. V1/PKCS7 metadata is not trust validation; PTX is not GPU execution; synthetic Flutter/Rust/IL2CPP evidence is not universal decompilation. |

The dependency/runtime reference audit checked 35 references and found only the Windows addon/manifest absent from the Linux runtime. `loadWindowsNativeAuthority` rejects non-Windows-x64 hosts before reading those artifacts. This is consistent with Linux packaging, not evidence that the full upstream source is incomplete. The audit is bounded to its scanned references; it is not a proof that every lazily loaded branch executed.

Kuna is not an unresolved Linux packaging gap: the SDK contains Linux x64 1.990 and the installed `kuna` case explicitly selected it and decompiled the fixture. Upstream's documentation still describes its own qualification as macOS arm64; the two evidence scopes are different. Cutter likewise has a real installed bridge/disassembly result, while its upstream identity limitation is retained.

## Bounded actions for the primary

1. Build the matched official Frida17.25.1 override while preserving the pinned REA source/lock. Verify final artifact contents and installed runtime hashes, then run the full 100-case suite, including the new process-lifecycle regression, in the installed environment. Earlier split passes cannot certify the failed Frida sequence.
2. Perform the independent clean reinstall and final artifact persistence/SSH acceptance. Retain original artifact identities for completed NativeAOT, SSH, refresh, reconstruction, desktop and policy proofs. Keep model-driven solving separate from the successful no-model desktop lifecycle.
3. Preserve the source export and five pinned submodules. Keep optional external providers explicitly unavailable rather than substituting another engine or narrowing the catalog. The new provider correction is justified by reproduced upstream Frida behavior; no REA engine fork is required.
4. Reconcile final reports against saved evidence, including the unavailable KVM test route. No push or publication is authorized by this review.

## Evidence index

All paths below are local development evidence, not shipped runtime paths. The JSON map stores each effective case's source run, archive member, exact semantic result and runtime qualifier. Earlier failed attempts remain in the raw aggregate's `run_history` and original result members.

| Evidence | Path / digest |
| --- | --- |
| Effective aggregate | `/root/dev/rea-sdk/validation-logs/installed-functional/after-policy-results.json` |
| Aggregate summary | `/root/dev/rea-sdk/validation-logs/installed-functional/after-policy-summary.json` |
| First installed runs and retries, raw CLI/MCP outputs/fixtures | `/root/dev/rea-sdk/validation-logs/installed-functional/first-installed-evidence.tar.gz`; SHA256 `ccfa96e601ff0c2a573412659e7b93703bb0de42e3baff198a97c2e6eedd3883` |
| Policy supplement, raw packet results | `/root/dev/rea-sdk/validation-logs/installed-functional/tshark-policy-evidence.tar.gz`; SHA256 `9f61ff31d3a653e6bafe6cc200842ec289164880b990ff65e3ff4d128bfa7c2a` |
| Archive manifests reviewed | `sdk-validation-{first,retry1,retry2,retry3}/results.json` in the first archive; `tshark-policy-acceptance/results.json` in the supplement |
| Source archive roundtrip | `/root/dev/rea-sdk/validation-logs/downloads/source-archive-roundtrip.json`; independent source/export hashes, raw links and modes, not final SDK runtime proof |
| Runtime reference audit | `/root/dev/rea-sdk/validation-logs/runtime-file-audit.json` and `.log` |
| Fresh policy artifact | `/root/dev/rea-sdk/validation-logs/final-artifact.json`, `rebuild-final.log`, `final-preflight.exit`; c7373502 full digest above |
| Failed initial fresh sequence | `/root/dev/rea-sdk/validation-logs/final-initial-run-classification.json`, `frida-sequencing-interruption.json`; 17 passes, one observed SQLite timeout after Frida, 81 aborted |
| Fresh continuation and desktop | `/root/dev/rea-sdk/validation-logs/final-remaining.log` (81/82); `desktop-final2.log` and `.exit` (corrected fixture, real lifecycle pass) |
| Controlled Frida correction | `/root/dev/rea-sdk/validation-logs/frida-direct-baseline.log`, `frida-direct-fixed.log`, `frida-mixed-fixed.log`; scratch candidate scope only |
| Official runner | `/root/dev/rea-sdk/validation-logs/official-sdkcraft-test.log` and `.exit` |
| Upstream source owners | `/root/dev/rea-sdk/upstream-rea/src/composition/capabilityDeclarations.ts`, `src/contracts/toolContracts.ts`, `src/domain/artifactGraph.ts`, `src/artifacts/artifactFormats.ts` at the commit above |

This review changed only coverage documentation. It did not operate shared containers, alter upstream, rebuild dependencies or publish artifacts.
