# Installed Hermes REA validation coverage

Environment: `workshop:validation-corrected-06f5f874`. SDK SHA256: `b21c8af259f232e0547f56abf8152cc38032c2353677745ed37c46140241a4f1`.

A pass proves only the recorded representative scope. Missing means a tested operation was not operational; unresolved failure causes still require triage. Registration and diagnostics are not functional evidence. Earlier attempts remain in the JSON report.

## Capabilities

| Capability | Status | Representative tests | Scope / remaining limits |
| --- | --- | --- | --- |
| adbDevice | Partially functional | adb-initialization: pass | Fresh worker initialized its owned ADB daemon and enumerated an empty device set. Device shell, transfer and package operations require an attached device or emulator. |
| analysisView | Fully functional | analysis-view: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| android | Fully functional | android: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| androidApplicationGraph | Fully functional | android-graph: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| apkSignature | Fully functional | apk-signature: pass | V1 CMS signer/certificate metadata and exact file digest; v2/v3/v3.1 and cryptographic trust not exercised. |
| apktool | Fully functional | apktool: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| appleApplicationGraph | Fully functional | apple-graph: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| appleIps | Fully functional | apple-ips: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| applicationWorkflows | Fully functional | application-comparison: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| artifactGraph | Fully functional | archive: pass, apple-graph: pass, harmony-graph: pass, android-graph: pass, container-asar: pass, container-dotnet-bundle: pass, container-bun-standalone: pass, container-deno-standalone: pass, container-node-sea: pass, container-pyinstaller: pass, container-msix: pass, container-appx: pass, container-hsp: pass, container-app-pack: pass, container-plist-resources: pass, artifact-directory-classification: pass, format-uimage: pass, format-fit: pass, format-intel-hex: pass, format-srec: pass, format-esp-image: pass, format-uf2: pass, format-dfuse: pass, format-esp-flash-image: pass, format-android-boot-image: pass, format-android-ota-payload: pass, format-ines: pass, format-godot-pck: pass, format-unityfs: pass, format-wxapkg: pass | Representative archive, firmware and container operations passed. Bun, Deno, Node SEA and PyInstaller require explicit provider selection where Ghidra and Kuna both admit the carrier. |
| artifactResources | Fully functional | archive: pass, artifact-resources: pass, container-asar: pass, container-dotnet-bundle: pass, container-bun-standalone: pass, container-deno-standalone: pass, container-node-sea: pass, container-pyinstaller: pass, container-msix: pass, container-appx: pass, container-hsp: pass, container-app-pack: pass, container-plist-resources: pass, format-uimage: pass, format-fit: pass, format-intel-hex: pass, format-srec: pass, format-esp-image: pass, format-uf2: pass, format-dfuse: pass, format-esp-flash-image: pass, format-android-boot-image: pass, format-android-ota-payload: pass, format-ines: pass, format-godot-pck: pass, format-unityfs: pass, format-wxapkg: pass | Representative archive, firmware and container operations passed. Bun, Deno, Node SEA and PyInstaller require explicit provider selection where Ghidra and Kuna both admit the carrier. |
| binaryLayout | Fully functional | binary-layout: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| browserObservation | Fully functional | browser: pass | Real local browser target discovery and DOM/accessibility observation; does not cover every browser tool. |
| browserScenarioCapture | Fully functional | browser-scenario: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| byteEntropy | Fully functional | entropy: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| cutter | Fully functional | cutter: pass | Packaged Linux Cutter 2.5.0 Qt5 with unchanged REA bridge; requires an owned running GUI session and display (Xvfb provided for headless use). Representative session commands and cleanup do not imply every Cutter command was tested. |
| desktopApplication | Fully functional | desktop-application: pass, desktop-capture: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| desktopBuildComputers | Partially functional | desktop-clients: pass, desktop-runtime-pack: pass, desktop-build: pass | Model-free local AgentEnv desktop lifecycle, xterm, retained state changes, screenshots and teardown passed. Model-driven operations and remaining export variants require separate validation. |
| devicetree | Fully functional | devicetree: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| dwarfUnits | Fully functional | dwarf: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| electronActiveObservation | Fully functional | electron-active: pass | Dedicated Electron45.3.3 test-only target with actual IPC handler invocation; arbitrary target runtime compatibility is not implied. |
| electronFuses | Fully functional | electron-fuses: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| electronObservation | Fully functional | electron-passive: pass | Dedicated Electron45.3.3 test-only target for file CDP DOM/source; ordinary browser CDP is not substituted. |
| elfDependencies | Fully functional | elf-dependencies: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| elfNotes | Fully functional | elf-notes: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| elfDebugLink | Fully functional | elf-debug-link: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| nativeInitializers | Fully functional | native-initializers: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| elfUnwindRanges | Fully functional | elf-unwind: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| erlangBeam | Fully functional | beam: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| evmInterface | Fully functional | evm: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| firmwareAnalysis | Fully functional | firmware: pass, firmware-extract: pass, firmware-ext2: pass | Representative region/extractor operation; format-specific Unblob extractors require separate fixtures. |
| flutter | Fully functional | flutter: pass | Synthetic admitted APK snapshot headers and Dart string-pool evidence, not arbitrary Dart decompilation. |
| fridaInstrumentation | Fully functional | frida: pass, frida-injection: pass, frida-process-lifecycle: pass | Matched Frida 17.25.1 passed native loading, enumeration, instrumentation, 24 child-process checks and clean shutdown. SQLite and Ghidra succeeded after injection in the same MCP process. |
| gdbSessions | Fully functional | gdb: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| ghidra | Partially functional | ghidra: pass, native-load-mz: pass, native-load-com: pass, native-load-raw: pass, native-load-dol: pass | Default Ghidra decompiled ELF successfully. DOS MZ, COM, raw x86-64 and GameCube DOL passed with the installed stock engine after omitting the default NativeAOT profile; normal launcher defaults rejected those targets. |
| goBinary | Fully functional | go-binary: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| gpuCodeObjects | Fully functional | gpu: pass | PTX kernel parameter/register declarations, not GPU execution or every CUDA/AMDGPU container. |
| harmonyApplicationGraph | Fully functional | harmony-graph: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| hopper | Not yet tested | No representative test | Requires separately provisioned Hopper engine and applicable license/GUI bridge. |
| ida | Not yet tested | No representative test | Requires separately provisioned IDA engine, applicable license and MCP configuration. |
| il2cppMetadata | Fully functional | il2cpp: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| javascriptApplication | Fully functional | javascript: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| javascriptRecovery | Fully functional | javascript-recovery: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| javascriptRuntimeObservation | Fully functional | runtime: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| javascriptRuntimeReconciliation | Fully functional | runtime: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| jeb | Not yet tested | No representative test | Requires activated JEB with applicable license and local MCP endpoint; CE is not equivalent to licensed Android decompilation. |
| kernelBuildConfig | Fully functional | kernel-config: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| kernelModule | Fully functional | kernel-module: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| kuna | Fully functional | kuna: pass | Explicitly selected Linux Kuna decompiled a synthetic addition function. Upstream release notes only qualified macOS arm64; this installed Linux representative proof does not imply all architectures or operations. |
| managedStatic | Fully functional | managed: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| managedWorkflow | Fully functional | managed-workflow: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| modelArtifact | Fully functional | model: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| nativeExports | Fully functional | native-exports: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| nativeMacOS | Unsupported on target platform | No representative test | Native macOS framework/UI/runtime operations require Darwin and cannot execute on Ubuntu. |
| packetCapture | Fully functional | packet-capture: pass | Fresh candidate inspected real synthetic recorded DNS traffic with packaged policy. Live external network interception was outside the fixture scope. |
| pcap | Fully functional | pcap-summary: pass | Fresh candidate inspected real synthetic recorded DNS traffic with packaged policy. Live external network interception was outside the fixture scope. |
| peCertificates | Fully functional | pe-certificates: pass | PKCS7 metadata extraction from synthetic WIN_CERTIFICATE; no cryptographic trust claim. |
| peImports | Fully functional | pe-imports: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| peLoadConfig | Fully functional | pe-load-config: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| binaryHardening | Fully functional | binary-hardening: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| peResources | Fully functional | pe-resources: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| windowsShortcut | Fully functional | windows-shortcut: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| pythonPyc | Fully functional | python-pyc: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| nugetNupkg | Fully functional | nuget: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| releaseExposure | Fully functional | release-exposure: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| v8CodeCache | Fully functional | v8-cache: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| recordedCrash | Fully functional | recorded-crash: pass, pwndbg-core: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| reverseEngineering | Fully functional | objdump: pass, rizin: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| rizinDebugSessions | Fully functional | rizin-debugger: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| rustBinary | Fully functional | rust: pass | Synthetic cargo-auditable ELF dependency metadata, not Rust execution or full symbol recovery. |
| signalRecording | Fully functional | signal-recording: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| sqliteDatabase | Fully functional | sqlite: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| wasmArtifact | Fully functional | wasm: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| webModuleTrace | Fully functional | web-modules: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| webNetworkCapture | Fully functional | mitmproxy: pass, environment-export: pass | Native mitmproxy flow decoding and HAR ingestion/export; SAZ and qlog not individually exercised. |
| webRuntime | Fully functional | web-runtime: pass | Representative local browser runtime observation; arbitrary target execution and every CDP tool are not implied. |
| webScriptExport | Fully functional | web-export: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |
| webSourceLocation | Fully functional | web-source: pass | Representative tests only; unsupported input variants and exhaustive operation coverage are not implied. |

