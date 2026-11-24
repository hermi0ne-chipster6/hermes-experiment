# SDK maintenance and release qualification

Maintenance CI covers the three SDKs and their declared dependencies. The monitor
reads official GitHub releases/tags and the stable Hermes plugin catalog, PyPI/npm
metadata, Node releases, image registry digests, stable snap channels, Docker apt
metadata and Ubuntu security notices. This monitor produces review reports.
The stable Hermes pipeline additionally generates pinned Workshop A upgrade PRs
and enables GitHub auto-merge after full qualification.

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

`upstream-locks/` captures Hermes' upstream pnpm and uv locks and workspace manifests and OpenSandbox's
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

The Hermes core candidate generator updates `VERSION`, the exact upstream
revision, frozen locks and `sources.json` together. Qualification runs on a
dedicated Ubuntu 26.04 AMD64 host. It covers source checks, SDK packaging and
startup, Spread, native tools and plugins, persistence, rollback and Workshop A's
integration boundaries. Updates to other components remain subject to review
and qualification of affected SDKs. Keep the preceding tested artifact and its
state-compatible rollback procedure. See [workflow operation](workflows/README.md)
for repository protection, runner setup and bot authentication.

After reviewing successful evidence, promote the **exact tested `.sdk` artifact**,
verifying its recorded SHA-256 before upload. Use `sdkcraft upload <artifact.sdk>`
and `sdkcraft release <sdk-name> <uploaded-revision> <track>/stable`. Initial edge
publication is recorded separately; CI has no publication credentials and never
promotes a candidate. `workshop refresh` downloads the promoted SDK revision; the
runtime wrapper directs `hermes update` to the SDK release and refresh process.
Hermes' native plugin commands manage operator-installed plugins independently.

Do not copy Canonical's default push-to-edge upload workflow unchanged: this experiment requires reviewed promotion. Avoid rebuilding between verification and publication. CI automation must retain the tested artifacts and their checksums, source pins, dependency inventory, and complete check outcomes.

Workshop A's registered publisher name is `hermes-experiment`; B/C remain `hermes-execution` and `hermes-rea`. Use the current [publishing commands](publishing.md) and `reports/SHA256SUMS`, rather than an earlier `hermes-agent` SDK archive. This SDK rename does not rename the official upstream repository.
