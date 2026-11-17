# Local CLI workflow validation

Status: both cases passed against the installed historical artifact `77fc26d1660fe359511d41a3cc06c76d6224be8dda9b80367261bed61cad5af3`, with live HOME/shell setup and AppArmor fixes. Final rebuilt-package acceptance remains pending. These are executed semantic results, not passes inferred from CLI registration, help, or the existing version/doctor/providers/capabilities checks.

The helper `tests/main/launch/cli_cases.py` registers `cli-setup` and `cli-evidence` through `run_cli_cases(command, output, work, test)`. The parent functional runner supplies its existing `test(case_id, callable)` callback. Each callable returns a semantic result dictionary and writes `cli-setup-result.json` or `cli-evidence-result.json` under `output` only after its assertions pass.

Standalone invocation, as the installed unprivileged `rea` account:

```sh
python3 cli_cases.py --rea /usr/local/bin/rea --output /work/cli-results --work /work/cli-fixtures
```

Optional `--case cli-setup` or `--case cli-evidence` selects one case. Direct upstream Node invocations are also supported through `--rea 'node /absolute/package/scripts/rea.mjs'`. The setup case resolves canonical skill assets from that actual package or the SDK wrapper target; it does not supply substitute assets.

Each case owns a new private directory under `work`, retained for review, and a `rea`-owned mode-0700 HOME. All XDG roots and temporary files are placed there. Child environments are built from an allowlist rather than inheriting client roots, credentials, provider overrides, or Node startup options. All child commands run from the fixture directory. Update notices are disabled through upstream-supported `CI` and `NO_UPDATE_NOTIFIER`. The SDK wrapper supplies normal packaged provider defaults. Only the selected shared skill is writable through setup; no `--client`, `--all-detected`, Hopper installation, desktop setup, or package update is requested. Upstream discovery can still read fixed system-wide client configuration locations; no client registrations are selected or written. The helper does not modify the actual runtime HOME. The ADB initialization case separately checks that HOME's ownership and usability.

## `cli-setup`

Executes `setup --skill-client shared --yes --json`, `doctor --skill --json`, then the same setup command again. Requires initial `status: ready`, exactly `installed_skill`, no configured clients, exactly the nine upstream managed skill files, byte equality to the installed package's canonical skill directory, owned non-world/group-writable regular files, aligned skill version, and healthy scoped doctor. The repeat must produce no applied actions and preserve file hashes and modification times.

Pinned REA 6.9.0 contracts at upstream commit `51459cf203ae1eb6b586a95b21899eaa0f631823`:

- `src/cli/setupCommands.ts`: `--skill-client shared` selects an explicitly empty client-registration list, approval, and scoped skill readiness.
- `src/application/SetupSkill.ts`: `MANAGED_SKILL_FILES` has nine entries, loaded relative to `../../skills/reverse-engineer-anything`; installation publishes and verifies those assets.
- `src/application/SupportedClients.ts`: shared destination resolves to `HOME/.agents/skills`.
- `src/application/Setup.ts`, `SetupTypes.ts`, and `Doctor.ts`: applied action, idempotence, and `identity.skill.state: aligned` contracts.

This checks bundled asset placement, user-owned publication, and CLI setup execution. It does not prove a real external agent discovers the skill, an MCP client registration works, or an external licensed provider/model is configured.

## `cli-evidence`

Creates an independent two-module CommonJS application with an Electron IPC declaration named `hermes-cli-evidence-marker`. Executes static `analyze-javascript-application` with `--detail summary --evidence_output`, then `evidence-import`, `evidence-export`, and an export to the already occupied destination without `--overwrite`.

