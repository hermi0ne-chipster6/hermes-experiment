# Later upstream changes outside the frozen acceptance baseline

The current SDK acceptance baseline remains REA `51459cf203ae1eb6b586a95b21899eaa0f631823`, version 6.9.0. This audit does **not** change its source pin, provider inputs, active build, or test expectations. Full source preservation and representative functionality against that pinned baseline must not be described as including subsequent upstream changes.

On 2026-11-17, a separate fetch recorded upstream HEAD as `bb5278c7e2d5b0a423a63858c8b3c9682232e2d2`, five commits after the frozen baseline. This is an observed HEAD, not a promise that upstream remains there. The owning checkout retains it at `refs/remotes/origin/validation-head`; the range and diffstat are in `/root/dev/rea-sdk/validation-logs/upstream-head-delta.{log,stat}`. This review inspected that exact Git range without checking it out or running its engine.

## Public capability and contract changes

| Surface | Frozen baseline | Observed later HEAD | Qualification |
| --- | --- | --- | --- |
| Declared capability groups | 78 | 79 | New `mavenGradleMetadata` entry in `src/composition/capabilityDeclarations.ts` |
| Full MCP inventory | 259 tools operationally enumerated | Expected 260 tools from source delta | One new standalone contract, `inspect_maven_gradle_metadata`; later HEAD was not started or enumerated by this audit |
| CLI | Existing commands | Adds `rea inspect-maven-gradle-metadata PATH --json` | Registered through the same contract/service as MCP; local CLI resolves relative paths, MCP requires an absolute path |
| Tool family | Existing artifact family | New tool joins `artifacts` | No new family or provider substitution |
| Provider identity | Absent | `rea-maven-gradle-metadata`, version `1` | Bundled static reader, independent of active native providers |
| Artifact graph format IDs | 48 | 48, unchanged | `src/domain/artifactGraph.ts` and `src/artifacts/artifactFormats.ts` are byte-identical; `maven-pom` and `gradle-module` are result formats of the dedicated reader, not new artifact graph readers |
| Package version | 6.9.0 | 6.9.0 | Version text alone cannot identify this change |
| Packaged skill version | 62 | 63 | `src/generatedPackageMetadata.ts` and both skill distributions change |

The new tool takes `path` and optional `max_file_bytes`, default 1 MiB and ceiling 16 MiB. It reports artifact hash/length, literal coordinates, parent/property declarations, dependency and dependency-management rows, BOM imports, Gradle variants/rich versions, unresolved references, coverage and limitations inside the normal Evidence result. Its advertised compact schema fingerprints are input `14d15ae0b2da05c0` and output `4bda7c3651bfc579`. These are source fixtures, not a runtime schema-equality test performed here.

