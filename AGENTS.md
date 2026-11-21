# Agent instructions for Hermes Experiment

Applies throughout `hermi0ne-chipster6/hermes-experiment`. Read this file and any
more specific agent instructions before editing. Follow the user's current task;
these standing requirements do not expand a documentation task into implementation
or deployment work. Current user instructions take precedence.

## Read the existing project first

- Inspect the working tree, target branch, relevant PR diff and discussion before
  editing. Preserve unrelated work. Continue draft PR #3 on
  `fix/hermes-sdk-runtime-extensibility` when working on that implementation;
  do not start a replacement implementation or merge it without authorization.
- Start with `README.md`, `sdks/hermes-experiment/`, `sources.json`,
  `release/{README.md,components.json,inventory.py,monitor.py,detect.py}`,
  `.github/workflows/`, `ci/check.py`, relevant `tests/` and `validation/`,
  and the deployment examples. Consult `release/publishing.md` and
  `reports/README.md` for artifact identity and evidence limits.
- Older README, deployment, CI design and test statements reflect an earlier
  restrictive design. The requirements below supersede requirements to disable
  native tools, require B for all execution, rebuild the SDK for plugin changes,
  qualify only manually on `main`, or keep all release PR merges manual.
  Reconcile affected code, tests and current docs together during implementation;
  preserve historical verification records as historical evidence.

## Architecture and runtime requirements

- Workshop A uses `sdks/hermes-experiment/`, publisher name `hermes-experiment`
  and local name `try-hermes-experiment`. Keep official Hermes core immutable,
  version-pinned and reproducible through SDKcraft.
- Workshop B (`sdks/hermes-execution/`) supplies optional external OpenSandbox
  execution. Workshop C (`sdks/hermes-rea/`) supplies optional external REA
  analysis. Preserve their connection configuration; neither replaces or disables
  A's native tools. A's native CLI must work independently of B/C availability.
  A failed explicit remote operation must report failure rather than silently
  changing its execution target.
- Preserve native terminal, filesystem, browser, code execution, skills and other
  supported Hermes capabilities inside A. Use upstream configuration syntax and
  permission mechanisms. Remove SDK-imposed broad tool restrictions without
  overwriting operator preferences or expanding unattended Buzz/email/cron
  permissions merely to restore interactive CLI functionality.
- Support native plugin install, update, enable, disable and removal independently
  of SDK rebuilds. Keep plugin files, resolved dependencies, package-manager state
  and installation metadata in writable persistent locations. Record plugin
  versions/source revisions separately from core pins. Core releases must not
  silently update independently managed third-party plugins.
- Verify upstream packaged-install behavior and dependency-environment activation.
  The bootstrap and wrapper must use the supported plugin dependency environment
  without writing into the immutable SDK payload. Do not add a parallel plugin
  manager or a custom permission/approval framework.
- Core upgrades remain SDK-managed: keep `hermes update` from modifying the
  packaged core while allowing native plugin operations.
- Keep configuration, plugins, dependency environments, conversations, memories,
  Hindsight/pg0, credentials and integration state persistent across restart and
  SDK refresh. Inventory actual mounts and paths, including
  `/home/workshop/.hermes`, `.hindsight`, `.sui`, `.link-cli` and the
  `.pg0` link. Preserve established secret delivery.
- Migrate the former `/etc/hermes-experiment/config.yaml` symlink into the
  persistent profile safely, idempotently and reversibly. Keep a recovery copy,
  preserve user edits and remove only identified SDK-imposed legacy restrictions.
  Handle bundled-plugin symlinks without overwriting user-managed plugins or
  re-enabling deliberately disabled plugins.

## Repository work and scope boundaries

Proceed with requested repository edits and disposable non-production tests
without recurring permission requests. Keep changes focused on the task.

- Do not access, refresh, recreate, remove or otherwise change live A/B/C Workshops
  or a live VPS for development or tests. Do not change host users, production
  networking, DNS, credentials, gateways or heartbeat services as a side effect.
- SDK Store upload/release/promotion and live Workshop refresh are separate,
  manual operator-authorized actions. A commit, green CI or automatic merge does
  not authorize any of them.
