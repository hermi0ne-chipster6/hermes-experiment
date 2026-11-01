# Hermes REA SDK for Workshop

Pinned official REA MCP6.7.0 with compatible Ghidra12.1.4 and analysis tools in a dedicated worker. SSH stdio access requires an operator-provisioned public key and fixed command; no wallet, mailbox or model credentials are shared.

## Reference workshop

```yaml
name: c
base: ubuntu@26.04
sdks:
  - name: try-hermes-rea
```

This local reference consumes `sdkcraft try`. The published Store SDK is `hermes-rea` on `latest/edge`; use the bare name and that channel to download it.

## Using the SDK

### Prerequisites, project layout

Provide a root-owned `rea_authorized_keys` file through the configuration mount. A must pin C's SSH host key. Follow the [activation checklist](../../deployment/activation-checklist.md) and keep private keys outside C.

### Analyze through the native MCP

Connect from A using the provided `hermes-rea-remote` transport. C forces the existing REA MCP command (or the bounded artifact input described in the network guide), disables PTY and forwarding, and stores analysis work under `/var/lib/hermes-rea`. This state survives Workshop updates. Actual MCP initialization, cancellation and synthetic analysis must pass before activation.

## Plugs (resources this SDK consumes)

| Plug | Interface and target | Connection |
| --- | --- | --- |
| `state` | mount, `/var/lib/hermes-rea` | automatic system mount |
| `configuration` | read-only mount, `/etc/hermes-experiment` | automatic system mount; operator supplies public-key allowlist |

## Slots (resources this SDK provides)

None. Restricted SSH uses the private LXD bridge.

## Documentation and guidance

- [Official Hermes REA plugin](https://hermes-agent.nousresearch.com/docs/plugins/rea)
- [Verification and limitations](../../reports/verification.md)

## Community and support

Use the official Hermes REA documentation and linked upstream repositories.

## Contributions

Verify forced-command behavior and synthetic analysis before changing transport or toolchain pins.

## License and copyright

REA is MIT licensed and Ghidra is Apache-2.0 licensed. System analysis tools and other bundled dependencies retain their own licenses and notices.
