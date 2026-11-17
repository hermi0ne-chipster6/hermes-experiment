# Frida and subprocess sequencing validation

The pinned Frida 17.23.2 native dependency breaks ordinary Node child completion after a local Frida spawn in the installed environment. An owned compatibility runtime using the complete official Frida 17.25.1 package and matching native binding passes the direct reproducer and the mixed REA MCP sequence. REA engine source was not patched. This records candidate-runtime validation; the final SDK must package that correction and pass its installed acceptance suite before these results become final-package acceptance.

## Observed failure and source trace

The fresh full-suite run passed 16 cases through `frida-injection`, then stalled at `inspect_sqlite_database`; the later in-process managed case also passed, giving 17 completed passing cases overall; `/root/dev/rea-sdk/validation-logs/final-functional.log` retains the last completed cases. The primary observed an unreaped `ps` child. Upstream `SqliteDatabaseWorkerExecution.ts` launches its worker through `runOwnedCommand`; `spawnOwnedProviderProcess` performs ownership inspection, and `ProcessOwnershipObservation.ts` obtains process information using asynchronous `ExecFileOutput` calls to `ps`. That subprocess layer waits for real child/stdio completion, including during cancellation. Missing exit events can therefore prevent SQLite admission or cleanup from settling. This source trace explains the symptom; the direct dependency test below isolates it without loading REA or SQLite.

