# Workflow installation

These files are templates, not activated workflows. Paths assume `hermes-experiment/` becomes the root of a protected integration repository. The detector's Ubuntu 24.04 runner performs only standard-library HTTP/JSON work; **every SDK target and the compatibility build host remain Ubuntu 26.04 AMD64**.

Detection runs every six hours and produces a review artifact. After a candidate's exact tag/revision, plugin pins and dependency locks are updated on a candidate branch, the compatibility workflow runs automatically for its pull request to `latest`. It retains the exact tested SDK bytes and checksums. Configure required checks and operator review on that branch. Failed, empty, blocked or skipped suites cannot support promotion.

The dedicated `hermes-sdk-build` runner needs Workshop/SDKcraft/LXD, passwordless local build privileges, working KVM, adequate free disk/RAM, and a fresh disposable environment. Pin and maintain its toolchain against `sources.json` and the verification report. It must not hold operator or publication credentials. Do not grant runner access to untrusted fork pull requests.

The SDK jobs cover packaging/Spread smoke checks; cross-worker routing, native authenticated gateways, actual heartbeat hooks, memory continuity and refresh/network policy still need the separate activation evidence named by each release candidate. Do not infer that a green smoke workflow proves those checks. Promotion remains an operator review followed by upload/release of the verified artifact. No automatic publishing workflow or runtime updater is supplied.
