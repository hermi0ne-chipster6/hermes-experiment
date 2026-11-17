# Packaged executable and ZIP container validation

`tests/main/launch/container_format_cases.py` adds eleven independent cases through `run_container_format_cases(mcp, work, test)`. `CONTAINER_FORMAT_CASES` lists their exact names. The parent runner must copy the helper and `container-format-fixtures.json` beside its existing helpers and register the callback. No shared runner, SDKcraft definition or Spread file is changed by this contribution.

The pinned REA commit is `51459cf203ae1eb6b586a95b21899eaa0f631823`. Its public interfaces are `open_binary`, `inspect_artifact`, `extract_artifact`, and `close_binary`; it does not expose fictional `open_artifact`, list-entry or read-entry MCP methods. Inspection contains retained nested inventory Evidence. Each case verifies the root format, exact member occurrence and content hash, selects those occurrence IDs for extraction, requires verified containment, reads exact extracted bytes and confirms the input hash remains unchanged. Every opened session closes in `finally`.

| Case | Representative stored content | Scope |
| --- | --- | --- |
| `container-asar` | Chromium-pickle ASAR with `main.js` | Native ASAR reader |
| `container-dotnet-bundle` | PE apphost marker and .NET v6 bundle with stored and deflated data | Container parsing and decompression, not managed assembly execution |
| `container-bun-standalone` | ELF carrier with Bun 1.3.9 module graph and source | Stored source extraction, not bytecode decompilation |
| `container-deno-standalone` | ELF note carrying a Deno section and VFS source | Stored source and metadata inventory |
| `container-node-sea` | ELF SEA blob with main script, asset and unset fuse | Static extraction without running its launcher |
| `container-pyinstaller` | ELF CArchive 2.1 with compressed data | Data-member extraction, not Python execution or general bytecode decompilation |
| `container-msix` / `container-appx` | Deflated ZIP, minimal manifest, marker | Upstream ZIP-signature plus package-suffix classification; no Windows installation/signature trust |
| `container-hsp` / `container-app-pack` | Deflated ZIP with module/pack metadata and marker | HSP or root `.app` package classification; no HarmonyOS execution |
| `container-plist-resources` | ZIP with binary plist and XML entitlement resource | Member classification and byte-preserving extraction only |

Plist and entitlements are described as plain formats in upstream `src/artifacts/artifactFormats.ts`; their presence in the format catalog is not an independent container reader. Native `inspect_plist` requires an open binary or bundle-resource session and its documented native tooling. This extension deliberately makes no claim of native plist semantic decoding, signing or entitlement enforcement on Linux.

Six binary containers are generated from upstream inert fixture factories by `regenerate-container-format-fixtures.mjs`; the output records the pinned Git commit and SHA256 of ten source files. The generator uses Node 24 TypeScript stripping and records no target execution. Bun's source fixture also exports an unused read-side helper; its runtime import resolves against the supplied built REA directory, while generation calls only the pinned fixture's serializer helpers. All embedded JavaScript throws if executed; carriers are inert structural data, not usable third-party applications. The upstream MIT attribution is retained in JSON and the existing `static-fixtures-LICENSE.txt`. ZIP fixtures use standard-library writers with fixed timestamps.

Generation completed successfully under tmux using Node 24.22.1. Python/JavaScript syntax and generated fixture hashes were checked.

All **11/11 actual public MCP cases passed** in an isolated host process using the unmodified `rea/` subtree extracted from verified SDK SHA256 `c7373502e97f32c34be99ba7fd92e7ea5832caf31121aa79a747badd27cf22c5`. Its `UPSTREAM_COMMIT` is the pinned `51459cf…`; provenance is retained in `/root/dev/rea-sdk/host-contract-runtime/provenance.json`. The host process used private HOME, TMPDIR and working directories, exposed exactly 259 tools, closed every artifact session, and shut down on stdin EOF with exit 0. No Frida or external provider operations were used.

Evidence: `/root/dev/rea-sdk/validation-logs/container-host-1.log` and `.exit` (0); complete raw MCP replies, initialization, inventory, results and shutdown receipts under `/root/dev/rea-sdk/agent-worktrees/agent-b/.validation/container-host-1/output/`. All nineteen selected member payloads matched their exact source bytes; inputs remained unchanged and containment was verified. The six carrier fixtures plus five ZIP cases required no contract corrections.

These are **host-only fixture-contract results, not final installed SDK acceptance**. The primary operator must run all eleven cases against the verified final artifact in Workshop and retain those independently scoped results. Fixture generation and advertised format names alone are never operational proof.
