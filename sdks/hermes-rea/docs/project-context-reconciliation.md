# REA worker purpose and documentation reconciliation

Reviewed the supplied `Hermes_Documentation_v0.2 (10).zip` on 2026-11-17. Archive SHA256: `d513a69653b3ba09429c4cc117dedf67f0815fe19af0f2304a6b1f4ee9420e8c`. All 40 entries in its `SHA256SUMS` matched. The archive is retained unchanged outside this source checkout; detailed verification is in `/root/dev/rea-sdk/validation-logs/documentation-integrity.json`.

Primary context read: `README.md`, `docs/PROJECT_CONTEXT.md`, `docs/ARCHITECTURE.md`, `docs/decisions/0003-rea-mcp-worker.md`, `docs/decisions/0002-persistence-and-reproducibility.md`, and `docs/sources/OPERATOR-CONTEXT-2026-10-27.md` inside the archive.

## Intended role

Hermes Experiment #1 studies self-directed agent behavior across recurring sessions; it does not prescribe a business or revenue objective. The engineering goal is to reproduce approved capabilities while preserving continuity, inspectability, operator authority and recovery.

The three-role design assigns orchestration and trusted native state to A, ordinary execution to B, and specialist REA analysis to C. REA is an analysis service available to Hermes, rather than a replacement orchestration agent or general-purpose execution backend. The historical Ghidra/JDK/pwntools/GDB list is the earlier toolchain baseline. The current task explicitly broadens C to the supported upstream REA engine.

## How this SDK work implements that purpose

| Documented intent | SDK implementation or validation obligation |
|---|---|
| Reuse upstream REA rather than invent another protocol server | Build unmodified pinned upstream; retain CLI and MCP; compare the complete canonical tool inventory with `tools/list` and `binary_session`; exercise real operations. |
| Keep analysis dependencies away from A's trusted state | Package them in the existing C SDK; use a separate disposable Workshop project and synthetic inputs during development. No production A/B environments or private state are used. |
| Restricted SSH stdio and no public MCP service | Preserve the forced-command transport and public-key allowlist import; test allowed MCP/artifact requests and rejected command forms. SDK startup launches no public MCP listener. |
| Pin compatible tools and prevent silent provider substitution | Use source/checksum pins and provider-specific configuration. Report licensed, external, platform and upstream limitations separately. A registered tool is not runtime proof. |
| Separate executable reconstruction from durable data | Immutable SDK tool trees; dedicated `/var/lib/hermes-rea` state mount. Test exported evidence across refresh and re-import in a new process, plus provider snapshots. Active in-memory sessions are not claimed to survive process exit. |
| Keep credentials and operator control outside C | No A home/state mounts, production secrets, signing material or administrator engine sockets are added. The C account and artifact protocol are preserved. |

## Historical statements versus current authorization

The archive is explicitly an October documentation draft, not proof of deployment. Its REA6.7.0 pin, documentation-only task boundary, old host/account paths and unverified source identity are historical. The current user request authorizes local development, root administration, SDK builds and disposable Workshop/LXD tests on this VPS and supplies the authoritative upstream repository. That authorization does not extend to other VPS instances, unrelated infrastructure, remote pushes or Store publication.

The existing published SDK6.7.0 and its original repository were independently located before modification. This development branch continues that implementation with upstream commit `51459cf203ae1eb6b586a95b21899eaa0f631823`, package version6.9.0. No earlier documentation approval gate is being used to suspend currently authorized work.

## Claims that remain separate

SDK validation proves C's package, interfaces and tested operations. It does not by itself prove the pinned Hermes plugin in A routes every operation to C, cannot fall back locally, or keeps all A credentials out of worker synchronization. Likewise, SSH command restrictions are not a complete sandbox for analysis tools that intentionally execute processes. Full A/B/C routing, network policy, cross-role access denial, independent audit and production deployment need their own integration evidence. No production deployment, audit enforcement, financial authority, scheduler or experimental-personality change is claimed by this work.
