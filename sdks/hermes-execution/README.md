# Hermes Execution SDK for Workshop

Pinned OpenSandbox control service in a separate Workshop, with a dedicated Cloudflare tunnel client. Requires Canonical's `docker-ce` SDK first; credentials and service activation remain operator-controlled.

## Reference workshop

```yaml
name: b
base: ubuntu@26.04
sdks:
  - name: docker-ce
    channel: "latest/stable"
  - name: try-hermes-execution
```

This local reference consumes `sdkcraft try`. The published Store SDK is `hermes-execution` on `latest/edge`; use the bare name and that channel to download it. The [deployment example](../../deployment/b/workshop.yaml.example) defines system secret slots. Manually connect `hermes-execution:api-key` to `system:api-key` and `hermes-execution:cloudflare-token` to `system:cloudflare-token`; neither connects automatically.

## Using the SDK

### Prerequisites, project layout

Use an unprivileged LXD container with working nested Docker. Configure the authenticated private API and dedicated tunnel through the operator-owned configuration mount. Never expose the Docker socket to A or publish the control API.

### Inspect the packaged runtime

Inside B, inspect `opensandbox-server --help`. Follow the [activation checklist](../../deployment/activation-checklist.md) before starting services. Unconfigured health reports installation status, not authenticated execution readiness. The control database survives Workshop updates; Docker containers and their files do not have a persistent mount. Export needed workload artifacts before refreshing B, and recreate public workloads afterward. Normal sandbox retention follows the configured TTL.

## Plugs (resources this SDK consumes)

| Plug | Interface and purpose | Connection |
| --- | --- | --- |
| `state` | mount, `/home/workshop/.opensandbox` | automatic system mount |
| `configuration` | read-only mount, `/etc/hermes-experiment` | automatic system mount; operator populates it |
| `api-key` | secret, dedicated OpenSandbox authentication | manual system slot connection |
| `cloudflare-token` | secret, dedicated tunnel token | manual system slot connection |

## Slots (resources this SDK provides)

None. A reaches the authenticated API through the private bridge, not a public port forward.

## Documentation and guidance

- [Official OpenSandbox](https://github.com/opensandbox-group/OpenSandbox)
- [Verification and limitations](../../reports/verification.md)

## Community and support

Report upstream issues to the official OpenSandbox repository.

## Contributions

Prove worker routing, failure behavior and refresh persistence with synthetic workloads before enabling new operations.

## License and copyright

OpenSandbox and cloudflared are Apache-2.0 licensed. Bundled dependencies retain their own licenses and notices.
