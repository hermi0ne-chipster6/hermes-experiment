# Final MCP acceptance review

This review inspected the primary source and retained results on 2026-11-17 without running or modifying Workshop, LXD, package managers, SDKcraft builds or shared tests. The SDK remains `hermes-rea`, upstream commit `51459cf203ae1eb6b586a95b21899eaa0f631823`. Final corrected-artifact acceptance remains pending.

## Verified scope

| Evidence | Actual result | Boundary |
| --- | --- | --- |
| Cold-built `c7373502…` installed functional catalog | 259 tools; `binary_session` inventory and packaged canonical contracts match | Session and catalog operation; not every tool operation |
| Historical `77fc26d…` network SSH | 6/6 passed, actual native ADD/RET and Ghidra pseudocode, bounded artifact transfer, shell refusal 64, forwarding refusal 255 | Existing installation; subsequent HOME/shell correction rerun also 6/6 |
| Historical refresh persistence | Both phases passed after change 56 Done, worker Ready; exact hashes, Evidence equality and explicit snapshot replay | Stored analysis data; live processes do not persist |
| Installed Frida 17.23.2 direct probe | 37 records, 15 failures, lost post-exit SIGCHLD handling | Reproduced dependency defect without REA |
| Compatibility Frida 17.25.1 direct probe | 37 records, zero failures, 24 child checks and sentinel cleanup | Scratch runtime with unchanged REA engine; not final installed SDK |
| Compatibility mixed MCP | JavaScript → Frida enumeration → injection → SQLite → Ghidra, 5/5 passed | Real same-process operations; complete suite still required |

Raw catalog result: `/home/rea-sdk-dev/.local/share/workshop/id/782b8b9c/validation-final/mount/hermes-rea/state/work/sdk-validation-final/results.json`. Direct and mixed results are adjacent under `frida-process-baseline`, `frida-process-fixed` and `frida-mixed-fixed`. SSH results and shutdown receipts are under `/root/dev/rea-sdk/validation-logs/ssh-network-installed/` and `ssh-network-home-fixed/`. Both SSH MCP shutdown receipts record stdin EOF and exit 0.

## Regression wiring and cleanup

The primary `functional.py` imports `run_frida_lifecycle` and registers `frida-process-lifecycle`. The provider Spread task has a matching variant and `CHECK` mapping, copies Python and MJS helpers, and installs the fixture compiler. The main functional loop independently retains Frida injection immediately before SQLite in the same MCP process; the direct diagnostic does not replace that check.

The diagnostic uses the installed Node runtime and complete installed Frida module. A separate owned Node sentinel keeps libuv's child watcher alive while Frida creates and exits its target. Checks require normal child exit/close observations at 12 stages; mere signal-bit presence is insufficient. Its Python wrapper creates an owned process group and bounds execution at 180 seconds. The JS probe bounds individual operations, attempts script/session cleanup and resumes a suspended finite fixture on failure. Sentinel cleanup must emit an actual exit event. Retained native binding, fixture and version hashes identify the tested runtime.

The review found that a fixed 2.5-second delay could label a still-running target as exited under resource contention. The scoped correction now captures PID/starttime at spawn, observes disappearance or an exited state within 10 seconds, rejects PID reuse, and records termination before post-exit checks. The validator binds the exit to the captured identity. Seven controlled parser/exit/error checks, Node syntax and Python compilation pass; the strengthened case still needs actual installed execution.

## Prepared final script review

`validation-logs/final-persistence-and-ssh.sh` has the correct broad order: prepare durable Evidence/snapshot, configure the read-only public allowlist, add an inert SDK to force an applied refresh, verify persistent replay, run local SSH boundary checks, prepare startup probes, run actual authenticated SSH, verify/clean startup probes. It preserves private keys on the host and pins the worker's public host key through direct local LXD inspection. Normal SSH test failure still runs probe verification/cleanup.

Before using it for the final corrected artifact, the primary operator should make these bounded changes:

1. Gate on a new installed-identity receipt matching the final artifact, complete Frida package and native binding hashes, and current source hooks. The existing `final-preflight.exit == 0` belongs to an earlier installation and is insufficient by itself.
2. Read the catalog from the current final-artifact functional run and require its full suite's selected cases to pass. The hard-coded `sdk-validation-final/tools-list.json` currently belongs to `c7373502…`. Catalog equality across builds is useful but cannot identify an installed build.
3. Keep project, definition, container selector, output state and SSH helper paths consistent if the final environment changes. The current scripts target only `/home/rea-sdk-dev/integration-final`, `validation-final`, and the unique `validation-final-` LXD instance.
4. Retain changes/tasks/info after each stop, remount, start and refresh mutation, including the actual refresh change ID and Ready state. Require the ephemeral witness to disappear naturally after applied refresh; do not delete it manually.
5. Add an interruption cleanup trap after successful startup-probe preparation. The current normal network-failure path cleans up, but a shell interruption between preparation and verification can leave the harmless probe files. The existing explicit helper `cleanup` phase preserves unrelated files and can be used by the trap.
6. Use fresh output directories and preserve earlier attempts. The persistence/startup helpers intentionally refuse overwrites. Capture each phase's result receipt as well as command exit status.

No shared script was modified by this review. These requirements are local validation corrections; they do not call for upstream engine changes or additional infrastructure access.

## Completion gates

The final report should join immutable artifact identity with: successful SDKcraft build and registration, clean Workshop installation, runtime identity and dependency checks, a complete single-process provider suite including the Frida sequencing regression, fresh persistence/SSH/startup evidence, and independent clean reinstall. The VM-backed SDKcraft test limitation caused by unavailable `/dev/kvm` remains a reported infrastructure limitation; alternate passing container tests do not turn aborted VM jobs into passes.

Catalog exposure, actual provider behavior and external-provider availability must remain separate. Licensed tools, physical devices and configured external model services are not proven by these tests. No release publication or remote Git push is part of this review.
