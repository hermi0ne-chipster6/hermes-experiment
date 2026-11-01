# Verification — Hermes Experiment #1

**Store publication — 2026-11-01:** All three SDKs are now revision 1 on `latest/edge`. See the [publication record](publishing/publication.md), [exact metadata](publishing/publication.json) and current Store deployment examples. Stable promotion and production activation remain gated. The following local-build evidence was recorded on 2026-10-31.

**Publisher rename completed:** SDK A is now `hermes-experiment`, matching the name registered by the operator. Its clean build, real Workshop refresh/readiness, installed checks and local synthetic native CLI/diary/plugin checks passed. See the [rename verification](sdk-rename.md) and [current publishing commands](../release/publishing.md). Earlier integration logs retain the previous SDK name. No upload or release was performed during that rename checkpoint; initial Store publication followed on 2026-11-01.

Final local checkpoint: 2026-10-31 UTC. The three SDK definitions, built archives and available local verification are complete. **Production activation remains gated on the account-specific and VM checks below.** No real model/embedding API requests, messages, transactions, wallet setup, or bank restoration were performed during local verification; Store publication followed separately on 2026-11-01.

## Build and installation results

All SDKs target **Ubuntu26.04 AMD64, CPU only**. Actual Workshop states reached `ready`.

| Role | Final installed composition | Evidence |
| --- | --- | --- |
| A | Registered name `hermes-experiment`; official Hermes0.22.5, revisionbf0203a7; native Buzz/email assets, Hindsight, diary/notifications/artifact clients, Link and Sui | [Ready](rename-ready.log), [installed-runtime checks](rename-installed.log); renamed refresh 83 Done |
| B | Canonical docker-ce29.5.1/rev13, actual Engine29.9.2; OpenSandbox1.2.0 SDKx3 and cloudflared2026.10.7 | Refresh65 Done; persistent marker retained; native API/user-service checks below |
| C | Native REA6.7.0 SDKx7, Ghidra12.1.4, Java/Javac25, Frida17.23.2 and analysis tools | Refresh71 reached ready; actual Ghidra analysis below |

SDKcraft try exitedzero for all final sources. Packing ran its built-in linters. Archive inspection matched **28 custom A files,7 B files and6 C files** against source, including hooks; all three try-cache archives match the built files. No generated SDK archive or Spread reuse file was found inside a payload. [Exact hashes/sizes](artifacts.json), [archive check](rename-archive-verification.log).

## Passed checks