Requires the delivered summary to be an `inspect_analysis_view` Evidence record whose `parameters.parent_evidence_id` and sole Evidence link identify the complete analysis in the bundle. Checks the expected source operation and actual IPC/module graph semantics, unique retained identities, no dangling Evidence links, and every retained record reachable from that source root. The derived summary is a presentation record and need not itself be in the published source bundle. Import counts must equal actual records and Unknown revisions. The exported bundle must preserve all parsed content and identities; publication receipts must match file paths and byte counts, and export counts must match records and Unknown revisions. The occupied destination must return `code: invalid_request`, `category: invalid_input`, and `details` identifying `operation: write`, `reason: exists`, and the exact path. Source and destination bytes must remain unchanged. Its exit code must be 1: `src/cliLogging.ts` recognizes this projected failure and sets `process.exitCode ||= 1`, while `src/cli/runCliCommand.ts` also sets exit 1 for an output error. The installed run recorded 1; the explicit assertion was added after reviewing that evidence and its owning source.

Owners: `src/cli/electronCommands.ts`, `analysisEvidenceDelivery.ts`, `src/cliEvidenceCommands.ts`, `src/application/EvidenceBundleCommands.ts`, `EvidenceBundleFiles.ts`, `src/domain/evidenceBundle.ts`, and `analysisErrorProjection.ts`. No model, network target, Electron runtime, or mock tool registration is used.

## Evidence retention and acceptance

Every command retains numbered `.stdout`, `.stderr`, and `.exit` files in its unique case directory. Successful result JSON records that directory and semantic assertions. The fixture HOME, nine installed skill files, synthetic source application, and Evidence bundles remain available for independent inspection. This helper never removes a pre-existing directory or calls `uninstall`.

Local preparation checks cover Python syntax, standalone help, and equality of the helper's nine-file list to pinned `MANAGED_SKILL_FILES`. Raw installed evidence was subsequently reviewed independently, as recorded below. Final rebuilt-artifact acceptance remains distinct from this run against an earlier installation with live setup fixes.

## Installed results

Run log: `/root/dev/rea-sdk/validation-logs/cli-regressions.log`; exit record: `/root/dev/rea-sdk/validation-logs/cli-regressions.exit` (0).

Host-visible raw evidence root: `/home/rea-sdk-dev/.local/share/workshop/id/65743ca5/validation/mount/hermes-rea/state/work/cli-regressions`, corresponding to `/var/lib/hermes-rea/work/cli-regressions` inside the worker.

- `cli-setup` passed in 34.579 seconds. Raw commands are under `fixtures/cli-setup-r_629y66`: `01-setup`, `02-doctor-skill`, and `03-setup-repeat`, each with stdout/stderr/exit. All three exited 0. Initial setup applied only `installed_skill`; repeat applied nothing; both configured zero clients. Scoped doctor reported healthy and aligned skill version `62`. All nine retained skill files match the hashes recorded in `cli-setup-result.json`; the helper also checked canonical package byte equality and unchanged repeat modification times. Result JSON SHA256: `b0f28078df851435974c9ff56b02ef61a94ee3d342f1ccfc0ea43b644c02a463`.
- `cli-evidence` passed in 13.661 seconds. Raw commands are under `fixtures/cli-evidence-y8ijcvbt`: `01-analyze`, `02-import`, `03-export`, and `04-no-overwrite`. The first three exited 0 and the typed refusal exited 1. The source bundle has one complete `analyze_javascript_application` record, no Unknown revisions, and the expected IPC marker and both modules. The summary links that exact retained source identity: `ev_ebb67a0cbe4e8837008312c68ece6e7b7700c24328c6f30c8114024bc9a60539`. Source and exported bundle are byte-identical, 113,082 bytes, SHA256 `e9006ac5d9d140a7b0ccffdb6e9bd76bd1e722b88d9ac9e1fd37f66ae580ef55`. Independent review verified the actual records, summary parent/link, import/export counts, typed refusal, and both retained files. Result JSON SHA256: `7e320638eadba40689c888c9668955ba73c18af5aac07303c4407fd70e48452e`.

No external client activation, model inference, Electron runtime, or final fresh-artifact claim follows from these two passes.
