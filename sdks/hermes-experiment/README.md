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

Keep the operator charter and deployment inputs in the read-only configuration mount. The active Hermes profile, installed plugins, and package-manager state live on the persistent Hermes mount. Follow the [activation checklist](../../deployment/activation-checklist.md) before enabling gateways or cron. Native tools run in A. Connect B or C when a task explicitly needs external OpenSandbox execution or REA analysis.

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
| `diary` | tunnel, `/run/user/1000/hermes-diary.sock` | explicit example connection |
| `model-key`, `buzz-key`, `email-password`, `sandbox-api-key`, `rea-ssh-key` | secret, dedicated runtime credentials | manually connect each same-named system slot |

### Sui and Stripe Link state

The [Sui SDK](../sui-cli/) owns `/home/workshop/.sui` and the
[Stripe Link SDK](../stripe-link-cli/) owns `/home/workshop/.link-cli`.
Each installs its own executable in `/usr/local/bin`. For disposable
qualification, register the three exact archives and use the
[local composition](../../validation/hermes-agent/workshop.try.yaml.example).

When moving an older Workshop that bundled the CLIs, record both existing
mount sources with `workshop info` and preserve the directories. Keep
the gateway and financial operations inactive during the cutover. Use
the standalone SDKs' mount paths and remount the preserved sources to the
new plugs while the Workshop is stopped. Verify executable ownership
and state before returning it to use. The existing financial policies
and Link auth-file path continue to apply.

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

Configure the official Hindsight provider through `hermes memory setup` before activation. For this deployment choose its native `local_embedded` mode and explicitly select the extraction model/provider. The packaged `hindsight-api` entrypoint runs in an isolated, pinned environment; the native embed manager starts it on demand and stops it after its configured idle period. No additional Hindsight service or runtime installer is required. Its fresh pg0 directory is linked into the durable Hindsight mount. Provider credentials/profile setup and semantic cross-session tests remain activation requirements; existing bank restoration is separate.