[Frida's issue 121](https://github.com/frida/frida-node/issues/121) reports the corresponding Linux problem: GLib's child watch replaces the application's SIGCHLD handler, then resets it when the watch is removed, disrupting libuv child reaping. [The official GLib fix](https://github.com/frida-forks/glib/commit/c366177b9292432a26f6903fa82a71d83e4927eb) enables pidfd support despite older build headers. [Frida 17.25.0 release notes](https://frida.re/news/2026/10/30/frida-17-25-0-released/) include that correction. The tested candidate is 17.25.1, using its complete package and matching binding, without modifying the REA engine.

## Direct dependency comparison

Both runs used Node **24.22.1**, the same owned two-second native fixture (SHA256 `83ccd4239a776153336741b1f373e46703e246b927adcf4ccf38ce6c25e413e1`), and `frida_process_probe.mjs`. The probe loads Frida directly and checks `ps` and ordinary Node children before and after import, discovery, spawn, attach, injection, unload, resume, detach and target exit. A separate owned Node sentinel stays alive throughout, preventing libuv from masking the defect by reinstalling its child handler after becoming idle. The sentinel is explicitly terminated and its exit is required.

| Runtime | Records | Failures | Result |
| --- | ---: | ---: | --- |
| Installed Frida 17.23.2 | 37 | 15 | Child checks fail from the Frida-spawn stage onward; sentinel cleanup receives no exit event |
| Candidate Frida 17.25.1 | 37 | 0 | All 24 child checks and the Frida/sentinel lifecycle complete |

Baseline `SigCgt` was `0000000100014602` before import and `00000001004056c2` after target exit: SIGCHLD bit 16 was lost. Candidate `SigCgt` was `0000000100014602` before import and `00000001004156c2` after target exit: that bit remained set. The baseline's first failures already occurred at spawn while the caught bit was still set; this bitmap alone cannot distinguish the application's handler from a replacement handler. The child exit/close observations, rather than the bitmap alone, establish the operational failure.

Raw results and `final.json` files are under `/home/rea-sdk-dev/.local/share/workshop/id/782b8b9c/validation-final/mount/hermes-rea/state/work/frida-process-baseline/` and `frida-process-fixed/`. Baseline duration was 63,822 ms with 15 failures; corrected duration was 5,578 ms with zero failures. Independent read-only review recomputed the check counts and examined the before/after signal masks.

Candidate preparation evidence: `/root/dev/rea-sdk/validation-logs/frida-fixed-preparation.log` records 3,550 unchanged engine files verified and native binding SHA256 `ac4e786dcadb35f1717bc44ab1ec92ee439a3f606bcc016fdeb9bd1cbc4aa665`. `/root/dev/rea-sdk/validation-logs/frida-fixed-downloads.json` records official package archive SHA256 `81c475d3425a3748007efdc80ebd2c747a44694627e2aab11999675536f9ec04` and native release archive SHA256 `28f6bf3a8926288ffe79f415777256a37213c2d217cdab4ee81b225b096854bb`. The candidate lived under `/var/lib/hermes-rea/work/frida-fixed-runtime`; the installed immutable SDK was not modified for this comparison.

## Mixed MCP result

The candidate then passed JavaScript analysis → Frida enumeration → real owned-process Frida injection → SQLite inspection → explicit Ghidra analysis and snapshot reopen in one MCP process. All **5 cases passed**, and `/root/dev/rea-sdk/validation-logs/frida-mixed-fixed.exit` is `0`. The sequence and raw responses are retained in `/root/dev/rea-sdk/validation-logs/frida-mixed-fixed.log` and `/home/rea-sdk-dev/.local/share/workshop/id/782b8b9c/validation-final/mount/hermes-rea/state/work/frida-mixed-fixed/`. SQLite completed in 2.210 seconds after Frida injection; Ghidra completed in 197.820 seconds. This proves the previously stalled provider sequence works with the tested dependency correction; it does not replace the complete final installed suite.

## Durable case

`tests/main/launch/frida_lifecycle_case.py` exports:

```python
run_frida_lifecycle(package_root, output, work)
```

The primary shared runner registers it as `frida-process-lifecycle`. The provider Spread task maps its `frida_process_lifecycle` variant to that case and copies both `*.py` and `*.mjs` from the launch directory. Its prepare step installs test-only GCC/libc headers. The complete runner also retains Frida injection immediately before SQLite inspection in the same MCP process, independently exercising the original mixed-provider failure. The case compiles a private, owned two-second ELF using test-only GCC/libc headers. It derives the installed Node executable from `package_root.parents[2] / "node/bin/node"`, rather than using host PATH, and invokes the probe in a new owned process group with a 180-second deadline. A timeout terminates only that group.

Acceptance requires exit code zero, completed `final.json` with no failed checks, every recorded status passing, exactly the expected 24 child-process probes across all 12 stages, successful Frida operation records, and sentinel start/cleanup surrounding the before/after checks. Both pre-import and post-target-exit child checks must retain SIGCHLD's caught bit while the sentinel is alive. Each child must emit its successful exit and complete without timeout. The result includes Node/Frida versions, fixture hash, native binding hash and retained output paths.

The initial helper validator accepted the corrected historical 37-record run and rejected the 15-failure baseline. The strengthened validator described below additionally requires explicit target-exit evidence and therefore intentionally rejects historical runs lacking that receipt. The wrapper itself still requires execution against the corrected installed SDK; candidate-runtime success does not waive that gate. No shared runner, Spread wiring or package definition is changed by this helper's source commit.


## Final acceptance review

Independent read-only review recomputed the retained outcomes: initial installed run **17 passed**, one observed SQLite sequencing failure and **81 aborted/unexecuted cases**; a fresh MCP run completed **81 of 82** selected remaining cases. Its desktop fixture decoder failure was corrected and the real desktop rerun passed separately. The interrupted run's machine-readable 82 failure rows must not be described as 82 independently executed failures. Neither the split runs nor the five-case compatibility-runtime pass establish a complete final-package pass.

The direct probe's original fixed 2.5-second delay did not explicitly observe target exit. The follow-up correction captures the owned target's PID and `/proc` starttime immediately after spawn, waits up to 10 seconds for its `/proc` entry to disappear or reach an exited state, and rejects PID reuse. It records `owned-frida-target-exit` before any post-exit child checks; the Python validator requires that receipt and the captured identity. A complete successful corrected run therefore has 38 records instead of the historical 37. Node syntax and Python compilation passed; seven controlled checks covered unusual process names, missing entries, zombie/dead states, PID reuse, deadline expiry, access errors and malformed records. Actual execution of the strengthened case remains required. This correction strengthens the regression; it does not invalidate the historical baseline failure.

A corrected artifact must independently prove its installed complete Frida package version and binding hash, run this direct lifecycle case, and complete the same-process Frida → SQLite sequence in the complete suite. Retain clean MCP shutdown and exact runtime provenance alongside the result. An earlier preflight exit code alone cannot establish which artifact is currently installed.
