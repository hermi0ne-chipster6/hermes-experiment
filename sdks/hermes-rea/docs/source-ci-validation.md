# Source maintenance validation

The SDK keeps the original repository release inventory. `sources.json` now identifies the unmodified REA source commit rather than the historical npm 6.7 package. That previous npm metadata remains under `previous_npm_release`; the old SDK npm lock is retained as published-revision history. Active source dependencies are separately captured in `release/upstream-locks/rea/` with their upstream commit and SHA-256 digests.

`release/components.json` covers every new SDK part. New source-backed parts have their exact URLs, checksums, or Git revisions checked against `sdkcraft.yaml`. Provider asset metadata, `SOURCE.json`, the active package version, the complete-source Git checkout, and the NativeAOT extension revision must agree. The complete tracked source with all five upstream submodules is retained at `upstream/rea`, separate from the production package. REA's Node 24 pin has a separate record, preserving the other SDK's existing Node pin. Frozen Python dependency files retain normal transitive package discovery. A new Git-commit monitor detects changes on REA main even when the npm/package version stays unchanged; ILSpy's platform package is monitored through NuGet's stable version index. Browser monitoring follows the pinned Playwright release and documents the required coordinated browser update. Discovery never implies compatibility approval.

Validation on 2026-11-17:

- Repository unit suite: **125 passed** as an unprivileged user in the earlier disposable Cutter source snapshot, matching hosted CI's user context; this suite was not rerun for subsequent shell/runtime dependency and non-interactive Workshop command changes (`source-unit-nonroot-cutter.log`; earlier source snapshots also passed).
- Six focused source linkage / release-monitor tests: **6 passed** (`rea-inventory-source-archive.log`; after the complete-source archive representation change).
- `ci/check.py`: **passed**, 2,051 monitored components, 72 syntax files and 30 shell scripts (`source-ci-http-final.log`, exit 0). This latest check includes the required Linux runtime tools, system executable search paths, immutable build identity, explicit non-interactive Workshop invocations with closed stdin, the model-free desktop-build fixture, and the real local HTTP MCP environment helper. New untracked source files are included because CI uses filesystem traversal.
- `git diff --check`: **passed** (`source-diff-http-final.log`, exit 0).

Running the complete suite as root leaves two unrelated heartbeat harness failures: its fixture removes `/usr/sbin` from PATH while the root-only production path executes `runuser`. Both failures were reproduced without changes at original commit `df4d649` in a detached disposable worktree (`original-heartbeat-tests.log`), and both passed unprivileged. No heartbeat or other SDK behavior was changed.

These are source CI results, separate from SDK build, installation, and provider acceptance. Logs are under `/root/dev/rea-sdk/validation-logs/`. No release was published or remote branch pushed.
