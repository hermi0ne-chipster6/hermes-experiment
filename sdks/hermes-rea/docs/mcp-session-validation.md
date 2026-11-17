# MCP, SSH and refresh acceptance

This bounded validation complements the retained installed 259-tool inventory and 93-case functional audit. It does not repeat those provider audits. The commands below are the repeatable runbook; recorded results and their artifact scope appear at the end. Use the primary operator's existing worker and retain actual results and Workshop changes/tasks/status logs. Only that operator owns worker operations and refresh.

## Inputs and retained output

- Existing Workshop project and worker, installed SDK, `rea` account, GCC fixture compiler and configured Ghidra. Current validation uses project `workshop.rea-sdk-dev`, worker `validation-65743ca5`, installed SDK `/var/lib/workshop/sdk/hermes-rea`, mounted work `/var/lib/hermes-rea/work`.
- Host-side SSH address/port, ephemeral development private-key **path**, caller-pinned known-hosts **path**, and the already-validated installed full `tools-list.json`. Do not print/copy credentials into result directories or source control. Helpers never read key bytes; OpenSSH reads the selected private-key file for authentication.
- Source helpers from `sdks/hermes-rea/tests/main/launch` and `tests/main/persistence/persistence.py`. For direct worker execution, copy `functional.py` beside `persistence.py`, or preserve their repository-relative directories. Keep test scripts on a project mount so refresh preserves access.
- A new state directory per run, for example `/var/lib/hermes-rea/work/sdk-persistence-refresh-1`. Both phases refuse to overwrite an existing phase directory. Select a new run directory after a failed preparation rather than erasing evidence.

## Ordered worker lifecycle

From the owning Workshop project, first inspect `workshop info` and confirm Ready. The operator must make the selected helper path visible inside that worker, then run:

```sh
workshop exec -I validation -- sudo -Hu rea bash -c 'cd /var/lib/hermes-rea/work && exec "$@"' -- python3 /project/persistence.py prepare --state /var/lib/hermes-rea/work/sdk-persistence-refresh-1
```

Replace `validation` with the actual Workshop definition name (the container ID is not the CLI name) and `/project/persistence.py` with the actual mounted helper path. Standard `rea` must resolve to the installed SDK wrapper. `--rea '/absolute/rea-wrapper'` is available when needed; it accepts argv with shell-like splitting, without executing a shell.

Require `prepare/results.json` to report `persistence-prepare: pass` before refresh. Preparation compiles an owned ELF, explicitly selects Ghidra, selects the single Program returned by `list_documents`, verifies addition pseudocode and ADD/RET assembly with that explicit document selector, exports authentic Evidence, saves a nonempty replayable snapshot and validates its provider/target SHA256. It closes the binary and MCP process, records exact file hashes and creates an ephemeral witness outside the state mount. This does not require an active analysis session to survive.

Apply the already-authorized public allowlist mount or SDK update as needed through the primary's existing procedure. Then perform a real refresh and retain its verification triplet:

```sh
workshop refresh validation
workshop changes
workshop tasks
workshop info validation
```

Require the relevant change/tasks to finish Done and workshop status Ready. Preserve the change ID in the acceptance record. Do not replace refresh with restarting MCP, and do not manually delete the ephemeral witness.

```sh
workshop exec -I validation -- sudo -Hu rea bash -c 'cd /var/lib/hermes-rea/work && exec "$@"' -- python3 /project/persistence.py verify --state /var/lib/hermes-rea/work/sdk-persistence-refresh-1
```

Require `verify/results.json` to report `persistence-verify: pass`. Verification requires unchanged hashes and REA ownership, disappearance of the ephemeral witness, semantic equality of imported Evidence, and an independent snapshot load after resetting the investigation. Both pseudocode and assembly must exactly match and include upstream's explicit snapshot-replay limitation: `Loaded from a local REA analysis snapshot; this call did not re-run the provider.` The binary must close successfully. Raw MCP responses, stderr, initialization and shutdown receipts stay beneath the two phase directories; `manifest.json`, `evidence-bundle.json`, `snapshot.json` and the fixture remain in the persistent state directory.