- Do not change the separate B/C SDKs unless a demonstrated compatibility issue
  requires a separately reviewed change. Do not rebuild them for every A-only
  update. Preserve unrelated diary, memory, financial and messaging behavior.
- Preserve the existing runtime charter and upstream `SOUL.md`; do not invent
  additional governance, restrictions or infrastructure to perform routine work.
  Existing wallet/transaction policies and operator-selected permissions remain.
- Keep secrets, private keys, runtime databases, local Workshop state, raw
  diagnostics and built `.sdk` packages out of Git. Use synthetic fixtures;
  redact access-bearing values from logs, artifacts and reports.
- Ask for missing access or credentials, genuinely unresolved requirements, or
  actions outside the authorized scope. Explain the concrete blocker and the
  smallest operator action needed; continue independent repository work.

## Coding and reproducibility standards

- Follow existing Python, shell, YAML and unittest conventions. Prefer the
  standard library and existing pinned dependencies over new frameworks.
  Keep shell arguments quoted, propagate exit status, bound external operations
  and make hooks/migrations repeatable without destroying existing state.
- Upgrade to the latest verified compatible official stable Hermes release when
  core upgrade work is requested. Pin the release tag and exact resolved commit;
  never build a moving branch or infer compatibility from a version number.
- Update `VERSION`, `sources.json`, SDKcraft recipes, dependency inputs/locks,
  `release/upstream-locks/` provenance, installation stamps, health checks and
  version assertions consistently. Derive identity checks from recorded pins;
  do not weaken them to a generic "Hermes Agent" string match.
- Follow the pinned upstream Web UI/TUI toolchain, including its required pnpm
  version, workspace names and frozen lockfile for releases using pnpm. Do not
  blindly translate npm commands. Extend inventory validation for new lock
  formats and recapture metadata/digests from the selected source revision.
- Preserve frozen/hash-verified dependencies and document any necessary change
  to the existing dependency cutoff or exclusion. Resolve native browser
  dependency conflicts rather than retaining a blanket capability exclusion.
- Keep shared `diary/hermes_diary/` code and packaged copies under
  `sdks/hermes-experiment/assets/diary/` consistent when changing that code.
  Preserve dependency licenses and notices.
- Pin GitHub Actions and downloaded tools as the repository does. Give each job
  only the permissions needed for its operation; release-PR creation needs
  narrowly scoped writes, so the old blanket read-only validator must evolve.
  Keep production and Store credentials out of qualification jobs.

## Testing and SDK qualification

Use the repository's existing checks. In an isolated environment with supported
Python and the locked CI dependencies, the source-check commands are:

```sh
python3 -m pip install --only-binary=:all: --require-hashes -r ci/requirements.txt
python3 -m unittest discover -s tests -v
python3 ci/check.py
actionlint -color
gitleaks git . --redact=100 --no-banner
```

`ci/check.py` includes inventory/configuration parsing and ShellCheck.
`ci/install-tools.py` installs the repository-pinned actionlint/gitleaks tools.
Run checks appropriate to the change; documentation-only edits need file/diff
validation and accurate CI reporting, not a fabricated SDK qualification.

For runtime, packaging or release changes:

- Add meaningful behavior/regression tests. Update obsolete tests that enforce
  superseded restrictions; retain coverage for real operator preferences,
  invalid configuration, core immutability and credential handling. Do not
  delete or skip failing tests just to make CI green.
- Use a dedicated non-production Ubuntu 26.04 AMD64 qualification host. Verify
  actual runner registration/online status, `self-hosted, linux, x64,
  hermes-sdk-build` labels, Workshop, SDKcraft, LXD, build privileges and capacity.
  A readiness input is not evidence that a runner is online.
- Run the existing `sdkcraft clean`, `sdkcraft try --build-for amd64`,
  `sdkcraft test --list` and `sdkcraft test` workflow from the affected SDK
  directory on that host. Run heavy builds sequentially. KVM is required for
  the current VM-based Spread suite, not inherently for container-based try
  builds. Report unavailable VM tests as blocked; never count discovery as pass.
