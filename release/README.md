# Reviewed SDK refreshes

Maintenance CI covers the three SDKs and their declared dependencies. The monitor
reads official GitHub releases/tags and the stable Hermes plugin catalog, PyPI/npm
metadata, Node releases, image registry digests, stable snap channels, Docker apt
metadata and Ubuntu security notices. It proposes review items; it never changes
source pins, installs candidates, merges, publishes or upgrades a running agent.

Run from this deliverable directory:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --only-binary=:all: --require-hashes -r ci/requirements.txt
python3 ci/check.py
python3 -m release.monitor --output reports/upstream-review
```

`components.json` classifies externally sourced SDK parts and tool channels;
Python/npm dependencies are extracted from every declared lock. New unclassified
parts or lock formats fail validation. Current application pins come from
`sources.json`; the primary VERSION files and source revisions must agree.

`upstream-locks/` captures Hermes' upstream npm/workspace manifests and OpenSandbox's
server uv lock/manifest from the exact selected source commits. Its provenance
records bind each input to a revision and SHA-256; local validation checks that
binding and release monitoring checks the immutable upstream bytes. Recapture these
metadata files when changing either upstream source pin. They are metadata only,
including declared build/optional dependencies, and do not install extra software.
Hermes' selected Python dependency export remains in its reviewed requirements lock.

Reports contain current/candidate identities, immutable revisions or available
digests, affected SDKs, required checks and metadata errors. An incomplete lookup
fails the monitoring job and is not interpreted as no update. Beta-only dependencies
already selected by upstream are identified separately and are not approved as
new stable candidates. A review report is not an automatic update pull request.

The Docker SDK source track is watched for changes, but that does not prove a
Store revision was published. Verify `sdk info docker-ce`, its Ubuntu 26.04 revision
and the installed Docker Engine during qualification. Canonical's current hook
installs Engine from apt, so the SDK's displayed version is not an Engine lock.

`platform-packages.json` is a nonsecret snapshot of the observed A/B/C packages.
Ubuntu notices are matched against binary/source package names since the reviewed
baseline; this is advisory monitoring, not a complete vulnerability audit. Refresh
that inventory from qualified containers after platform changes. The host kernel,
LXD configuration and dynamic OS packages still require host-specific validation.

For each candidate, review the upstream release and plugin catalog, update `VERSION`, exact source revision, dependency locks and `sources.json` together, and preserve the fixed dependency cutoff. Build A/B/C on Ubuntu 26.04 AMD64; require unit tests, SDK try/launch and Spread jobs, native plugin compatibility, complete worker routing, bridge/refresh behavior, memory continuity, heartbeat receipts and authenticated gateway checks. A skipped or blocked check is not a passing check. Keep the preceding artifact and state-compatible rollback path.

The integration workflows target `main`; see [workflow operation](workflows/README.md).
Use pull requests and required checks where the account's private-repository plan
supports enforcement. The full build workflow is manual and defaults to a blocked
preflight until the operator confirms an online disposable KVM runner. Each
publisher SDK can later adopt its own template/version-branch release layout;
this integration repository does not enable automatic Store uploads.

After reviewing successful evidence, promote the **exact tested `.sdk` artifact**,
verifying its recorded SHA-256 before upload. Use `sdkcraft upload <artifact.sdk>`
and `sdkcraft release <sdk-name> <uploaded-revision> <track>/stable`. Initial edge
publication is recorded separately; CI has no publication credentials and never
promotes a candidate. `workshop refresh` downloads the promoted SDK revision; the
runtime wrapper refuses `hermes update` and plugin install/update/remove.

Do not copy Canonical's default push-to-edge upload workflow unchanged: this experiment requires reviewed promotion. Avoid rebuilding between verification and publication. CI automation must retain the tested artifacts and their checksums, source pins, dependency inventory, and complete check outcomes.

Workshop A's registered publisher name is `hermes-experiment`; B/C remain `hermes-execution` and `hermes-rea`. Use the current [publishing commands](publishing.md) and `reports/SHA256SUMS`, rather than an earlier `hermes-agent` SDK archive. This SDK rename does not rename the official upstream repository.