The standalone Spread job installs `gcc` and `libc6-dev` solely for fixture compilation before preparation. It then adds the inert `project-persistence-refresh` test SDK before refresh, making an SDK-list change that requires an applied lifecycle even when `try-hermes-rea` itself is unchanged. The fixture SDK has no hooks and cannot remove the witness. A primary acceptance run that installs a newly registered REA SDK revision already has the required change. An unchanged refresh is insufficient: [the CLI applies required definition/SDK changes](https://ubuntu.com/workshop/docs/reference/cli/workshop.md#ref-workshop-refresh), and [applied refresh discards the writable filesystem](https://ubuntu.com/workshop/docs/explanation/sdks/runtime-hooks.md). The inert fixture follows the documented [minimal in-project SDK definition](https://ubuntu.com/workshop/docs/reference/definition-files/sdk-definition.md).

The witness is supporting evidence of filesystem replacement; the retained Workshop refresh change is the authoritative lifecycle evidence. This checks durable analysis data and replay, not preservation of live processes, interactive debugger state or provider database edits.

## Restricted SSH and public allowlist

Run the local forced-command check as the worker's unprivileged REA account, after configuring the read-only public allowlist mount:

```sh
workshop exec -I validation -- sudo -Hu rea bash -c 'cd /var/lib/hermes-rea/work && exec "$@"' -- python3 /project/ssh_boundary.py --output /var/lib/hermes-rea/work/ssh-boundary --authorized-keys-source /etc/hermes-experiment/rea_authorized_keys
```

This requires `functional.py` beside the helper. It checks the actual installed forced-command wrapper, malformed-command rejection, bounded artifact size/hash/idempotence and mode, and absence of REA sudo privileges. The optional allowlist check requires a read-only source mount, root-owned installed allowlist, no group/world write permission, and no REA write access to either file or parent. Only metadata and mount options are inspected; no allowlist contents are logged. Without this option, no read-only allowlist claim is supported.

Run the real network check on the host, supplying existing credential paths without printing them:

```sh
python3 sdks/hermes-rea/tests/main/launch/ssh_transport.py \
  --host "$REA_TEST_SSH_HOST" --port "$REA_TEST_SSH_PORT" \
  --key "$REA_TEST_SSH_KEY_PATH" --known-hosts "$REA_TEST_KNOWN_HOSTS_PATH" \
  --expected-inventory "$REA_TEST_INSTALLED_INVENTORY_PATH" \
  --output "$REA_TEST_SSH_OUTPUT"
```

Require every row in `results.json` to pass. Strict pinned host-key checks, identity-only key authentication, disabled agent/password fallback and connection deadlines apply. The test initializes actual MCP, calls `binary_session`, checks its complete 259-name inventory against the retained independently validated installed catalog, and discovers all deferred tools in batches of at most 20 (the pinned upstream contract). Expanded `tools/list` must equal that complete inventory, excluding the `discover_tools` control. It uploads a freshly compiled ELF with artifact-v1 length/SHA256, verifies the exact receipt, and remotely disassembles its addition function with real ADD/RET instructions and unchanged artifact hash. Arbitrary shell execution must return refusal 64 and remote forwarding must fail explicitly. Optional `--ghidra` adds remote explicit-Ghidra decompilation; it is not needed for the separate snapshot proof.

An SSH connection failure does not count as shell/forwarding rejection: successful authenticated MCP/artifact/native checks are required in the same run. Catalog equality proves transport exposure, not every tool's functionality. This is the restricted REA transport boundary, not complete A/B/C routing or a general sandbox for analysis tools intentionally capable of executing processes.

Upstream requires an explicit `document` selector for these MCP primitive queries to enter the snapshot cache (`AnalysisSnapshotCache.ts`, `replayDocumentSelected` / `isSnapshotCacheable`). An initial installed preparation correctly failed with zero snapshot entries when that selector was omitted, despite producing valid Evidence. The helper now records and reuses the provider-reported document identity; the nonempty-cache and replay assertions remain mandatory.

Retained initial failure: `/root/dev/rea-sdk/validation-logs/persistence-prepare.log`; raw snapshot and MCP replies: `/home/rea-sdk-dev/.local/share/workshop/id/65743ca5/validation/mount/hermes-rea/state/work/sdk-persistence-refresh-1/`.


## Writable HOME startup regression

The mounted `/var/lib/hermes-rea` home must belong to REA with mode `0700`, allowing upstream providers to create their own state directories. Before that correction, actual ADB initialization failed to create `.android` with `Permission denied`; `/root/dev/rea-sdk/validation-logs/adb-initialization.log` retains the failure. Root should establish only the fixed mount root; creation and installation below the writable home must run as REA. The public SSH allowlist remains at its root-owned `/etc/ssh/hermes-rea/authorized_keys` path.

A writable home also permits `.bashrc`. OpenSSH invokes `ForceCommand` through the account login shell with `-c`; Bash can read `.bashrc` under sshd even for a noninteractive command. `PermitUserRC no` only addresses `.ssh/rc`. The account therefore uses `/bin/sh`, including correction of an existing account, while the installed forced-command wrapper retains its Bash shebang. This is the startup behavior documented by the installed `bash(1)` and `sshd_config(5)` manuals.

Use the new `tests/main/launch/ssh_home_probe.py` as REA with the correct HOME. It requires REA ownership/mode `0700` and passwd login shell `/bin/sh`. Select a fresh state directory:

```sh
workshop exec -I validation -- sudo -Hu rea python3 /project/ssh_home_probe.py prepare --state /var/lib/hermes-rea/work/ssh-home-probe-1
# Run and retain the actual authenticated SSH transport checks above here.
workshop exec -I validation -- sudo -Hu rea python3 /project/ssh_home_probe.py verify --state /var/lib/hermes-rea/work/ssh-home-probe-1
```

Preparation refuses existing `.bashrc` or `.ssh/rc`, including dangling links; it never replaces them. It creates two harmless scripts whose only action, if sourced, is writing a marker inside the private probe output directory. A pre-existing `.ssh` directory must be a REA-owned directory without group/world write access. The manifest records created-file identity and directory ownership without opening or enumerating any key files. Verification requires both probes to remain in place and both markers to be absent. A separately retained successful SSH run between phases is mandatory; marker absence alone proves nothing about SSH.

Verification always attempts cleanup, including on a failed assertion. It removes only the recorded inode/device/owner/type/mode of each created startup file and removes `.ssh` only if the probe created it and it is still empty. Replacement files, replacement directory symlinks, and unrelated directory contents are preserved and reported. If the SSH run is interrupted, execute the explicit cleanup phase (it remains usable if HOME permissions or login shell have regressed):

```sh
workshop exec -I validation -- sudo -Hu rea python3 /project/ssh_home_probe.py cleanup --state /var/lib/hermes-rea/work/ssh-home-probe-1
```

Retain `manifest.json` and `prepare-results.json`, `verify-results.json` or `cleanup-results.json`. Local syntax/help checks and cleanup safety checks pass. The actual worker prepare → authenticated SSH → verify result is recorded separately below, because the HOME and login-shell corrections were applied live to the historical installation.

## Recorded installed validation, 2026-11-17

These results cover the existing installed artifact SHA256 `77fc26d1660fe359511d41a3cc06c76d6224be8dda9b80367261bed61cad5af3`, identified in `/root/dev/rea-sdk/validation-logs/pre-policy-artifact.json` (the moving `final-artifact.json` now describes a later build). The later rebuilt final artifact still requires its own installation and acceptance checks; these results must not be attributed to that replacement artifact.

The corrected persistence run passed both phases. Workshop **change 56: Done; status: Ready**, with the inert `persistence-refresh` SDK addition forcing an applied refresh. `/root/dev/rea-sdk/validation-logs/refresh-persistence-and-ssh.log` retains the actual refresh tasks, read-only configuration remount/import and verification output. Raw phase replies and the manifest are retained at `/home/rea-sdk-dev/.local/share/workshop/id/65743ca5/validation/mount/hermes-rea/state/work/sdk-persistence-refresh-2/`.

The snapshot contains exactly two bindings: `procedure_pseudo_code` and `procedure_assembly`, using the explicit provider-reported document. Evidence `ev_6aa21c0d7ca9e96c1c1239d4e47a1562fc429058fcfcb58da8abec416e43e439` re-imported with identical semantics. Both post-refresh raw query replies match the saved outputs and contain the exact upstream replay limitation. All four fixture/export files retain their hashes and REA UID 999 (host-mapped UID 1000999); the ephemeral witness is gone. Both MCP processes shut down on stdin EOF with exit code 0. Independent read-only review recomputed the four hashes and inspected both replay replies.

| Durable file | SHA256 after refresh |
| --- | --- |
| `fixture.c` | `99bf3ea1d94211878e1fa857ab107a32e1c4adb8c4471feb55ac88761282b529` |
| `fixture` | `fc5116a9a73746adfeda6a83d77fff3f54aceca60844ad238b7d98891c05c52f` |
| `snapshot.json` | `3e47717806d61d161f78bbfb79bc8c62f55f6105145791806050b2ccd1e0e0a3` |
| `evidence-bundle.json` | `55a242d520f7e8f5077ffe15cc3a0852ec8219bf0e4ab6d2ef307fbcb897d73e` |

The six local SSH boundary cases passed in the same refresh log: native version/MCP, seven malformed remote commands plus extra local arguments, bounded artifact validation, no REA sudo policy, and read-only public-allowlist metadata. The source mount reports `ro,relatime`; the imported allowlist is root-owned mode `0644`; REA cannot write either file or parent. Key contents were not read by the helper.

The actual network SSH run also passed **6/6 cases**, with process exit `0` and clean MCP stdin-EOF shutdown. Evidence: `/root/dev/rea-sdk/validation-logs/ssh-network-installed.log`, `/root/dev/rea-sdk/validation-logs/ssh-network-installed.exit`, and raw files under `/root/dev/rea-sdk/validation-logs/ssh-network-installed/`. Authenticated MCP exposed exactly 259 names, matching both `binary_session` and the independently validated installed catalog. This run used the full catalog profile, so deferred discovery was not exercised. The 17,008-byte transferred ELF matched SHA256 `6f28fe363f8569b661f3b2cd7c84da7ee06e817267aa5216a70b3ae42db40c38`; real remote objdump produced ADD/RET and explicit Ghidra produced addition pseudocode. Arbitrary shell execution was refused with exit `64`; remote forwarding was refused with exit `255` and the explicit diagnostic `remote port forwarding failed for listen port 0`. Independent review verified the raw catalog equality, local fixture size/hash, normalized pseudocode, rejection diagnostics and clean shutdown. No transport or persistence acceptance failures remain for this existing-artifact run; replacement-artifact acceptance remains pending.


### Live HOME and login-shell regression, 2026-11-17

After applying the writable-home and `/bin/sh` account-shell corrections to the existing installation, `ssh-home-prepare` and `ssh-home-verify` both passed; verification reports `cleanup: complete`, and `/root/dev/rea-sdk/validation-logs/ssh-home-probe.exit` is `0`. The real authenticated SSH run between those phases passed all **6/6 cases**, including Ghidra, arbitrary-shell refusal `64` and forwarding refusal `255`; `/root/dev/rea-sdk/validation-logs/ssh-network-home-fixed.exit` is `0`. MCP shut down on stdin EOF with exit `0`.

Evidence is retained in `/root/dev/rea-sdk/validation-logs/ssh-home-probe.log`, `/root/dev/rea-sdk/validation-logs/ssh-network-home-fixed.log`, raw replies under `/root/dev/rea-sdk/validation-logs/ssh-network-home-fixed/`, and the probe manifest/results under `/home/rea-sdk-dev/.local/share/workshop/id/65743ca5/validation/mount/hermes-rea/state/work/ssh-home-probe-1/`. The transferred 17,008-byte ELF has SHA256 `6e3369bfa37f71008dc839debf162d0059d5891be3b7f2fe2761c7d3a386dae8`.

Independent read-only review confirmed home mode `0700` and mapped REA ownership, absence of both sourced markers, removal of the two created startup files and the empty probe-created `.ssh` directory, all six SSH results, both exit receipts, artifact hash/size and clean MCP shutdown. No key files were read or enumerated. Review of the updated source hooks found no additional actionable defect: both new and existing accounts receive `/bin/sh`, root adjusts only the fixed home directory, all descendant directory/plugin installations run as REA, and the public allowlist remains at the read-only-input/root-owned-output boundary outside HOME.

This is validation of **live corrections on the historical `77fc26d…` installation**, not proof that the corrected hooks are present in an installed final package. Exact archived-hook verification, final-package installation and post-install acceptance remain pending.


### Subsequent artifact boundary and remaining acceptance

The later cold build SHA256 `c7373502e97f32c34be99ba7fd92e7ea5832caf31121aa79a747badd27cf22c5` installed into `validation-final-782b8b9c`. Its functional run verified exactly **259 MCP tools**, operational `binary_session` inventory equality, and packaged canonical contract equality. The result is retained in `sdk-validation-final/results.json` beneath that worker's persistent work directory. This is operational session/catalog evidence, not proof that all advertised tool operations work.

That run exposed the Frida 17.23.2 child-reaping defect described in [Frida sequencing validation](frida-sequencing-validation.md). A complete official Frida 17.25.1 compatibility runtime passes the direct and mixed-provider reproductions. A final corrected SDK still needs its own installed identity, complete suite, refresh persistence, authenticated network SSH and startup-file regression results. Earlier `77fc26d…` persistence/SSH passes remain useful historical evidence and must not be relabeled as results for the corrected artifact.

See [the final MCP acceptance review](mcp-final-review.md) for the exact remaining runbook gates and bounded script corrections identified without changing shared infrastructure.
