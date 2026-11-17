# Hermes REA capability audit

The [edge capability matrix](edge-capability-matrix.md) records execution for Store revision 2. This audit retains the source and format inventory and the historical build observations.

This combines a **source-derived audit and recorded representative installed-Workshop results**, not a claim that every operation was executed. The baseline column describes the preserved original SDK source at `df4d649` (Store revision 1, REA 6.7.0). The validation column is reconciled against the 2026-11-17 saved results; this column describes earlier runs before revision 2 acceptance. Availability probes, installed files, and `tools/list` do not establish functional support.

## Exact comparison baseline

- SDK repository: `hermi0ne-chipster6/hermes-experiment`, original commit `df4d649`; package identity `hermes-rea`, Ubuntu 26.04 amd64.
- Current upstream source: [`morluto/rea@51459cf203ae1eb6b586a95b21899eaa0f631823`](https://github.com/morluto/rea/blob/51459cf203ae1eb6b586a95b21899eaa0f631823/), package metadata version 6.9.0, fetched 2026-11-17.
- Published npm `rea-agents@6.9.0`: tag `rea-agents-6.9.0`, commit `d74549e495c58eb4a560279fd9f05508401ea0a0`; integrity `sha512-KqDn1UR5BMqHoQ3MGAnPuWiSKwgdFaz1L/uUNgrKt+1W8kPtgYP8AWEOXIF1lDIOBVyPuYIIst2iamo1Wf3r8g==`.
- Main and npm have the same version string but different source. Main adds at least `inspect_dwarf_units`, `inspect_elf_dependencies`, `inspect_elf_debug_link`, and `inspect_nuget_nupkg`, plus Android boot/OTA support under existing artifact operations. It also changes schemas and bridges. Packaging npm 6.9.0 alone is not parity with this main baseline.
- Source inventory owner: [`src/composition/capabilityDeclarations.ts`](https://github.com/morluto/rea/blob/51459cf203ae1eb6b586a95b21899eaa0f631823/src/composition/capabilityDeclarations.ts); public contract owner: [`src/contracts/toolContracts.ts`](https://github.com/morluto/rea/blob/51459cf203ae1eb6b586a95b21899eaa0f631823/src/contracts/toolContracts.ts). The table below covers **all 78 declared capability keys**, including entries without provider identities. Additional shared contracts follow it.

## Status rules

**Fully functional** means only the mapped representative operations passed in the development installed Workshop with recorded semantic assertions. It never means every input or upstream operation was exhaustively tested. **Partially functional** means named operations passed while other required operations remain unavailable or untested. **Missing** means a packaging/runtime prerequisite or source feature is absent. **Unsupported on target platform** requires an actual platform restriction. **Not yet tested** makes no execution claim. Missing dependency, packaging defect, unconfigured external provider, incompatible platform, and upstream limitation are separate causes.

## Recorded execution boundary

The historical aggregate contains 93 passing selected cases across runs. The newer policy/HOME-corrected SDK `c7373502e97f32c34be99ba7fd92e7ea5832caf31121aa79a747badd27cf22c5` built and installed successfully in a fresh Workshop. Its initial suite passed 17 cases, then exposed a real Frida 17.23.2 child-process sequencing failure; 81 later cases were aborted. A separate MCP process passed 81 of 82 remaining cases, and a corrected desktop test decoder subsequently passed the last case. Thus all 99 individual cases have passing observations across runs, **not a successful single-session suite**.

The official matched Frida 17.25.1 scratch override passes 37 direct lifecycle records and a five-case JavaScript → Frida → SQLite → Ghidra sequence. Its rebuilt SDK and independent clean reinstall remain pending. The matrix therefore keeps Frida **Partially functional** rather than allowing isolated injection passes to hide the sequence defect. The current representative counts are 71 fully functional, three partially functional (Frida, desktop build/model boundary, ADB/device boundary), three untested external licensed providers, and one unsupported macOS group.

Each row's test IDs, semantic results and artifact qualifiers are in [capability-coverage.json](capability-coverage.json). Raw historical results and failures remain retained. Eight NativeAOT modes, actual refresh replay and live SSH checks passed on the earlier installed artifact; they do not certify the replacement artifact. Catalog equality (259 tools) proves registration only. See [provider parity review](provider-parity-review.md) and [Frida compatibility](frida-compatibility.md).

## Declared capability matrix

| Upstream capability key | Operations and scope | Runtime dependency / configuration | Original SDK assessment | Validation status |
| --- | --- | --- | --- | --- |
| `adbDevice` | Android device inspection, shell/package observations | ADB executable; selected attached/emulated device; REA_ADB_PATH | ADB daemon and direct/MCP enumeration passed; device operations need attached/emulated device | Partially functional |
| `analysisView` | Retained Evidence views, filtering and paging | Built-in Node runtime | Not yet tested | Fully functional — representative `analysis-view` |
| `android` | APK classes, methods, resources and Android analysis | jadx-headless-mcp 0.7.1 JAR; full JDK; REA_JADX_MCP_JAR | Missing dependency | Fully functional — representative `android` |
| `androidApplicationGraph` | Android application/component/native dependency graph | Built-in parsers; deeper class facts need JADX | Not yet tested | Fully functional — representative `android-graph` |
| `apkSignature` | APK signing-block inspection | Built-in parser; no trust or signer authenticity inference | Not yet tested | Fully functional — representative `apk-signature` |
| `apktool` | Decoded Android resource inspection | Apktool >=2.7.0 and Java; REA_APKTOOL_COMMAND | Missing dependency | Fully functional — representative `apktool` |
| `appleApplicationGraph` | Apple application graph | Built-in archive/Mach-O/plist inspection; no macOS execution implied | Not yet tested | Fully functional — representative `apple-graph` |
| `appleIps` | Recorded Apple IPS crashes | Built-in parser; supplied crash file | Not yet tested | Fully functional — representative `apple-ips` |
| `applicationWorkflows` | Application comparison, semantic tracing, guidance and reconstruction coverage | Built-in workflows plus source Evidence/providers selected by task | Not yet tested | Fully functional — representative `application-comparison` |
| `artifactGraph` | Artifact inventory, extraction and comparison | Built-in format readers; selected compression/extractor boundaries apply | Not yet tested | Fully functional — representative `archive`, `apple-graph`, `harmony-graph`, `android-graph` |
| `artifactResources` | Owned input/output resources and cleanup | Built-in resource lifetime management; filesystem permissions | Not yet tested | Fully functional — representative `archive`, `artifact-resources` |
| `binaryLayout` | ELF/PE/Mach-O layout through pwntools | Python3 + pwntools; REA_PWNTOOLS_PYTHON | Not yet tested | Fully functional — representative `binary-layout` |
| `browserObservation` | Browser targets, pages, DOM and network observations | Reachable caller-selected local CDP browser endpoint | Unconfigured external provider | Fully functional — representative `browser` |
| `browserScenarioCapture` | Browser scenario execution and capture | playwright-core dependency plus compatible browser executable/runtime libraries | Missing dependency / unconfigured external browser | Fully functional — representative `browser-scenario` |
| `byteEntropy` | Byte-range entropy | Built-in parser | Not yet tested | Fully functional — representative `entropy` |
| `cutter` | Cutter disassembly/decompilation/analysis bridge | Packaged Linux Cutter 2.5.0 AppImage, Python bridge, Qt/X11 runtime; owned GUI session (Xvfb supported) | Missing dependency | Fully functional — representative `cutter` |
| `desktopApplication` | Desktop application analysis/export/capture workflows | Static workflows built in; runtime capture requires external app/display and AgentEnv paths | Partially functional candidate; not yet tested | Fully functional — representative `desktop-application`, `desktop-capture` |
| `desktopBuildComputers` | Owned desktop build computers, actions, capture and export | Docker engine/CLI; agentenv-framework 0.9.1485; packed REA runtime archive | Missing dependency / unconfigured external execution environment | Partially functional — real model-free `desktop-build`, clients and runtime packing passed; external model-driven operations remain unconfigured |
| `devicetree` | Flattened Device Tree inspection | Built-in FDT reader | Not yet tested | Fully functional — representative `devicetree` |
| `dwarfUnits` | DWARF compilation/type unit inspection | Built-in DWARF reader; new after npm 6.9.0 tag | Missing in release baseline | Fully functional — representative `dwarf` |
| `electronActiveObservation` | Active Electron scenario capture | Caller-supplied Electron executable/app; Playwright; runtime libraries/display | Unconfigured external provider | Fully functional — representative `electron-active` |
| `electronFuses` | Electron fuse configuration inspection | Built-in static binary reader | Not yet tested | Fully functional — representative `electron-fuses` |
| `electronObservation` | Passive Electron targets and page inspection | Local Electron CDP endpoint | Unconfigured external provider | Fully functional — representative `electron-passive` |
| `elfDependencies` | ELF dependency/version requirements and caller-selected resolution | Built-in reader; new after npm 6.9.0 tag | Missing in release baseline | Fully functional — representative `elf-dependencies` |
| `elfNotes` | ELF notes and build identifiers | Built-in parser | Not yet tested | Fully functional — representative `elf-notes` |
| `elfDebugLink` | ELF debug-link and selected debug companion inspection | Built-in reader; new after npm 6.9.0 tag | Missing in release baseline | Fully functional — representative `elf-debug-link` |
| `nativeInitializers` | Native initializer inventories | Built-in native format parsers | Not yet tested | Fully functional — representative `native-initializers` |
| `elfUnwindRanges` | ELF unwind ranges | Built-in parser | Not yet tested | Fully functional — representative `elf-unwind` |
| `erlangBeam` | Erlang BEAM metadata/instructions | Built-in BEAM parser; no Erlang runtime required for static inspection | Not yet tested | Fully functional — representative `beam` |
| `evmInterface` | EVM bytecode interface/selector analysis | Bundled evmole npm dependency | Not yet tested | Fully functional — representative `evm` |
| `firmwareAnalysis` | Binwalk region inspection and Unblob extraction | Binwalk 3.1.x; Unblob 26.6.x; prlimit; format-specific extractors | Missing dependency | Fully functional — representative `firmware`, `firmware-extract`, `firmware-ext2` |
| `flutter` | Flutter application and AOT metadata inspection | Built-in static provider; supported input/layout admission applies | Not yet tested | Fully functional — representative `flutter` |
| `fridaInstrumentation` | Local process/device instrumentation | Matched Frida 17.25.1 npm/native SDK override; original REA source pins 17.23.2; target permissions | Not yet tested | Partially functional — original same-process regression; corrected scratch direct/mixed tests pass, artifact acceptance pending |
| `gdbSessions` | Native debugging sessions | GDB executable; suitable target and ptrace permissions | Not yet tested | Fully functional — representative `gdb` |
| `ghidra` | Native analysis, procedures, decompilation and cross references | Ghidra 12.x >=12.1; supported full JDK; GHIDRA_INSTALL_DIR | Not yet tested | Fully functional — representative `ghidra` |
| `goBinary` | Go build info, symbols and runtime metadata | Built-in parser; no Go runtime required for static inspection | Not yet tested | Fully functional — representative `go-binary` |
| `gpuCodeObjects` | GPU code object metadata | Built-in static parser; not GPU execution | Not yet tested | Fully functional — representative `gpu` |
| `harmonyApplicationGraph` | Harmony application graph | Built-in artifact/application parsers | Not yet tested | Fully functional — representative `harmony-graph` |
| `hopper` | Hopper native analysis provider | Caller-provisioned Hopper and applicable license/demo constraints; Linux display/Python prerequisites | Unconfigured external provider | Not yet tested |
| `ida` | IDA native analysis through selected MCP registration | Caller-provisioned IDA and MCP integration; REA_IDA_MCP_CONFIG | Unconfigured external provider | Not yet tested |
| `il2cppMetadata` | Unity IL2CPP metadata | Built-in parser; native code correlation additionally needs qualified binary provider | Not yet tested | Fully functional — representative `il2cpp` |
| `javascriptApplication` | JavaScript/TypeScript/bundle application structure | Built-in parser and bundled dependencies | Not yet tested | Fully functional — representative `javascript` |
| `javascriptRecovery` | Recovered/deobfuscated JavaScript through Wakaru | Standalone Wakaru ^1.13.0 Linux x64 binary and prlimit; REA_WAKARU_COMMAND | Missing dependency | Fully functional — representative `javascript-recovery` |
| `javascriptRuntimeObservation` | Node/V8 runtime inspection | Local V8 Inspector endpoint or selected supported Node process | Unconfigured external runtime | Fully functional — representative `runtime` |
| `javascriptRuntimeReconciliation` | Static/runtime JavaScript evidence reconciliation | Built-in workflow plus real static/runtime evidence | Not yet tested | Fully functional — representative `runtime` |
| `jeb` | JEB analysis MCP provider | Activated JEB engine, local MCP endpoint; REA_JEB_MCP_URL | Unconfigured external provider | Not yet tested |
| `kernelBuildConfig` | Embedded Linux kernel configuration | Built-in parser | Not yet tested | Fully functional — representative `kernel-config` |
| `kernelModule` | Linux kernel module metadata | Built-in ELF/module parser | Not yet tested | Fully functional — representative `kernel-module` |
| `kuna` | Kuna native decompiler provider | Packaged Linux Kuna 1.990; REA_KUNA_COMMAND override | Missing dependency; Linux qualification required | Fully functional — representative `kuna` |
| `managedStatic` | .NET PE/CLI metadata and CIL inspection | Built-in TypeScript parser; .NET runtime and ILSpy not required | Not yet tested | Fully functional — representative `managed` |
| `managedWorkflow` | Managed application, interop and reconstruction workflows | Built-in parser/workflows; supplied reconstruction evidence; optional ILSpy oracle | Not yet tested | Fully functional — representative `managed-workflow` |
| `modelArtifact` | ML model artifact inventory | Built-in static format parsers; no model inference/runtime implied | Not yet tested | Fully functional — representative `model` |
| `nativeExports` | PE/ELF/Mach-O export inventory | Built-in parser | Not yet tested | Fully functional — representative `native-exports` |
| `nativeMacOS` | Native macOS UI/runtime/LLDB observations | macOS facilities and permissions; cannot be supplied by Linux packages | Unsupported on target platform | Unsupported on target platform |
| `packetCapture` | Packet capture inspection through tshark | Wireshark tshark 4.x; REA_TSHARK_COMMAND | Missing dependency | Fully functional — representative `packet-capture`; fresh policy-bearing c7373502 installation passed; corrected-Frida final reinstall pending |
| `pcap` | PCAP/PCAPNG inspection and stream queries | tshark and capinfos 4.x; REA_TSHARK_COMMAND/REA_CAPINFOS_COMMAND | Missing dependency | Fully functional — representative `pcap-summary`; fresh policy-bearing c7373502 installation passed; corrected-Frida final reinstall pending |
| `peCertificates` | PE certificate table inspection | Built-in parser; not signature trust validation | Not yet tested | Fully functional — representative `pe-certificates` |
| `peImports` | PE imports/delay imports | Built-in parser | Not yet tested | Fully functional — representative `pe-imports` |
| `peLoadConfig` | PE load configuration | Built-in parser | Not yet tested | Fully functional — representative `pe-load-config` |
| `binaryHardening` | Static binary hardening evidence | Built-in ELF/PE/Mach-O readers | Not yet tested | Fully functional — representative `binary-hardening` |
| `peResources` | PE resource inventory | Built-in parser | Not yet tested | Fully functional — representative `pe-resources` |
| `windowsShortcut` | Windows LNK inspection | Built-in parser; no Windows execution required | Not yet tested | Fully functional — representative `windows-shortcut` |
| `pythonPyc` | Python bytecode inspection | Built-in parser for admitted bytecode versions; not arbitrary execution | Not yet tested | Fully functional — representative `python-pyc` |
| `nugetNupkg` | NuGet package inventory/dependencies | Built-in ZIP/XML readers; new after npm 6.9.0 tag | Missing in release baseline | Fully functional — representative `nuget` |
| `releaseExposure` | Release exposure inventory and comparison | Built-in static workflow; selected local artifacts | Not yet tested | Fully functional — representative `release-exposure` |
| `v8CodeCache` | V8 code-cache inspection | Built-in static reader; version-specific admission | Not yet tested | Fully functional — representative `v8-cache` |
| `recordedCrash` | Recorded core/crash inspection | Python3 + pwntools and supported recorded artifacts | Not yet tested | Fully functional — representative `recorded-crash`, `pwndbg-core` |
| `reverseEngineering` | Objdump inspection and Rizin commands | binutils objdump; separate Rizin executable/REA_RIZIN_COMMAND | Partially provisioned; Rizin missing | Fully functional — representative `objdump`, `rizin` |
| `rizinDebugSessions` | Rizin native debugger sessions | Rizin executable, compatible target and ptrace permissions | Missing dependency | Fully functional — representative `rizin-debugger` |
| `rustBinary` | Rust binary metadata/symbol inspection | Built-in static parser; no Rust runtime required for static inspection | Not yet tested | Fully functional — representative `rust` |
| `signalRecording` | Recorded signal decoding and decoder inventory | sigrok-cli 0.7.2 + libsigrokdecode; Linux prlimit; REA_SIGROK_COMMAND | Missing dependency | Fully functional — representative `signal-recording` |
| `sqliteDatabase` | Read-only SQLite schema/query analysis | Node bundled SQLite capability and REA read-only workflow | Not yet tested | Fully functional — representative `sqlite` |
| `wasmArtifact` | WASM validation, disassembly and WAT inspection | WABT >=1.0.42 <1.1.0; REA_WABT_BIN_DIRECTORY | Missing dependency | Fully functional — representative `wasm` |
| `webModuleTrace` | Web module import tracing | Built-in parser and captured scripts | Not yet tested | Fully functional — representative `web-modules` |
| `webNetworkCapture` | HAR, SAZ, mitmproxy and qlog evidence | HAR/SAZ/qlog readers built in; mitmproxy capture decoding may require configured Python/mitmproxy | Not yet tested | Fully functional — representative `mitmproxy`, `environment-export` |
| `webRuntime` | Web runtime evidence | Local CDP browser and selected session | Unconfigured external provider | Fully functional — representative `web-runtime` |
| `webScriptExport` | Captured web script export | Built-in workflow with retained browser/script Evidence | Not yet tested | Fully functional — representative `web-export` |
| `webSourceLocation` | Source-map/source-location correlation | Built-in parser, source maps and captured script Evidence | Not yet tested | Fully functional — representative `web-source` |

## Shared contracts and workflows outside individual provider declarations

| Contract/workflow | Coverage required | Dependencies and original gap | Validation status |
| --- | --- | --- | --- |
| CLI | `--version`, help, JSON commands, `doctor`, `providers`, `capabilities`, analysis command contracts and error exits | Original SDK only exposes restricted `hermes-rea-stdio`; no ordinary `rea` entrypoint. This is a packaging interface defect. | Fully functional — representative `cli`, `javascript` |
| MCP initialization and complete catalog | Initialize, notifications, paged `tools/list`, compare to full source contract inventory and selected family policy | Original smoke asserts only a nonempty list; that cannot establish catalog parity. | Fully functional — representative `mcp-catalog` |
| `binary_session` | Discovery, selected provider/configuration, actual availability and active target | Must remain present under the intended tool-family profile; availability must be compared with real operations. | Partially functional — representative `mcp-catalog`, `ghidra`, `rizin`, `gdb`, `provider-no-fallback` |
| Binary session lifecycle | Open, close, reset, snapshots, restore, cancellation and shutdown cleanup | Provider-specific target/process ownership; writable state/evidence paths | Partially functional — representative `mcp-catalog`, `ghidra`, `rizin`, `gdb`, `provider-no-fallback` |
| Evidence lifecycle | Inspect/search/compare/export/import Evidence bundles and provenance | JSON files and retained session state; explicit paths and digest checks | Fully functional — representative `evidence` |
| Analysis settings | Inspect/update supported budgets and selectors | Built-in settings; cannot turn an unavailable provider into a supported one | Fully functional — representative `settings` |
| Official/enhanced binary workflows | Procedures, strings, xrefs, decompilation, assembly, function analysis and mutation where selected provider permits | Per-provider supported subsets; never silently substitute Ghidra for another provider | Partially functional — representative `ghidra`, `rizin`, `objdump`, `kuna`, `cutter` |
| API contracts | OpenAPI/GraphQL and endpoint/runtime correlation | Built-in parsers; captured/runtime Evidence where requested | Fully functional — representative `api-contracts` |
| NTFS journal and filesystem evidence | Static recorded NTFS change-journal interpretation | Built-in parser; Linux host does not prevent static Windows artifact analysis | Fully functional — representative `ntfs-journal` |
| Playwright trace import | Stored browser trace evidence | Built-in trace reader; no live browser required for offline import | Fully functional — representative `playwright-trace` |
| Process scenario capture | Capture a harmless selected command through PTY, interactions and selected filesystem observations | Native node-pty dependency and process ownership; not a sandbox | Fully functional — representative `process` |
| Runtime evidence correlation | Compare process captures/artifacts/functions, find changed behavior, build call paths and correlate explicit static/runtime hypotheses | Built-in workflows; real compatible source Evidence; cochange is not causality | Partially functional — representative `runtime` |
| Unknown lifecycle / reconstruction | Record/update/list unknowns, verify their resolution and verify a finite reconstruction specification | Built-in registry; missing observations remain unknown | Partially functional — `unknown-lifecycle` and `reconstruction-verification` passed; general resolution remains outside these fixtures |
| Environment bundle export | Generate replayable environment files from accepted Evidence | Export does not prove external AgentEnv/Docker execution | Fully functional — representative `environment-export` |
| Workshop persistence | State mount survives refresh/reinstall, SDK hook state and restored evidence remains readable | Existing `/var/lib/hermes-rea` mount; per-user home/working-directory contracts matter | Partially functional — real refresh/replay passed; fresh final-artifact reinstall pending |
| Restricted SSH transport and artifact input | Forced command, bounded input and clean MCP stdout | Existing openssh-server/public allowlist and artifact wrapper; must preserve original restriction while adding local CLI | Fully functional — six local boundary and six authenticated network checks passed |

Additional shared evidence: `ghidra` passed target-bound snapshot save/reopen; `ilspy-reconstruction` passed optional decompilation/import; `full-source` verified the complete source tree and ran its original CLI. Windows x64 native filesystem/Job Object controls are unsupported on Ubuntu by `src/windows/WindowsNativeLoader.ts`; static Windows artifacts are separate. All eight NativeAOT extension proof modes passed; see [the exact results](nativeaot-validation.md), including positive recovery and expected refusals. Finite reconstruction verification also passed accepted/rejected/mixed/unknown claims with exact retained evidence links; see [the bounded proof](reconstruction-validation.md). These are mapped explicitly in the JSON, without inventing additional declared capability keys.

The canonical grouped contract inventory includes analysis settings, official/enhanced binary, native, diagnostics, analysis views, artifacts, release exposure, desktop application, EVM, Go, IL2CPP, model, GPU, Rust, Python, NuGet, Erlang, V8, WASM, APK signatures, SQLite, capture, signals, managed, Android, Apktool, PCAP, Flutter, JEB, ADB, firmware, managed workflows, browser providers, Electron, JS runtime, application, web script/runtime/network, environment export, desktop build, JS recovery, sessions, Cutter, reverse-engineering, GDB, Rizin debug, and Frida. Browser and scenario arrays are named subsets, not additional public catalogs.


## Artifact format inventory and Linux boundaries

This supplements the capability table: a format identifier is not proof of every operation. Source owner is `src/domain/artifactGraph.ts#ARTIFACT_FORMAT_IDS`; reader behavior is in `src/artifacts/artifactFormats.ts`. The 48 identifiers below match the source inventory exactly. The status column is format-reader-specific: a passing higher-level capability does not prove every container variant or extraction path.

| Format IDs | Source-defined scope / dependency | Linux status |
| --- | --- | --- |
| `directory`, `file`, `unknown` | Filesystem inventory and explicit unknown classification | Not yet tested; `unknown` is a classification, not a decoder |
| `zip`, `ipa`, `apk`, `msix`, `appx`, `hap`, `hsp`, `app-pack` | ZIP-family inventory/extraction and package metadata | ZIP inventory/extraction and APK/IPA/HAP path fixtures passed (`archive`, graph cases); MSIX/APPX/HSP/app-pack and complete semantic variants untested |
| `asar` | Electron ASAR reader, including declared unpacked companions | Not yet tested |
| `dotnet-bundle`, `bun-standalone`, `deno-standalone`, `pyinstaller`, `node-sea` | Embedded application/asset readers with version-specific admission; no target execution | Not yet tested |
| `ines`, `godot-pck`, `unityfs`, `wxapkg` | Game/package/container readers; not emulation or runtime execution | Not yet tested |
| `uimage`, `fit`, `intel-hex`, `srec`, `esp-image`, `uf2`, `dfuse`, `esp-flash-image` | Built-in firmware component/readers and explicitly admitted integrity/extraction modes | Not yet tested; separate from Binwalk/Unblob |
| `android-boot-image`, `android-ota-payload` | Boot/vendor boot and OTA payload inventory; exact operation coverage follows reader limitations | Not yet tested; current-main additions beyond release baseline |
| `ntfs-mft` | Recorded NTFS Master File Table reader | `ntfs-journal` passed paired MFT fixups, digest and sequence-checked reference; general artifact extraction untested |
| `javascript-bundle`, `source-map` | Artifact classification; JS/source-map analysis supplied by corresponding workflows | JS graph/recovery and exact browser source-map tracing passed; exhaustive bundle-reader coverage untested |
| `elf`, `pe`, `mach-o`, `dos-mz`, `dos-com`, `raw-binary`, `gamecube-dol` | Classification/static facts; deep analysis requires a provider admitting the selected target | ELF/PE representative static/provider operations passed; other listed format-reader variants untested; arbitrary bytes are not automatically executable targets |
| `plist`, `entitlements` | Static structured Apple metadata | Not yet tested |
| `hopper`, `analysis-database` | Recognized analysis artifacts; actual use depends on corresponding provider/database support | Unconfigured external provider / not yet tested |
| `dmg` | Native DMG entry reader explicitly requires Darwin | Unsupported on target platform for entry reading/extraction; recognition is separate |
| `mach-o-universal` | Reader/slice extraction explicitly requires Darwin and its native tooling | Unsupported on target platform for this reader; thin Mach-O static inspection remains distinct |
| `pkg` | Recognized container with no `createReader` in current format registry | Upstream limitation: entry inventory/extraction absent; not repaired by installing Ghidra |

## Provider dependency decisions

| Provider/tool | Source-authoritative requirement | Packaging and validation consequence |
| --- | --- | --- |
| REA runtime | Node `^22.23.4 || ^24.22.1 || >=26.12.1`; current source package manager npm 11.16.0; immutable source/dependency locks | Preserve unmodified source and matching built contract metadata. An npm release version alone cannot identify current-main bytes. |
| Process ownership | procps-compatible `ps` on Linux, util-linux `prlimit` for bounded integrations | Install explicitly; a provider executable may exist but refuse to run without ownership probes. |
| Ghidra | 12.x >=12.1 and its supported full JDK; original bundle 12.1.4/JDK25 | Verify native decompiler startup and real binary output. NativeAOT extension requires a separately built `REA_GHIDRA_NATIVEAOT_JAR`; plain Ghidra is not proof of that optional extension. |
| JADX | `jadx-headless-mcp-0.7.1-all.jar`, SHA256 `6e5eacf500b64292bfb73c49797c1958f6ee44646e43e868039ae7feb573ff75`, Java compiler modules | JAR: `https://github.com/1013503897/jadx-headless-mcp/releases/download/v0.7.1/jadx-headless-mcp-0.7.1-all.jar`; set `REA_JADX_MCP_JAR`; test classes/methods, not only `--version`. |
| Wakaru | Linux x64 standalone binary, accepted ^1.13.0; parser verified 1.13.0, docs recommend 1.14.0 | `REA_WAKARU_COMMAND` must select the actual platform executable, not npm's Node shim; keep prlimit constraints. |
| Binwalk / Unblob | Binwalk 3.1.x (verified 3.1.0); Unblob 26.6.x (verified 26.6.4) | Install compatible versions and format extractors such as `debugfs`; do not disable Unblob Landlock sandbox to manufacture a pass. General `rea doctor` does not inspect firmware readiness. |
| WABT | `wasm-validate`, `wasm-objdump`, `wasm2wat`; >=1.0.42 <1.1.0, verified 1.0.42 | Set absolute `REA_WABT_BIN_DIRECTORY`; all executable versions must pass admission and an actual WASM request. |
| Apktool | >=2.7.0; caller-selected launcher or PATH | Preserve reported warnings for old/vulnerable decoder builds; newer compatible release preferred. |
| Packet capture | tshark and capinfos major 4 | Install both; prove decoded packets/stream results from a synthetic capture. |
| Native mitmproxy recordings | `mitmdump` exactly 12.2.3, Linux | Required for native `.mitm` decoding, with version admission; HAR, SAZ and qlog readers are independent built-in paths. A generic network-capture pass does not prove `.mitm` decoding. |
| Recorded GDB cores / Pwndbg | Pwndbg is optional mapping/context enrichment, documented baseline 2026.09.15 | `REA_PWNDBG_GDB`, `REA_PWNDBG_GDBINIT`, `REA_PWNDBG_VENV_PATH` select enrichment. Its absence does not disable the base recorded-core parser. |
| NativeAOT metadata | Built-in x64 PE/.NET 8 RTR 9.1 inspection; optional Ghidra extension | Broader metadata/database annotations need `REA_GHIDRA_NATIVEAOT_JAR`; upstream submodule commit `effeb734fc570c32650f88b159608979dc7b423e` can be built with `npm run build:ghidra:nativeaot` plus full JDK. Do not equate the optional extension with all NativeAOT inspection. |
| Signal recordings | sigrok-cli 0.7.2 and libsigrokdecode; Linux/prlimit | Recorded waveform test and decoder result assertions, not physical device presence. |
| Rizin / GDB / Frida | Separate executable/native binding and process permissions | Real harmless target sessions needed. A working Ghidra path cannot cover these providers. |
| Kuna | Apache-2.0 standalone executable; verified upstream baseline 1.990 on macOS arm64 | Linux x64 1.990 is packaged; installed `kuna` case selected it explicitly and decompiled a synthetic function. This supplements upstream macOS-only release qualification at representative Linux scope. |
| Hopper / IDA / JEB | Caller-provided engine and applicable license/activation; provider-specific bridges/registrations | Keep explicit unconfigured status unless supplied and tested. JEB Linux CE 5.48.0.202610071539 exists, but vendor EULA/license activation is separate and CE capabilities differ from licensed Android decompilation. |
| Cutter | Packaged Qt5/PySide2 GUI and unchanged bridge; caller-owned session | Headless execution uses packaged Xvfb. Installed `cutter` case passed actual metadata, symbol and disassembly operations and owned-session teardown; upstream target identity remains partial. |
| Browser / Electron / V8 | Compatible browser/runtime, libraries, local endpoint or selected executable | Package browser prerequisites; use real local synthetic app. Target Electron runtime/device still belongs to the analysis input. |
| Managed/.NET | Production PE/CLI/CIL parser is REA TypeScript | Do not misclassify missing .NET SDK or ILSpy as failure of built-in managed inspection. Optional ILSpy reconstruction is a separate lane using `REA_ILSPY_CMD_PATH`. |
| Desktop build computers | Docker engine/CLI, agentenv-framework==0.9.1485, packed REA runtime archive | `REA_AGENT_ENV_COMMAND`, `REA_DOCKER_COMMAND`, `REA_BUILD_COMPUTER_REA_ARCHIVE`; nested runtime operation must be proven in Workshop or reported unconfigured/incompatible with evidence. |
| macOS native UI/runtime | macOS frameworks, UI permissions and LLDB route | Unsupported on Ubuntu; static Mach-O/Apple artifact analysis remains independently testable. |

## Evidence and limits

Execution evidence includes the historical installed Workshop's 93 selected passing cases plus the newer artifact-specific observations described above. A failed request retains its actual reason in raw history. Upstream format admission, proprietary engine licensing, caller-selected external processes, missing package dependencies and container limitations remain distinct. The complete-source case verifies 14,149 tracked entries, 135,520,255 bytes, all five submodules and three derived runtime links, then runs the original source CLI against the real JavaScript fixture. Git history is omitted from the package; the SDK repository's history/identity is preserved.

`tests/main/launch/static_cases.py` adds semantic checks for 47 static and workflow cases. Its generated fixtures are inert format samples from the exact pinned source and retain the upstream MIT notice; `regenerate-static-fixtures.mjs` reproduces them. These tests exercise real MCP providers and the upstream desktop runtime archive producer, not mocked replies. Fixture coverage is deliberately bounded: Rust checks cargo-auditable dependency metadata; GPU checks PTX declarations without GPU execution; Apple/Harmony graphs check paths without executing applications; PKCS#7 checks metadata without asserting certificate trust; Flutter checks snapshot headers/string pools without decompiling arbitrary Dart. Go's compiler is a test fixture prerequisite, not a REA runtime dependency. Host debugging results must not be promoted to Workshop installation evidence.

Source references: [installation](https://github.com/morluto/rea/blob/51459cf203ae1eb6b586a95b21899eaa0f631823/docs/getting-started/installation.md), [firmware](https://github.com/morluto/rea/blob/51459cf203ae1eb6b586a95b21899eaa0f631823/docs/guides/firmware/firmware-analysis.md), [JavaScript recovery](https://github.com/morluto/rea/blob/51459cf203ae1eb6b586a95b21899eaa0f631823/docs/guides/javascript/javascript-recovery.md), [managed boundary](https://github.com/morluto/rea/blob/51459cf203ae1eb6b586a95b21899eaa0f631823/docs/guides/managed/managed-code-analysis.md#tool-and-packaging-boundary), [Android](https://github.com/morluto/rea/blob/51459cf203ae1eb6b586a95b21899eaa0f631823/docs/guides/android/android-analysis.md), [WASM](https://github.com/morluto/rea/blob/51459cf203ae1eb6b586a95b21899eaa0f631823/docs/guides/wasm/wasm-artifacts.md), [signals](https://github.com/morluto/rea/blob/51459cf203ae1eb6b586a95b21899eaa0f631823/docs/guides/signals/signal-recordings.md), [Kuna](https://github.com/morluto/rea/blob/51459cf203ae1eb6b586a95b21899eaa0f631823/docs/kuna-provider.md), [IDA](https://github.com/morluto/rea/blob/51459cf203ae1eb6b586a95b21899eaa0f631823/docs/providers/ida-provider.md), [JEB](https://github.com/morluto/rea/blob/51459cf203ae1eb6b586a95b21899eaa0f631823/docs/providers/jeb-analysis.md), [desktop build](https://github.com/morluto/rea/blob/51459cf203ae1eb6b586a95b21899eaa0f631823/docs/desktop-build-computer.md).

The `artifact-resources` representative case checks both the public archive lifecycle and the installed resource owners with real files: post-close inspection is refused, reopening preserves content, a closed owned handle rejects reads with EBADF, and an owned private scratch root disappears. Published extraction output persists by contract. This does not claim exhaustive cancellation, cleanup-failure or leak coverage. The installed `artifact-resources` case passed these normal-lifecycle assertions; final rebuilt-artifact acceptance remains separate.


The coverage map assigns representative cases to 73 of 78 capability groups. All 93 saved selected cases are now mapped, including optional ILSpy reconstruction and explicit selected-provider failure without fallback. The desktop group now includes a real model-free Docker/AgentEnv lifecycle: owned xterm typing changed retained INI values, screenshots decoded, and teardown was confirmed. External model-driven solve/measure and complete export variants require separate configuration and execution evidence. The original SDK assessment column remains historical.

Supplemental HOME correction proof: ADB daemon initialization and actual MCP enumeration passed; restricted SSH passed again with worker startup-file probes and cleanup. See [ADB validation](adb-validation.md) and [MCP/session validation](mcp-session-validation.md). The enforced TShark regression also passed with a valid allowed capture round-trip and a DAC-writable outside-work destination denied at exit9. The fresh policy/HOME-corrected c7373502 package also passed ADB initialization and the enforced TShark regression. The corrected-Frida replacement package and independent reinstall still require acceptance.
