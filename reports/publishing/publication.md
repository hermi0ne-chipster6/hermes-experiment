# SDK Store publication — 2026-11-01

Publisher: **codyprevost**. The operator explicitly authorized publishing all three SDKs using the existing SDKcraft login. Exact tested archives were verified against SHA256SUMS and uploaded without rebuilding.

| SDK | Version | Revision | Channel | Platform |
| --- | --- | --- | --- | --- |
| hermes-experiment | 0.22.5 | 1 | latest/edge | ubuntu@26.04 AMD64 |
| hermes-execution | 1.2.0 | 1 | latest/edge | ubuntu@26.04 AMD64 |
| hermes-rea | 6.7.0 | 1 | latest/edge | ubuntu@26.04 AMD64 |

All uploads were approved and released by the live Store. Authenticated revision listings and public SDK discovery confirm the channel/version/revision. [Exact metadata and hashes](publication.json), [preflight](preflight.json).

## Consumer verification

Separate projects under `validation/store/` use bare SDK names and `channel: latest/edge`. Original local try definitions and their test data remain intact. Replacing an existing try reference with identical Store bytes produced a no-op, so fresh consumer projects verify the Store path instead.

- B reached ready with Store revision1; actual native health200, unauthenticated list401 and authenticated list200 passed. Canonical docker-ce remains revision13, with Engine29.9.2.
- C reached ready with Store revision1; native REA6.7.0 MCP initialization and tools/list advertised207 tools. No replacement MCP server was created.
- A reached ready with Store revision1. Direct LXD execution passed native Hermes/Sui/Link/Buzz checks, fixed-profile guards, immutable-update rejection and absence of Docker/private diary sockets. The native diary/plugin fixture also passed on a standalone direct-LXD retry: five local synthetic API requests and one durable diary receipt, with progressive discovery of all seven custom tools. This used built-in fixture memory, not semantic Hindsight recall.

Evidence is in the SDK-specific `*-ready.log`, `*-tasks.log`, `*-smoke.log`, upload/revision/info logs and the final `verify-store.exit` marker. Nested validation projects use hostname fallbacks because their directory names duplicate the original test projects; this is recorded in Workshop info.

## Failed attempts and limits

The first REA upload invocation returned143 before confirming a revision; a Store check found none, and retry published revision1. Several Workshop command invocations also returned143. Signal-only diagnostics and original exit markers are retained; the cause is not established. A's direct LXD checks are distinguished from Workshop execution checks. One direct LXD invocation reported a Unix-socket write timeout; the standalone retry passed. A frontend signal trace showed exit143 without a received SIGTERM, so the origin is not established. No SDK code workaround was introduced.

The packages are published on edge. Stable promotion, full VM-based Spread qualification, live gateways/credentials, semantic memory checks, financial authorization setup, Cloudflare routing and unattended experiment activation remain outside this publication. Future-release CI is still an inactive template because no repository is configured.

Existing authentication was reused without exporting credentials. No real model/embedding API calls, messages, payments, wallet setup, original-bank migration or production-service activation occurred. Root AGENTS.md and the three Canonical skills remain unchanged.

Final result: publication and available consumer verification are complete. All three launch changes are Done and their SDKs track latest/edge revision1. Artifact checksums still match the tested files. Deployment examples and SDK READMEs now document the published edge channel.
