# Hermes Experiment SDK for Workshop

Official stable Hermes runtime for Experiment #1, with native Buzz/email gateway support, Hindsight, diary integration and the existing financial CLIs. Agent state persists across Workshop updates; credentials and activation are supplied separately.

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

Use an operator-owned read-only configuration directory and an external diary writer. Follow the [activation checklist](../../deployment/activation-checklist.md) before enabling gateways or cron. Independent B/C workers are required for execution and analysis.

### Inspect the packaged runtime

Inside A, run `hermes --version`. Runtime self-updates are refused; use a reviewed SDK revision and Workshop refresh. State mounts survive Workshop updates. The gateway starts only after explicit configuration and activation.

## Plugs (resources this SDK consumes)

| Plug | Interface and target | Connection |
| --- | --- | --- |
| `state` | mount, `/home/workshop/.hermes` | automatic system mount |
| `hindsight` | mount, `/home/workshop/.hindsight`, including linked pg0 database | automatic system mount |
| `sui-state` | mount, `/home/workshop/.sui` | automatic system mount |
| `link-state` | mount, `/home/workshop/.link-cli` | automatic system mount; native auth and identity state |
| `configuration` | read-only mount, `/etc/hermes-experiment` | automatic system mount; operator populates it |
| `diary` | tunnel, `/run/user/1000/hermes-diary.sock` | explicit example connection |
| `model-key`, `buzz-key`, `email-password`, `sandbox-api-key`, `rea-ssh-key` | secret, dedicated runtime credentials | manually connect each same-named system slot |

## Slots (resources this SDK provides)

None.

## Documentation and guidance

- [Hermes documentation](https://hermes-agent.nousresearch.com/docs/)
- [Verification and limitations](../../reports/verification.md)

## Community and support

Use the official [Hermes repository](https://github.com/NousResearch/hermes-agent) for upstream issues.

## Contributions

Validate source pins, tests and the real SDK try loop before proposing changes. No publication workflow is active here.

## License and copyright

Hermes is MIT licensed. Bundled dependencies retain their own licenses and notices; preserve them when redistributing the SDK.

## Memory lifecycle

Configure the official Hindsight provider through `hermes memory setup` before activation. For this deployment choose its native `local_embedded` mode and explicitly select the extraction model/provider. The packaged `hindsight-api` entrypoint runs in an isolated, pinned environment; the native embed manager starts it on demand and stops it after its configured idle period. No additional Hindsight service or runtime installer is required. Its fresh pg0 directory is linked into the durable Hindsight mount. Provider credentials/profile setup and semantic cross-session tests remain activation requirements; existing bank restoration is separate.
