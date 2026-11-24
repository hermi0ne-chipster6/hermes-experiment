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

1. Complete the broader candidate qualification and human review of the
   implementation PR. Start hosted rehearsal after the reviewed workflows
   reach the default branch. Confirm that the repository plan supports the
   required ruleset and that repository writers are trusted to publish Actions
   statuses. The expected status source identifies the GitHub Actions App.
   Repository writers can change workflow token permissions.
   [Manual workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch)
   [Actions token permissions](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#setting-the-permissions-of-the-github_token-for-your-repository)
2. Register a dedicated disposable Ubuntu 26.04 AMD64 runner with
   `self-hosted, linux, x64, hermes-sdk-build`. It needs Workshop, SDKcraft, LXD,
   passwordless build privileges and enough capacity. Spread's VM tests need
   working KVM. Run Workshop as the dedicated non-root runner user. Restrict
   admission to the reviewed reusable workflow on `main` through the runner
   group or equivalent enforced isolation. A label is only a scheduling
   selector. Keep the runner and test state disposable.
3. Keep repository auto-merge disabled for the controlled human rehearsal.
   With operator authorization, activate a strict `main` ruleset with an empty
   bypass list. Block force pushes, require pull requests and require the exact
   `Hermes stable release qualification` status from the GitHub Actions App.
   Require branches to be up to date before merging. The human finalizer needs
   this active rule before it can publish success. Check the empty bypass list
   in repository settings because GitHub omits it from the workflow token's
   ruleset response. If GitHub requires a recent result for this context before
   activating the rule, record the setup blocker and keep hosted proof pending.
   The ruleset API exposes the literal context and integration ID. Acceptance
   of an unused context must be verified on the target.
   [Ruleset API](https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset)
   [Required status prerequisites](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)
4. Qualify a controlled in-scope human PR, such as a change to the existing A
   SDK README. Verify the successful required status and run URL on the exact
   reviewed head and confirm the tested target SHA in the run inputs and jobs.
   Confirm manual merge eligibility with the PR's `auto_merge` unset. Check
   that failed or stale results cannot publish success. Activating the rule
   also blocks out-of-scope changes to `main`, including workflow fixes.
   Arrange a trusted broader qualification route before leaving the rule active
   beyond the operator-approved rehearsal.
5. After rehearsal, authorize GitHub Actions to create pull requests and enable
   squash merges and repository auto-merge for the controlled release-bot
   proof. The workflow uses a temporary `GITHUB_TOKEN` with job-scoped
   permissions. Select required contexts the unattended path can produce
   directly because bot-triggered PR event checks can require approval.

## Qualify a reviewed human PR

After the reviewed workflow is on `main`, a repository maintainer can dispatch
it with the exact reviewed same-repository PR head and current target. Update
the PR with current `main` and review its resulting head before dispatch.
This route covers existing Workshop A launcher, bootstrap, identity,
configuration, dependency reconciliation, and README edits. Changes
to other SDKs, the qualification harness, or shared composition require
the broader candidate acceptance matrix.

```bash
gh workflow run qualify-human-pr.yml --ref main \
  -f pr=PR_NUMBER -f reviewed_head=REVIEWED_HEAD -f target_base=CURRENT_MAIN
```

The workflow checks operator permissions, ancestry, head and target before
building. It marks the required Actions status successful for the reviewed
commit only after full qualification and another freshness check. Operator review and
manual merge follow the result. The release workflow remains the separate path
for bot-generated release PRs.

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
