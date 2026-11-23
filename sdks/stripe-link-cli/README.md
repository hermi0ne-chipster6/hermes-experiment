# Stripe Link CLI SDK for Workshop

This SDK packages `@stripe/link-cli` 1.0.1 and Node.js 26.13.0 for Ubuntu
26.04 AMD64. The native entry point is `/usr/local/bin/link-cli`, including
`link-cli --mcp` for MCP clients. The npm lock pins the full dependency graph.

List `try-stripe-link-cli` in the Workshop definition after building the local
SDK with `sdkcraft try --build-for amd64`. The `link-state` plug automatically
mounts `/home/workshop/.link-cli` with mode 0700. The wrapper defaults
`LINK_AUTH_FILE` to `/home/workshop/.link-cli/auth.json` and honors a nonempty
operator override. The native CLI manages authentication, identity and
transaction policy.

For an existing Workshop whose Hermes SDK still owns `.link-cli`, record and
back up the real host source reported by `workshop info` before replacing that
mount. The standalone SDK has a different default host source. In the reviewed
composition, remount `<workshop>/stripe-link-cli:link-state` to the preserved
source and verify the configuration in a disposable copy before migrating
operator state.

Run local package and wrapper fixtures from the repository root with
`python3 -m unittest discover -s sdks/stripe-link-cli/tests -v`.