The reader classifies content, preserves unresolved properties and coordinate gaps, refuses malformed or unsupported documents, and enforces bounded parser/report allocations. It does not execute Maven or Gradle, resolve a transitive dependency tree, activate profiles, fetch repositories, inherit parent/BOM values, or interpret all Gradle attributes. It uses existing REA resource ownership, XML/JSON parsing and Evidence composition. No Maven/Gradle executable or additional Java runtime is required by this capability. Sources: [tool contract](https://github.com/morluto/rea/blob/bb5278c7e2d5b0a423a63858c8b3c9682232e2d2/src/contracts/java/mavenGradleMetadataToolContracts.ts), [input/result schemas](https://github.com/morluto/rea/blob/bb5278c7e2d5b0a423a63858c8b3c9682232e2d2/src/domain/java/mavenGradleMetadata.ts), [provider](https://github.com/morluto/rea/blob/bb5278c7e2d5b0a423a63858c8b3c9682232e2d2/src/java/MavenGradleMetadataProvider.ts).

No existing tool is removed or renamed in the reviewed contract delta. Existing public input/output fields were not changed by that delta; JavaScript graph validation and ownership internals do change substantially, so regenerating catalogs and rerunning schema/behavior parity remain necessary. `mcpDoctorCatalog.ts` adds expectation caching and freezing, rather than changing the intended inventory contract.

## Dependencies and packaging impact

The following were compared directly between the two Git trees:

- `package-lock.json` is unchanged, Git blob `0e7270847fa0fdba6efee77deedcef736dabd1e4`.
- `package.json` version, dependency, optional dependency, development dependency, peer dependency, engine, `allowScripts`, executable and packaged-file declarations are unchanged. Only documentation/build script definitions change: `docs:check:built` delegates to `check-doc-facts.mjs --built`, and `cursor-plugin:generate` is added.
- `.nvmrc` is unchanged; Node remains 24.22.1. `.gitmodules` and all five `third_party` gitlinks are unchanged.
- The upstream optional Frida dependency therefore still pins 17.23.2. The SDK's separately justified matched 17.25.1 override remains necessary; the later HEAD does not itself fix that provider lifecycle defect.

The later source fits the existing SDK architecture without new runtime dependencies or an REA fork. It still requires a new engine build, source archive/manifest, generated metadata/catalog and package identity evidence. The current comparison that permits only a Frida module difference is intentionally unsuitable for this larger source roll-forward; its constraints must not be weakened to pretend these engine changes are unchanged payloads.

## Five-commit behavior audit

| Commit | Source change | Effect on current evidence and follow-on checks |
| --- | --- | --- |
| `5ccb7c59` | HAR retained-body source identity and scan coverage | Base64 replay now requires the retained field to have `har-base64-content` representation and match the declared body after allowed whitespace normalization. Missing/mismatched retained sources stay unavailable; credential scanning reports incomplete coverage instead of silently treating them as scanned. This is a real correctness fix, not a new dependency or tool. |
| `05be423a` | Maven/Gradle static metadata capability | Adds the public capability/tool/CLI described above, bounded parser, shared application service, documentation, lifecycle and boundary tests. Not present in the frozen SDK. |
| `015f726a` | Prunes redundant/obsolete tests | Changes test coverage rather than adding a runtime capability. Deleted upstream tests must not be confused with removed SDK functionality. |
| `84ee604c` | JavaScript semantic graph and directory/CI performance | Adds owned/frozen provenance and prevalidated graph paths, node lookup caching, canonical-digest fast paths, shared MCP expectation caching and concurrent directory containment checks. JavaScript graph implementation changes by 716 added/106 removed lines; this deserves regression testing despite the performance intent. Directory checks still compare root identity and containment, but scheduling changes. |
| `bb5278c7` | Android boot images without final page padding | Separates last declared data byte (`dataEnd`) from page-aligned image end. Complete declared components can end before final padding; truly truncated components still fail. AVB original-size checks use declared data end and footer admission still respects aligned image placement. No new artifact format ID or tool. |

The current SDK `environment-export` fixture in `tests/main/launch/static_cases.py` supplies ordinary JSON text in a HAR response with no base64 encoding or deliberately mismatched retained body. Its real export/HTTP replay pass therefore does not exercise or disprove the HAR defect. Follow-on tests should cover matching whitespace-normalized base64, mismatched content, wrong retained role, empty-body identity and the credential-scan-incomplete result through CLI and HTTP MCP. Upstream adds those cases in `tests/boundary/cli/{analysisViewCli,environmentBuildCli}.test.ts` and `tests/boundary/mcp/environmentServeMcp.test.ts`.

The current SDK functional suite has no Android boot image fixture; its Android cases concern APK/JADX/Apktool and its firmware cases concern Binwalk/Unblob. Those passes do not establish padded or unpadded boot-image behavior. Follow-on tests should use actual unpadded boot/vendor-boot components and a one-byte-short negative input, then verify retained artifact contents and AVB handling. The later upstream adds focused format and reader cases.

The performance changes affect paths exercised by current JavaScript/application graphs, reconstruction/Evidence and directory artifact tests. Source inspection identifies the affected paths but does not prove their outputs remain identical. Repeat those semantic assertions, source identity checks, catalog/CLI parity, snapshot and Evidence persistence after any roll-forward.

## Bounded follow-on roll-forward

1. Finish and retain acceptance evidence for the frozen `51459cf` baseline. Describe this later capability and the two corrected edge cases explicitly as outside it; do not claim the active artifact includes latest HEAD.
2. Select a new immutable upstream commit in a separate reviewed change. Update the source checksum, complete-source manifest/archive, generated source identity, release provenance and baseline-sensitive test expectation in `functional.py`. Retain the original lock and the documented Frida override.
3. Add real Maven POM and Gradle module fixtures through both CLI and MCP: verify literal dependency/BOM/variant facts, unresolved references, exact artifact identity, malformed/unsupported refusal and bounded input behavior. Validate its `binary_session`/`tools/list` inclusion separately from operation execution.
4. Derive the new expected catalog and capability map from the selected source. At the observed commit, expect 79 capability groups and 260 full tools; update the 78-group guard in `tests/report-coverage.py`, skill-version evidence to 63 and affected documentation. Keep the artifact-format count at 48 unless a newly selected commit actually changes it.
5. Run the HAR/Android boot regressions above, JavaScript/directory regressions and the existing full provider, Frida, persistence and SSH checks. Build through SDKcraft, inspect the resulting artifact, install in a clean Workshop and repeat the independent reinstall. Existing binary/provider inputs may be reused only with explicit provenance; changed engine files are not the previously tested engine.

This document records a source audit and future work only. No pins, builds, containers, dependency manifests or acceptance results were changed by this audit, and no release or remote push was performed.
