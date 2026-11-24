# Hermes Experiment SDK for Workshop

Official stable Hermes runtime for Experiment #1, with native Buzz/email gateway support, Hindsight and diary integration. The complete Workshop A composition installs the standalone Sui and Stripe Link SDKs alongside this core SDK. Agent state persists across Workshop updates; credentials and activation are supplied separately.

## Reference workshop

```yaml
name: a
base: ubuntu@26.04
sdks:
  - name: try-hermes-experiment
```

This local reference consumes `sdkcraft try`. The published Store SDK is `hermes-experiment` on `latest/edge`; use the bare name and that channel to download it. The complete [deployment example](../../deployment/a/workshop.yaml.example) declares host secret slots and explicitly connects `hermes-experiment:diary` to `system:diary`. Secret plugs require manual connections from their corresponding system slots; they never auto-connect.

## Using the SDK

### Prerequisites, project layout

Keep deployment inputs in the read-only configuration mount. Put the verbatim operator charter in its own read-only mount under `/project` so the pinned Hermes context loader can read it through `.hermes.md`. The active Hermes profile, installed plugins, and package-manager state live on the persistent Hermes mount. Follow the [activation checklist](../../deployment/activation-checklist.md) before enabling gateways or cron. Native tools run in A. Connect B or C when a task explicitly needs external OpenSandbox execution or REA analysis.

### Inspect the packaged runtime

Run `hermes --version` inside A to see the pinned release and source revision.
Apply core upgrades with a reviewed SDK revision and Workshop refresh. Manage
operator plugins with upstream `hermes plugins` commands. State mounts survive
Workshop updates. The gateway starts after explicit configuration and activation.

### Build inputs

The SDK checks the release tag against the commit declared in `sdkcraft.yaml`.
The Web and TUI builds use the upstream Node, pnpm and frozen workspace lock.
The Web build uses upstream's one-thread, minimum-heap build mode.
The Python environment uses the upstream uv lock and enables the Web and MCP
extras, with a hash-locked overlay for bundled integrations. Native
`browser-harness` uses upstream's recorded Pillow compatibility override, the
packaged Chromium system libraries and upstream-managed Chromium.

The bundled integration lock is resolved against the candidate's frozen core
export, keeping existing compatible pins and using the release publication
timestamp as its cutoff. For v0.23.3 the frozen MCP dependencies require
OpenTelemetry 1.45.2, published after the
previous 2026-10-28 integration cutoff. The isolated Hindsight runtime retains
its original cutoff and lock. Operator-installed plugins keep their own state.

## Plugs (resources this SDK consumes)

| Plug | Interface and target | Connection |
| --- | --- | --- |
| `state` | mount, `/home/workshop/.hermes` | automatic system mount |
| `hindsight` | mount, `/home/workshop/.hindsight`, including linked pg0 database | automatic system mount |
| `configuration` | read-only mount, `/etc/hermes-experiment` | automatic system mount; operator populates it |
| `charter` | read-only mount, `/project/.hermes-charter` | automatic system mount; operator supplies the original charter only |
| `diary` | tunnel, `/run/user/1000/hermes-diary.sock` | explicit example connection |
| `model-key`, `buzz-key`, `email-password`, `sandbox-api-key`, `rea-ssh-key` | secret, dedicated runtime credentials | manually connect each same-named system slot |

### Sui and Stripe Link state

The [Sui SDK](../sui-cli/) owns `/home/workshop/.sui` and the
[Stripe Link SDK](../stripe-link-cli/) owns `/home/workshop/.link-cli`.
Each installs its own executable in `/usr/local/bin`. For disposable
qualification, register the three exact archives and use the
[local composition](../../validation/hermes-agent/workshop.try.yaml.example).

When moving an older Workshop that bundled the CLIs, use this order on a
disposable copy first. Keep the gateway and financial operations inactive
throughout the cutover and reversal.

1. Record the exact old A and new CLI archives and the current Workshop definition.
   Run `workshop info a` to record both existing CLI mount sources. Preserve a
   copy of each source outside Workshop-managed storage and verify the contents,
   modes and ownership. Use these retained directories for the new mounts.
2. Before removing the bundled packages, verify both standalone CLIs against
   the old state in a transitional Workshop. In the old A composition, add the
   standalone SDKs with `sui-state.bind: hermes-experiment:sui-state` and
   `link-state.bind: hermes-experiment:link-state` under the respective SDKs'
   `plugs` mappings. Refresh and check that the standalone binaries own both
   entrypoints and that the old state is readable by the Workshop user.
3. Install the split A archive with the [standalone composition](../../validation/hermes-agent/workshop.try.yaml.example).
   Remove both transitional `bind` mappings from the definition before the
   refresh. Stop A after the refresh. Remount `a/sui-cli:sui-state` and
   `a/stripe-link-cli:link-state` to the retained directories using
   `workshop remount PLUG HOST-SOURCE`. Attach the new charter mount as described
   in the [runbook](../../deployment/NEW-SERVER-RUNBOOK.md). Start A and reapply
   the packaged setup hook. Verify both CLI versions and resolved executables,
   auth paths, contents and permissions before restoring operations.
4. To reverse to v0.22.5, prepare the configuration, charter and plugin paths
   before refreshing, following the [rollback runbook](../../release/workflows/README.md#exact-artifact-and-rollback).
   Refresh to the saved A archive and definition that declare the old
   `hermes-experiment` CLI plugs. Stop A and remount
   `a/hermes-experiment:sui-state` and `a/hermes-experiment:link-state` to the
   retained directories. Start A and verify CLI paths and state before restoring
   operations. Keep the saved archives and retained directories until the
   upgrade and reversal have been verified.

## Slots (resources this SDK provides)

None.

## Documentation and guidance

- [Hermes documentation](https://hermes-agent.nousresearch.com/docs/)
- [Verification and limitations](../../reports/verification.md)

## Community and support

Use the official [Hermes repository](https://github.com/NousResearch/hermes-agent) for upstream issues.

## Contributions

Validate source pins, tests and the real SDK try loop before accepting a core
change. SDK Store publication and live Workshop refresh are operator actions.

## License and copyright

Hermes is MIT licensed. Bundled dependencies retain their own licenses and notices; preserve them when redistributing the SDK.

## Memory lifecycle

Configure the official Hindsight provider through `hermes memory setup` before activation. Choose its native `local_embedded` mode and select the extraction provider and model explicitly. Hermes's native manager discovers the packaged slim API next to the SDK interpreter when both configured embedding and reranker providers are compatible with the slim runtime. For example, configure a reachable TEI embedding endpoint and select `none` for reranking. The embedded API keeps pg0 in the durable Hindsight mount. The native manager can fall back to upstream `uvx` when local SentenceTransformers dependencies are required. Provider credentials/profile setup and semantic cross-session tests remain activation requirements. Existing bank restoration is separate.
