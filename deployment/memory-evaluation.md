# Memory decision and remaining experiment

Hindsight remains the operational baseline. MemPalace is a candidate, not an approved migration or a demonstrated improvement over the existing banks. The project itself cautions against comparing its retrieval benchmarks directly with other systems' different metrics. [Official project](https://github.com/MemPalace/mempalace).

## Source findings

The reviewed stable candidate is MemPalace **v3.11.0**, revision `602d796c699cabba2971982cd9dccbbf46abfe79`. Its native Hermes provider uses persistent palace storage, semantic retrieval, a temporal knowledge graph and MCP access to the same palace. Palace state lives outside Hermes home under `~/.mempalace`; Hermes' own backup therefore does not cover it. Source snapshots, hashes and the MIT license are retained in [the review record](../reports/memory-source-review/provenance.json). [Pinned provider source](https://github.com/MemPalace/mempalace/blob/602d796c699cabba2971982cd9dccbbf46abfe79/mempalace/integrations/hermes/__init__.py).

The provider explicitly skips `agent_context=cron/flush` and `platform=cron`. Our operator heartbeat starts a separate ordinary CLI session from **OS cron**, so that guard alone does not establish incompatibility. The actual context passed by the packaged Hermes version must be measured. Native Hermes cron requires its own check; do not change upstream context semantics to manufacture a pass. [Pinned integration tests](https://github.com/MemPalace/mempalace/blob/602d796c699cabba2971982cd9dccbbf46abfe79/tests/test_hermes_integration.py).

## Acceptance experiment

Use an isolated candidate environment and synthetic facts only:

1. Pin all candidate dependencies and CPU embedding assets. Verify Ubuntu26.04 AMD64 installation and offline startup; require no GPU or runtime application installer.
2. Record one unique fact in an OS-cron-equivalent CLI session; stop the process, then retrieve it from a second session. Check actual provider context, bounded shutdown/flush and durable acknowledgment.
3. Repeat after Workshop refresh and concurrent gateway activity. Verify both provider and MCP read the same palace and collection.
4. Add and query a synthetic relationship, invalidate it, and check temporal results and cross-session continuity.
5. Compare retrieval relevance, latency, failure recovery and resource use with Hindsight on the same synthetic corpus and queries. Do not compare incompatible published benchmark percentages.
6. Verify backup/restore of the complete palace separately from Hermes state. Keep the external append-only diary/commitment register authoritative; MemPalace's own diary is not a replacement audit boundary.

These runtime comparisons have **not passed or been executed**. No existing Hindsight bank was opened, exported, migrated or deleted. If the candidate cannot satisfy continuity and heartbeat requirements, retain Hindsight. A later coexistence test must use separate data directories; any restore or migration remains separately reviewable and requires approval.

For Hindsight, the packaged provider's embedded PostgreSQL directory is `~/.pg0`, linked to the persistent `.hindsight/pg0` mount. Installation refuses to redirect an existing database or unrelated link. Native embedded profile files may contain runtime credentials: retain their owner-only permissions, protect backups, and never put credential values in SDKs or example configuration.