- Use disposable Workshop projects and synthetic state for startup/version
  identity, real native terminal/filesystem execution, Web/TUI and relevant
  browser/code paths, plugin install/enable/update/disable/remove, and packaged
  dependency resolution. Use a controlled local test plugin for the general
  plugin mechanism. Test bundled plugins, Mandate and Promise Keeper separately;
  report individual incompatibilities without confusing them with that mechanism.
- Exercise old-layout migration, repeated setup, operator-edited configuration,
  plugin conflicts and state persistence across restart and SDK refresh.
  Verify rollback to the prior working SDK without losing persistent state.
- Verify existing OpenSandbox/REA configuration and relevant integration paths
  with disposable peers or fixtures. Label mocked versus real integration
  evidence. Do not contact live B/C to satisfy a test.
- Preserve source manifests, dependency inventory, complete check outcomes,
  artifact SHA-256 values and a durable last-known-good SDK with its recovery
  procedure. Publish only the exact tested artifact after separate authorization.

## Stable-release automation requirements

Implement this behavior when release automation is in scope; these requirements
do not assert that the current workflows already provide it.

1. Monitor official `NousResearch/hermes-agent` releases on the existing schedule.
   Find every unseen supported stable release, paginating as needed; exclude
   drafts, prereleases and unsupported/legacy identifiers. Persist release
   identities and immutable commits, deduplicate PRs and process releases in
   order, including multiple releases between checks. Report metadata errors
   and moved tags explicitly rather than interpreting them as no update.
2. Automatically create pinned Hermes core SDK update PRs and qualify A's
   candidates before merge. Remove the main-only build gate and recurring manual
   runner attestation once the runner is configured. Keep unrelated dependency
   monitoring; its reports do not authorize unrelated automatic updates.
3. Ensure bot-created PRs actually trigger unattended qualification. Verify
   GitHub's current `GITHUB_TOKEN` event behavior and use a supported mechanism
   with the least necessary permissions. Report any one-time repository setting,
   runner or authentication requirement; do not quietly add persistent credentials.
4. Conditionally auto-merge only recognized release-bot Hermes core update PRs.
   Verify authenticated origin and expected change scope; a label or branch name
   alone is insufficient. Exclude PR #3, unrelated/human PRs, unexpected files,
   and workflow or permission changes from automatic merge.
5. Require the full declared qualification suite to pass for the latest PR commit
   against the current target branch: source checks, SDK packaging/startup,
   native tools, plugin management/dependencies, persistence, rollback and relevant
   compatibility/regression tests. Missing, skipped, cancelled, inconclusive or
   failed required checks block merge. Requalify after head/base changes; handle
   concurrent releases without merging stale evidence.
6. Use GitHub-supported auto-merge and required checks/protection or rulesets
   where available. Never bypass required checks or push unqualified updates
   directly to `main`. Leave failed candidates unmerged with diagnostics.
   Demonstrate passing and failing scenarios using controlled test PRs before
   declaring the automation operational.
7. Automatic merge ends at the repository. SDK Store publication and live
   Workshop refresh remain manual, separately authorized steps. Retain the last
   known good SDK and rollback capability.

## Verification and reporting

Before declaring success, inspect the exact diff and verify the resulting file
or behavior on the intended branch. State what changed and why, commands/checks
run, their outcomes, and remaining blockers. Include the commit and PR link for
remote changes. Do not equate committed code or workflow YAML with working runtime.

Report implementation, hosted CI, runner availability, SDK build, automated tests,
disposable Workshop integration, plugin persistence/rollback and release-pipeline
readiness separately when relevant. Distinguish passed, failed, blocked, skipped
and not-run results, and identify pre-existing failures. Historical reports and
synthetic/mocked checks do not prove current live readiness.

At this file's introduction, PR #3 still pins Hermes 0.22.5 and npm build steps;
the wrapper lost its explicit core-update block, migration copies legacy tool
restrictions, and `cli: [all]`, plugin dependency activation and bundled-plugin
symlink behavior still need runtime validation. Existing configuration/wrapper
tests and CI guards also need reconciliation. Review their current state before
acting; this list is context, not evidence that those fixes were completed.
