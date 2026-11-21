# Hermes Experiment #1

SDKcraft sources and deployment examples for Ubuntu 26.04 AMD64. The [verification records](reports/README.md) describe earlier builds and Store publication.

| Workshop | Purpose | Definition |
| --- | --- | --- |
| A | Official pinned Hermes, native Buzz/email gateway, Hindsight, diary client, existing financial CLIs | [hermes-experiment](sdks/hermes-experiment/sdkcraft.yaml) |
| B | Canonical Docker SDK followed by OpenSandbox; dedicated Cloudflare tunnel | [hermes-execution](sdks/hermes-execution/sdkcraft.yaml) |
| C | Official REA MCP 6.7.0, Ghidra and analysis tools, restricted SSH/stdio | [hermes-rea](sdks/hermes-rea/sdkcraft.yaml) |

Hermes independently chooses its objectives under the original charter. The persistent messaging gateway and operator-owned two-hour cron heartbeat have separate lifecycles. Gateway messages do not replace Stripe policy controls or Sui's required 2-of-3 authorization. No wallet, financial policy, credentials, live mailbox, Buzz identity or Cloudflare account has been created or changed.

## Build and verify

Each directory under `sdks/` is a separate publisher SDK source. Use its `sdkcraft clean` / `sdkcraft try --build-for amd64` loop, then consume it as `try-<name>` using the retained `validation/*/workshop.try.yaml.example` definitions. The separate `validation/store/` projects consume the published `latest/edge` revisions; the original validation projects retain their try definitions. B lists Canonical `docker-ce` first. Run heavy builds sequentially on this test host. Run `sdkcraft test --list` and `sdkcraft test` from each SDK directory on a host with the required virtualization support. SDK smoke tests never substitute for authenticated application checks.

The custom integration uses the Python standard library. From this directory:

```bash
python3 -m unittest discover -s tests -v
python3 release/detect.py --output reports/release-candidate.json
```

Exact upstream tags, revisions, package locks and binary/image hashes are recorded in [sources.json](sources.json). Workshop A packages the official source and frozen dependencies, with the upstream pnpm Web and TUI builds. Its native terminal, files, browser, code and skills are available with Hermes permissions. OpenSandbox and REA remain optional integrations. Core upgrades use SDKcraft. Native plugin commands manage plugins in the persistent Hermes profile.

## Diary and commitments

The [journal](diary/hermes_diary/) runs outside A under a dedicated identity. A receives a bounded Unix-socket API, never the database or operator control socket. SQLite transactions acknowledge durable, idempotent appends; receipts survive retries. Corrections and commitment changes create new events. Fulfillment requires an evidence reference and remains an agent-reported claim.

Native Hermes hooks request and submit an authored heartbeat report. The external runner checks the exact run/request receipt; a zero exit without it is incomplete. One bounded retry resumes that heartbeat's named session. Commitments established in messaging sessions use the same register. Missing hooks, interrupted processes and model errors cannot be repaired by inventing a report.

## Deployment and releases

Start with the [activation checklist](deployment/activation-checklist.md), [network requirements](deployment/networking.md), [execution-isolation decision](deployment/execution-isolation.md) and role-specific `.example` files. The shared LXD bridge provides connectivity; it does not authenticate workers or enforce isolation. Worker tool allowlists and external adapters remain disabled until their actual checks pass. Hindsight is the baseline; existing banks remain untouched. MemPalace evaluation and any restore or migration require separate evidence and approval.

Maintenance CI monitors the declared SDK inventory and prepares pinned Workshop A updates for official stable Hermes releases. The release workflow requires source checks, packaging, Spread and disposable Workshop acceptance before GitHub can auto-merge a recognized release PR. The runner and GitHub ruleset require one-time setup. Store promotion and Workshop refresh are separate operator actions. [Release workflow and setup](release/workflows/README.md)

## Source repository

This integration repository preserves all three publisher SDK sources, shared diary code, deployment examples, dependency locks, tests and reviewed release records. Each SDK remains under `sdks/<name>/`. Build outputs, credentials, runtime databases, local Workshop state and raw diagnostics are excluded; see [verification records](reports/README.md). Keep original test-machine evidence and exact published SDK packages separately.

## Reconnect

The ongoing Codex conversation is attached inside tmux. As `codex`, run `tmux attach -t hermes-sdk`; detach with **Ctrl+B, D**. Build outputs and the execution ledger are in `reports/`. Tmux survives a client disconnect, but does not itself schedule future assistant turns or survive a host reboot.

## Publisher name

Workshop A uses the registered SDK name `hermes-experiment` (local `try-hermes-experiment`). See the [publishing commands](release/publishing.md). The official upstream remains NousResearch Hermes Agent. Earlier archives using the SDK name `hermes-agent` are superseded.

## Published releases

Initial publication completed on 2026-11-01 under `codyprevost`: all three SDKs are revision1 on `latest/edge`, targeting Ubuntu26.04 AMD64. Fresh Store-based Workshops reached ready and passed the available native smoke checks. See the [publication record](reports/publishing/publication.md), including execution-transport retries and remaining stable/production gates. The current source bundle is `hermes-experiment-source-20261101-published.zip`; earlier source bundles predate publication.
