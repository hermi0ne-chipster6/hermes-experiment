# Hermes REA parity implementation and validation

This work continues the existing `hermes-rea` SDK in `hermi0ne-chipster6/hermes-experiment`, starting at `df4d649`. The user authorized implementation and disposable local environments; publication and remote pushes are excluded.

## Baseline and architecture

Published SDK: revision 1, 6.7.0, latest/edge, Ubuntu 26.04 amd64. Current upstream inspected: `51459cf203ae1eb6b586a95b21899eaa0f631823` (package version 6.9.0). The npm release and repository main must be compared; equal version strings do not imply equivalent capabilities.

Keep SDKcraft dump/build parts, five-hook lifecycle conventions, the persistent state mount, and restricted SSH transport. Add a local `rea` launcher preserving upstream arguments and environment overrides. Runtime apt dependencies belong in setup-base; independently pinned assets belong in immutable SDK parts. Do not replace unavailable providers or fork upstream.

## Work and verification

- [x] Locate original source/history and published revision; create dedicated local branch.
- [x] Read Canonical skills and inspect current upstream source.
- [x] Record exhaustive source-derived capability/dependency matrix, distinguishing runtime evidence from registration (historical installed results recorded; corrected artifact acceptance pending).
- [x] Reproduce existing build and runtime gaps.
- [x] Pin upstream baseline and provider artifacts; correct CLI/environment wiring and missing dependencies (final integration may reveal further corrections).
- [x] Extend functional tests with synthetic inputs and exact MCP inventory/session checks.
- [x] Build complete SDK with SDKcraft and consume `try-hermes-rea` in a fresh Workshop.
- [ ] Accept the final Frida compatibility artifact with strict archive comparison and a new full operational run.
- [x] Exercise diagnostics, native/JS/managed/Android/firmware/runtime operations, real desktop lifecycle, and persistence; retain provenance and failures.
- [x] Attempt SDKcraft Spread and record missing-KVM allocation failure (0 passed, 91 aborted); current discovery97 jobs passes.
- [ ] Execute the official VM jobs on a supported KVM host; unavailable on this VPS.
- [ ] Repeat installation in a second fresh environment and run regression checks.
- [ ] Save artifacts/checksums, final capability evidence, reviewable diff, and proposed release steps.

## Review focus

Validate real native module loading, lazy provider startup, version admission, caller-selected provider overrides, clean stdio framing, missing licensed providers, state ownership after mount/refresh, and complete catalog versus any deliberately filtered MCP profile. A working tool listing alone is never evidence of analysis functionality.

Long-running commands execute in tmux session `hermes-rea-validation`; host logs are in `/root/dev/rea-sdk/validation-logs`. Tests use synthetic owned fixtures and no external VPS.
