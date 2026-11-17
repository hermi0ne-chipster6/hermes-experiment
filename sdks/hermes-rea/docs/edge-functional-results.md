# Edge functional case results

These results are for Store revision 2. The initial run used the SDK launcher with its default profile. The eight targeted retries used the configurations shown in the table.

| Case | Initial result | Targeted retry | Configuration |
| --- | --- | --- | --- |
| `cli` | pass | — | — |
| `cli-setup` | pass | — | — |
| `cli-evidence` | pass | — | — |
| `full-source` | pass | — | — |
| `mcp-catalog` | pass | — | — |
| `javascript` | pass | — | — |
| `archive` | pass | — | — |
| `evidence` | pass | — | — |
| `objdump` | pass | — | — |
| `binary-layout` | pass | — | — |
| `rizin` | pass | — | — |
| `provider-no-fallback` | pass | — | — |
| `gdb` | pass | — | — |
| `rizin-debugger` | pass | — | — |
| `frida` | pass | — | — |
| `frida-injection` | pass | — | — |
| `sqlite` | pass | — | — |
| `managed` | pass | — | — |
| `android` | pass | — | — |
| `apktool` | pass | — | — |
| `javascript-recovery` | pass | — | — |
| `wasm` | pass | — | — |
| `firmware` | pass | — | — |
| `firmware-extract` | pass | — | — |
| `firmware-ext2` | pass | — | — |
| `runtime` | pass | — | — |
| `browser` | pass | — | — |
| `browser-scenario` | pass | — | — |
| `web-runtime` | pass | — | — |
| `web-export` | pass | — | — |
| `web-source` | pass | — | — |
| `web-modules` | pass | — | — |
| `process` | pass | — | — |
| `mitmproxy` | pass | — | — |
| `kuna` | pass | — | — |
| `ghidra` | pass | — | — |
| `elf-notes` | pass | — | — |
| `native-exports` | pass | — | — |
| `binary-hardening` | pass | — | — |
| `native-initializers` | pass | — | — |
| `elf-unwind` | pass | — | — |
| `elf-dependencies` | pass | — | — |
| `dwarf` | pass | — | — |
| `elf-debug-link` | pass | — | — |
| `entropy` | pass | — | — |
| `model` | pass | — | — |
| `python-pyc` | pass | — | — |
| `evm` | pass | — | — |
| `kernel-module` | pass | — | — |
| `devicetree` | pass | — | — |
| `nuget` | pass | — | — |
| `apple-ips` | pass | — | — |
| `beam` | pass | — | — |
| `gpu` | pass | — | — |
| `rust` | pass | — | — |
| `v8-cache` | pass | — | — |
| `windows-shortcut` | pass | — | — |
| `il2cpp` | pass | — | — |
| `flutter` | pass | — | — |
| `apple-graph` | pass | — | — |
| `harmony-graph` | pass | — | — |
| `go-binary` | pass | — | — |
| `pe-imports` | pass | — | — |
| `pe-certificates` | pass | — | — |
| `pe-resources` | pass | — | — |
| `pe-load-config` | pass | — | — |
| `kernel-config` | pass | — | — |
| `electron-fuses` | pass | — | — |
| `analysis-view` | pass | — | — |
| `android-graph` | pass | — | — |
| `apk-signature` | pass | — | — |
| `release-exposure` | pass | — | — |
| `settings` | pass | — | — |
| `unknown-lifecycle` | pass | — | — |
| `managed-workflow` | pass | — | — |
| `desktop-application` | pass | — | — |
| `application-comparison` | pass | — | — |
| `api-contracts` | pass | — | — |
| `playwright-trace` | pass | — | — |
| `environment-export` | pass | — | — |
| `ntfs-journal` | pass | — | — |
| `desktop-runtime-pack` | pass | — | — |
| `artifact-resources` | pass | — | — |
| `packet-capture` | pass | — | — |
| `pcap-summary` | pass | — | — |
| `signal-recording` | pass | — | — |
| `recorded-crash` | pass | — | — |
| `pwndbg-core` | pass | — | — |
| `ilspy-reconstruction` | pass | — | — |
| `desktop-clients` | pass | — | — |
| `tshark-policy` | pass | — | — |
| `frida-process-lifecycle` | pass | — | — |
| `adb-initialization` | pass | — | — |
| `reconstruction-verification` | pass | — | — |
| `electron-passive` | pass | — | — |
| `electron-active` | pass | — | — |
| `cutter` | pass | — | — |
| `desktop-dconf` | pass | — | — |
| `desktop-capture` | pass | — | — |
| `desktop-build` | pass | — | — |
| `container-asar` | pass | — | — |
| `container-dotnet-bundle` | pass | — | — |
| `container-bun-standalone` | fail | pass | Explicit Kuna |
| `container-deno-standalone` | fail | pass | Explicit Kuna |
| `container-node-sea` | fail | pass | Explicit Kuna |
| `container-pyinstaller` | fail | pass | Explicit Kuna |
| `container-msix` | pass | — | — |
| `container-appx` | pass | — | — |
| `container-hsp` | pass | — | — |
| `container-app-pack` | pass | — | — |
| `container-plist-resources` | pass | — | — |
| `format-uimage` | pass | — | — |
| `format-fit` | pass | — | — |
| `format-intel-hex` | pass | — | — |
| `format-srec` | pass | — | — |
| `format-esp-image` | pass | — | — |
| `format-uf2` | pass | — | — |
| `format-dfuse` | pass | — | — |
| `format-esp-flash-image` | pass | — | — |
| `format-android-boot-image` | pass | — | — |
| `format-android-ota-payload` | pass | — | — |
| `format-ines` | pass | — | — |
| `format-godot-pck` | pass | — | — |
| `format-unityfs` | pass | — | — |
| `format-wxapkg` | pass | — | — |
| `artifact-directory-classification` | pass | — | — |
| `native-load-mz` | fail | pass | Stock Ghidra with NativeAOT omitted |
| `native-load-com` | fail | pass | Stock Ghidra with NativeAOT omitted |
| `native-load-raw` | fail | pass | Stock Ghidra with NativeAOT omitted |
| `native-load-dol` | fail | pass | Stock Ghidra with NativeAOT omitted |