## Shared workflows

| Capability | Status | Representative tests | Scope / remaining limits |
| --- | --- | --- | --- |
| cli | Fully functional | cli: pass, cli-setup: pass, cli-evidence: pass, javascript: pass | Native CLI diagnostics, bundled shared-skill installation and idempotence, real JS Evidence publication/import/export and typed no-overwrite refusal |
| mcpCatalog | Fully functional | mcp-catalog: pass | Initialize and compare complete tools/list to packaged source catalog and binary_session inventory. |
| binarySession | Partially functional | mcp-catalog: pass, ghidra: pass, rizin: pass, gdb: pass, provider-no-fallback: pass | Actual explicitly selected Ghidra/Rizin/GDB operations and lifecycle; Ghidra snapshot reopen; explicit unavailable Ghidra selection refuses without opening a substitute provider. Other providers, cancellation and fault cleanup are separate. |
| evidenceLifecycle | Fully functional | evidence: pass | Export/reset/import with exact Evidence identity passed inside one installed environment; fresh-instance and mount persistence remain separate. |
| analysisSettings | Fully functional | settings: pass | Inspect/change/reset a runtime setting with revision/value assertions. |
| apiContracts | Fully functional | api-contracts: pass | OpenAPI operations and GraphQL SDL/query field binding; runtime endpoint correlation remains separate. |
| ntfsEvidence | Fully functional | ntfs-journal: pass | Recorded USN V2 with paired MFT fixups, exact digests and sequence-checked file reference; V3/V4 remain separate. |
| playwrightTraceImport | Fully functional | playwright-trace: pass | Offline v10 trace network/screencast references without replay or network. |
| processCapture | Fully functional | process: pass | Real harmless PTY process with captured output. |
| runtimeCorrelation | Partially functional | runtime: pass | JavaScript static/runtime reconciliation; general comparison hypotheses/call paths remain untested. |
| unknownLifecycle | Fully functional | unknown-lifecycle: pass | Create/list/update residual Unknown and inspect immutable history. |
| environmentExport | Fully functional | environment-export: pass | HAR-derived replay bundle generation and actual unchanged CLI loopback HTTP MCP serving: initialize, tools/list, fixture invocation with exact response/provenance, default state, and process/socket shutdown. Docker/AgentEnv desktop execution is separate. |
| workshopPersistence | Not yet tested | No representative test | Earlier Workshop refresh preserved files, Evidence and snapshot replay. Refresh validation was not repeated after the Frida/package changes. |
| restrictedSsh | Not yet tested | forced-command-version: not run, forced-command-mcp: not run, forced-command-rejections: not run, forced-command-artifact: not run | Earlier worker passed six local and six authenticated SSH checks. The transport and hooks match the previous verified payload. Authenticated SSH was not repeated in this candidate. |
| snapshots | Fully functional | ghidra: pass | Explicit-document Ghidra pseudocode/assembly queries saved as two replay bindings, restored after actual Workshop refresh and returned unchanged semantics with exact upstream replay provenance; other providers and cancellation/recovery variants remain separate. |
| desktopRuntimePackaging | Fully functional | desktop-runtime-pack: pass | Upstream pack-build-computer-runtime producer creates a self-contained production archive with matching package/lock/runtime entries; remote build computer execution is separate. |
| fullSource | Fully functional | full-source: pass | Complete pinned tracked source tree and five submodules: all manifest file hashes/modes, derived links, original source CLI version, real JavaScript graph operation. Git history is not required for runtime and is omitted. |
| ilspyReconstruction | Fully functional | ilspy-reconstruction: pass | Real optional ILSpy 11.2.0.10050 decompilation imported with managed method/source Evidence binding; independent from built-in managed parsing. |
| binaryWorkflows | Partially functional | ghidra: pass, rizin: pass, objdump: pass, kuna: pass, cutter: pass | Representative actual procedures/decompilation/assembly/symbol operations on explicitly selected providers; all mutation, xref and function workflow variants are not exercised. |
| reconstructionVerification | Fully functional | reconstruction-verification: pass | Representative finite structural-artifact claims over retained ZIP inventory comparisons: accepted, rejected, mixed, same-source unknown and shared-source residual Unknown propagation, exact Evidence closure and canonical claim-order digest. Behavioral/function claims and general unknown-resolution workflows remain outside this fixture. |
| nativeAotExtension | Not yet tested | No representative test | Eight proof modes passed on the earlier installed SDK. Archive comparison verifies the exact same extension JAR; the supplemental proof was not rerun. |
| windowsNativeControls | Unsupported on target platform | No representative test | Windows x64 native filesystem/Job Object controls require win32/x64 in src/windows/WindowsNativeLoader.ts; static PE, LNK and recorded NTFS parsers remain portable. |
| desktopStateDatabase | Fully functional | desktop-dconf: pass | Offline owned dconf database compiled and decoded with exact string/integer values; no user settings or D-Bus service modified. |
| tsharkConfinement | Fully functional | tshark-policy: pass | Enforced AppArmor allowed the owned capture round-trip and denied an otherwise writable outside-work destination. |
