# Verification records

This repository preserves the reviewed [verification summary](verification.md),
[artifact metadata](artifacts.json), [published SDK checksums](SHA256SUMS), and
[Store publication record](publishing/publication.md).

These records describe the builds and checks completed before this repository
was created on 2026-11-01. Their historical statements about Git and CI describe
that earlier environment. Creating this repository does not activate workflows,
run the blocked VM tests, promote a stable SDK, or activate the experiment.

Raw diagnostic logs, generated analysis results and local Workshop/Spread state
are excluded from Git. Some historical links therefore refer to evidence kept
on the original development machine. Keep that evidence separately; a clone is
not a complete copy of the original test machine.

The `.sdk` packages named by `SHA256SUMS` are also excluded from Git. They were
published to the SDK Store; retain the exact tested packages separately when
verifying checksums or reproducing archive comparisons. Rebuilding source does
not by itself prove a byte-identical artifact.

Use synthetic data for future checks, review logs for credentials before sharing,
and record passing, failing, blocked and skipped checks separately. Outstanding
stable-release and deployment checks remain in `verification.md`.
