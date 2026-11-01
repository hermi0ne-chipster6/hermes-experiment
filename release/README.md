# Reviewed SDK refreshes

The detector reads only official NousResearch releases and resolves the selected stable tag to its immutable commit. It uses publication chronology because historical calendar tags would outrank newer `v0.x` releases if sorted numerically. It writes a proposal; it never edits installed Hermes, changes source pins, installs software or publishes anything.

Run from this deliverable directory:

```bash
python3 release/detect.py --output reports/release-candidate.json
```

Local verification returned no newer stable release than the pinned v0.22.5. Test fixtures cover prereleases, drafts, moved tags, invalid revisions and historical calendar tags.

For each candidate, review the upstream release and plugin catalog, update `VERSION`, exact source revision, dependency locks and `sources.json` together, and preserve the fixed dependency cutoff. Build A/B/C on Ubuntu 26.04 AMD64; require unit tests, SDK try/launch and Spread jobs, native plugin compatibility, complete worker routing, bridge/refresh behavior, memory continuity, heartbeat receipts and authenticated gateway checks. A skipped or blocked check is not a passing check. Keep the preceding artifact and state-compatible rollback path.

The workflow templates are opt-in and remain inactive in this integration repository. Configure a protected integration branch before enabling detection. Package each publisher SDK from its own version branch, with `main` reserved for its template; do not commit `VERSION` to that publisher template branch. Configure the branch protection and required checks before promotion. A candidate should never promote itself or consume Store credentials during an unreviewed build.

After reviewing successful evidence, promote the **exact tested `.sdk` artifact**, verifying its recorded SHA-256 before upload. SDKcraft's verified command shapes are `sdkcraft upload <artifact.sdk>` and `sdkcraft release <sdk-name> <uploaded-revision> <track>/stable`. These publication commands were inspected with `--help`, not executed. Store names/tracks, credentials and promotion remain operator-controlled setup. `workshop refresh` then downloads the promoted SDK revision; the runtime wrapper refuses `hermes update` and plugin install/update/remove.

Do not copy Canonical's default push-to-edge upload workflow unchanged: this experiment requires reviewed promotion. Avoid rebuilding between verification and publication. CI automation must retain the tested artifacts and their checksums, source pins, dependency inventory, and complete check outcomes.

Workshop A's registered publisher name is `hermes-experiment`; B/C remain `hermes-execution` and `hermes-rea`. Use the current [publishing commands](publishing.md) and `reports/SHA256SUMS`, rather than an earlier `hermes-agent` SDK archive. This SDK rename does not rename the official upstream repository.
