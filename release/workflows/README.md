# SDK maintenance workflows

- `checks.yml` runs repository source checks on pushes and pull requests.
- `releases.yml` monitors declared upstreams at minute 17 every six hours. It
  retains JSON and Markdown review reports and processes compatible stable
  Hermes candidates from trusted `main`.
- `sdk-qualification.yml` runs source checks and Workshop A SDK qualification
  for the exact candidate and target commits. It can run within the release
  workflow without waiting for PR event approval.

Stable releases use the official Nous Research GitHub release ID, tag,
publication timestamp and resolved commit. Discovery follows all release pages.
It excludes drafts, prereleases, canaries and legacy calendar tags. Newly
observed versions above the installed pin queue in version order. Before
generating candidates, the workflow records every observed identity on the
`release/hermes-state` branch by fast-forward push. The state branch holds
metadata only. This preserves the first resolved commit even when candidate
generation or PR creation fails. Preserve that branch's history and block
force pushes and deletion where branch protection is available.

The workflow opens one PR per queued release and qualifies the oldest candidate
first. It also retains merged identities in `release/hermes-stable-history.json`.
Ledger divergence, missing metadata, changed release IDs and moved tags stop
preparation. A competing update to the state branch can reject a push. The
next run reloads the branch before proceeding.

The generator updates Workshop A pins, its dependency locks and upstream
provenance. It leaves Workshop B, Workshop C and independently managed plugins
alone. A candidate built on an older target is regenerated, and the existing
bot branch is updated with a Git lease only when its previous contents match
deterministic generation. Closing a failed candidate stops automatic processing
at that release until an operator resolves it.

GitHub places opened, reopened and synchronized PR workflows triggered by
`GITHUB_TOKEN` in an approval-required state. The trusted release workflow calls
SDK qualification directly. Its finalizer verifies the authenticated GitHub
Actions bot identity, exact head and base, official commit and allowed files.
It sets the required status to pending, enables GitHub auto-merge for that PR
and publishes success only after full qualification and a fresh head/base check.
Strict branch protection stops GitHub from merging after the target moves.
[GitHub token events](https://docs.github.com/en/actions/concepts/security/github_token)
[GitHub auto-merge](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/automatically-merging-a-pull-request)

## One-time repository and runner setup

1. Allow GitHub Actions to create pull requests. Enable auto-merge and squash
   merges. The release workflow uses the repository's temporary
   `GITHUB_TOKEN` with job-scoped permissions.
2. On an eligible GitHub plan, activate a ruleset for `main` with no bypass
   actors. Block force pushes, require pull requests and require the exact status
   `Hermes stable release qualification` from the GitHub Actions App, with the
   requirement that branches be up to date before merging. The ruleset also
   applies to human PRs, which need the same qualification status from a
   trusted operator workflow. PR-event checks for Actions-created PRs require
   approval, so avoid requiring those contexts for unattended candidates.
   GitHub omits the bypass list from the workflow token's ruleset response.
   Keep that list empty in the repository settings. The finalizer uses GitHub's
   ordinary auto-merge operation and checks the effective strict status rule.
3. Register a dedicated disposable Ubuntu 26.04 AMD64 runner with
   `self-hosted, linux, x64, hermes-sdk-build`. It needs Workshop, SDKcraft, LXD,
   passwordless build privileges and enough capacity. Spread's VM tests need
   working KVM. Restrict the runner to trusted jobs and use synthetic state.

Repository automation updates the observation branch and release PRs and uses
GitHub auto-merge for qualified candidates. The exact tested SDK artifact,
its checksum and the last-known-good artifact are needed for separately authorized Store
publication and Workshop refresh. See [publishing](../publishing.md).

## Exact artifact and rollback

Keep the current working A package in the runner's
`/var/lib/hermes-sdk-qualification/last-known-good/` directory as
`hermes-experiment_amd64_ubuntu@26.04.sdk` with its relative-path entry in
`SHA256SUMS`. Use a reviewed offline copy of that directory for recovery. The
runner checks the checksum before using the package and runs the upgrade,
restart, refresh and downgrade against a disposable Workshop. Retain the
workflow evidence and exact candidate package independently of GitHub's artifact
retention before moving the last-known-good pointer.

If rolling back to the original 0.22.5 package, preserve the writable
`.hermes/config.yaml` under a separate name in the same state mount and restore
the prior symlink to the read-only operator seed before swapping the SDK. Keep
the original seed and charter mounts. Restore the saved writable profile when
returning to the newer package. Keep the Hermes, Hindsight, Sui and Link mounts
connected to their existing sources throughout.
