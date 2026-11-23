# Sui CLI SDK for Workshop

This SDK packages the official Sui CLI 1.82.3 release for Ubuntu 26.04 AMD64.
It exposes `sui` at `/usr/local/bin/sui`. The pinned release archive is checked
against the SHA-256 in the project source manifest before extraction.

List `try-sui-cli` in the Workshop definition after building the local SDK with
`sdkcraft try --build-for amd64`. The SDK's `sui-state` plug uses the automatic
system mount at `/home/workshop/.sui` with mode 0700. SDK setup only installs the
executable link. The native CLI manages wallet configuration.

For an existing Workshop whose Hermes SDK still owns `.sui`, record and back up
the real host source reported by `workshop info` before replacing that mount.
The standalone SDK has a different default host source. In the reviewed
composition, remount `<workshop>/sui-cli:sui-state` to the preserved source and
verify the configuration in a disposable copy before migrating operator state.

Run the offline package and repeated-setup fixtures from the repository root
with `python3 -m unittest discover -s sdks/sui-cli/tests -v`.