- **90/90 behavioral tests**, including durable/idempotent diary storage, commitment status/evidence requirements, real-socket permissions and reserved IDs, timeout/closing behavior, runtime guards, artifact integrity/deadlines and release filtering. [Log](rename-unit-tests.log).
- **ShellCheck19 scripts**, and parsing of24 selected SDK/deployment/Spread YAML documents. Native SDKcraft builds also validated their definitions. [Shell](rename-shellcheck.log), [YAML](rename-yaml-check.log).
- Separate host diary writer/client subprocesses acknowledged a durable report and idempotent retry. [Log](diary-cli-smoke.log). Host production units/tunnel were not activated.
- **Real packaged Hermes CLI**, using a local synthetic API and isolated built-in-memory profile, submitted one durable report. Native progressive discovery registered all seven custom tools; terminal/read_file calls were rejected. Original-charter context was present. The test made five requests to its local fixture, not a model provider. [Final forwarded run](native-hooks-workshop-confirmed.log), [direct run](native-hooks-direct-packaged-final.log).
- Native Hermes, Sui and Link entrypoints work; Buzz help succeeds. Unconfigured chat, profile redirection and runtime self-updates are rejected. Default SOUL bytes remain unchanged; no Docker socket or private diary control socket is present in A. Canonical's user linger configuration is present. [Log](agent-installed-final.log).
- **Hindsight engine persistence:** a fresh embedded PostgreSQL row was written, read by a separate process without CREATE/INSERT, then read again after A's actual SDK refresh. [Write](pg0-before-refresh-write.log), [separate read](pg0-read-existing.log), [after refresh](pg0-after-refresh-read.log). Native embed imports and the packaged API entrypoint resolve. This proves engine/storage continuity, not semantic retention or recall.
- OTel module import and its included dashboard assets are present. Backend export/dashboard operation remains untested. [Log](otel-import-dashboard.log).
- **B native API:** health200, unauthenticated list401, authenticated list200 after final refresh. A native user service with NoNewPrivileges can access Docker29.9.2. B's state marker survived refresh. [API](execution-final-api-tmux.log), [service](execution-user-service-docker.log), [persistence](execution-refresh-persistence.log).
- Unprivileged nested Docker runs pinned hello-world with networknone/read-only root/cap-dropALL/no-new-privileges/pids32. A's packaged native SDK also created a temporary B sandbox, ran Python (`42`), wrote/read matching file bytes through the authenticated server proxy and killed/closed it. [Docker](nested-docker-smoke.log), [native workload](opensandbox-native-files-workload.log). The workload used a pinned small Python fixture image.
- **Real B→C pipeline:** native SDK file streaming plus a dedicated ephemeral test SSH agent delivered43,432 verified ELF bytes into C. Native REA objdump read that same unchanged path. After C's refresh, native **Ghidra12.1.4 listed255 procedures,206 internal**, with the same input digest. [Transfer](native-artifact-pipeline.log), [objdump](rea-pipeline-objdump.json), [Ghidra](rea-ghidra-procedures.json).
- Native SSH/MCP negotiated REA6.7.0 and207 tools. Actual checks rejected bad artifact digests, arbitrary commands, remote forwarding and wrong host identity; retries returned the same receipt. Native Frida loads. [Boundaries](rea-ssh-boundaries.log), [Frida](rea-frida-smoke.log).
- A resolves B/C and receives their private SSH banners after refresh; B's Docker TCP2375 is unavailable. A lacks Docker/private-diary sockets. This is sampled boundary evidence, not a complete network-security audit. [Bridge](bridge-final.log).
- Stable-release detection found no newer stable than Hermes0.22.5 at the final check. It proposes candidates without promoting/upgrading them. CI/Store templates remain inactive.

## Spread results

| Job | Actual outcome |
| --- | --- |
| A launch | Not run: required VM backend unavailable |
| A persistence | Not run: same blocker |
| A missing-secret | Not run: same blocker |
| B launch | Attempted; aborted at VM allocation; successful0/aborted1 |
| C launch | Not run: same blocker |

The host has no `/dev/kvm`; LXD explicitly rejected its virtual-machine allocation. [Actual failure](spread-b-final.log). Discovery is not a pass. The Spread host's24.04 VM setting does not change the SDK payload target26.04.

## Decisions, review and limitations

The original charter remains authoritative and is supplied verbatim outside SDK payloads. Upstream SOUL is preserved. No AGENTS.md, Canonical skill or historical document was modified. All three skill content/mode hashes and supplied document checksums match. [Preservation](preservation.json), [checksums](original-documents-checksums.log).

The first independent review found no Critical and four Important issues; all were corrected with regression evidence: missing configuration fallback, timeout falsely completing after a zero exit, public lifecycle-ID poisoning and fork access to the sudo-capable CI runner. A focused transfer review found one Important missing wall-clock deadline; its stalled-stream regression now passes. Review did not establish live integration or a dependency security audit.

Execution decisions are recorded in [progress.md](progress.md). Material choices:

- Package exact official source/frozen dependencies with CPython3.14.7; upstream reserves its wheel build for Nix. Omit only the disabled local browser dependency whose Pillow constraint conflicts with the official lock. No fork, main revision or runtime application installer.
- Keep native Hindsight's API isolated from incompatible core dependencies; use its on-demand embed manager and durable pg0 link. Select local_embedded explicitly during setup; the provider's default is cloud. No duplicate daemon or bank migration.
- Use bounded installation health checks, with full native startup tested in setup-project. A ready unconfigured installation does not establish authenticated gateway readiness.
- Require an external durable diary receipt and one bounded closing attempt; interrupted or missing submissions remain incomplete. Fulfillment/agreement records remain agent-reported claims.
- Retain the separate OpenSandbox worker. [Bubblewrap comparison](../deployment/execution-isolation.md). No unavailable worker selects local execution in A. Native MCP uses string commands; the Python argv extension failed against the selected execd and is not claimed supported.
- Retain native REA MCP, plus only a bounded artifact-input mode on its forced SSH connection. Pin compatible [Ghidra12.1.4](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.4_build): native REA rejected12.2. Include the verified official Frida binary rather than enabling npm installers.
- Copy C's public allowlist into a root-owned path for StrictModes. A configuration-only change can produce “no updates” from Workshop; the operator must explicitly reapply the packaged setup hook. This was done for revocation; the removed key was rejected. [Proof](rea-key-revocation.log), [operator command](../deployment/activation-checklist.md).

Earlier failures remain in logs. Initial cold CLI/API probes timed out or their transient clients terminated; final checks in tmux passed. The final CLI fixture allows a larger startup window. Those passes do not erase the failed attempts.

## Environment and cleanup

Test host: two vCPUs,3.7GiB RAM,38GiB disk. Workshop0.9.9-f8fdf0d/rev800; SDKcraft0.9.4/rev220; LXD6.10.1/rev41228. An earlier kernel OOM killed Vite. Temporary2GiB swap enabled the successful builds; it is now disabled and deleted, with no fstab edit. Build instances are stopped. Test gateways/API services are stopped, the synthetic SSH identity was revoked/deleted, and its private key is absent.

SDKcraft used sudo; Workshop operated as codex. Exact try-cache copies were verified; final A handoff replaced files atomically. No host Docker, privileged-container workaround, commit, push, Store publication or account CI activation was introduced.

A retired root-owned synthetic fixture failed a mount hook. One early full LXD diagnostic exposed its generated test host key in the tool transcript; no production identity was involved. Subsequent diagnostics filtered safe fields. The active test key was separate and has also been revoked/deleted.

## Production activation gates

1. Run all five Spread jobs on a supported KVM/VM host. Size production resources and test cold startup/recovery under expected load.
2. Qualify the full code-interpreter/browser images, explicit MCP tool allowlists, all cron/monitor/discovery paths, failure/cancellation/cleanup and deployment network policy. Empty MCP allowlists deliberately prevent premature activation.
3. Provision the external host journal identity/services/tunnel and test the actual operator-owned two-hour cron entry and persistent gateway concurrently. Those production units were not enabled during generation.
4. Configure real model/mailbox/Buzz identities, authenticated operator responses and headless host secret delivery. Test native send/receive/approvals. Preserve financial controls independently of gateway replies; no ACP auto-approval.
5. Test semantic Hindsight retain/recall across real CLI heartbeats and refresh. MemPalace has a [source review and acceptance experiment](../deployment/memory-evaluation.md), not a runtime acceptance result. Existing banks/backups were never accessed; restoration or migration requires separate approval.
6. Verify native Link transaction-policy behavior and separately finish Sui2-of-3 only when authorized. No financial configuration was invented or wallet initialized.
7. Configure delegated Cloudflare workload routing. The client/unit is packaged; live DNS, tunnel registration and autonomous route changes were not implemented or exercised. Never expose the administrative OpenSandbox reverse proxy. Configure telemetry backend/dashboard access separately.
8. The operator reports registering `hermes-experiment`, `hermes-execution` and `hermes-rea`. Initial edge uploads are complete; stable promotion and protected CI activation remain outstanding. Original local verification used try SDKs, followed by isolated Store-based launches. Refresh consumes promoted releases, not arbitrary upstream upgrades.

The session and logs remain available with `tmux attach -t hermes-sdk` as codex. Tmux survives client disconnection, not host shutdown, and does not itself schedule future assistant turns.
