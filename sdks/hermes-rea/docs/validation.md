# Hermes REA validation record

The Frida 17.25.1 artifact passed the archive comparison and a fresh Workshop installation and was published as revision 2 on `latest/edge`. The 130-case run recorded 122 initial passes and eight targeted retry passes. See the [edge release notes](edge-release-notes.md) and [per-case results](edge-functional-results.md). The records below preserve the earlier builds and failure investigations.

This report distinguishes source checks, earlier installed-runtime evidence, and final artifact acceptance. A registered tool, version probe or successful command alone is not counted as provider functionality. The [capability matrix](capability-matrix.md) covers all 78 upstream capability keys and the 48-format inventory, with bounded semantic results in [the coverage map](capability-coverage.json).

## Identity and source

- Existing repository: `hermi0ne-chipster6/hermes-experiment`, original commit `df4d6499ec01be2cf003841a4eac0d471fe4109b`.
- Development branch: `dev/hermes-rea-full-parity`.
- Unmodified REA baseline: `51459cf203ae1eb6b586a95b21899eaa0f631823`, version 6.9.0. This includes changes beyond the npm 6.9.0 release tag.
- Complete source: 14,149 tracked entries, 135,520,255 bytes, six repositories including five pinned submodules. All exported file/blob hashes, executable modes and symlinks were verified. The source CLI performed a real JavaScript graph operation.
- The rebuilt complete-source archive reproduced SHA256 `b0a9711bd858c3be9ad4d0bf9e9e400108e21f4807d54c1587cd19522dc4a70a`.

## Build and test routes

| Route | Actual result | Evidence / boundary |
| --- | --- | --- |
| Source validation | Passed; 125 repository regression tests, JSON/YAML/shell validation and diff checks | Latest `validation-logs/source-ci-frida.{log,exit}`: 125 tests, OK, exit0; earlier coordinated/HOME results retained |
| First complete SDK build | Passed `sdkcraft try`, build 7, exit 0 | `validation-logs/parity-build-7.exit` |
| Official `sdkcraft test` | Packaging/linting passed; VM allocation failed before provider tests | Exit 1, **0 successful and 91 aborted jobs**; `official-sdkcraft-test.{log,exit}` |
| Updated official test discovery | Passed; 97 unique jobs | `source-ci-frida.log`; discovery is not execution. The older `final-test-discovery.log` contains the earlier 91-job inventory |
| First clean Workshop install | Passed using `rea-sdk-dev`, launch change 17 Done/Ready | Owned instance `validation-65743ca5`, project `workshop.rea-sdk-dev`; initial dependency preflight preceded fixture compiler installation |
| Policy/HOME-corrected full cold build | Passed official `sdkcraft pack --verbose`, exit0; artifact c7373502 full digest below | `validation-logs/rebuild-final.{log,exit}`; metadata, hooks, source archive and NativeAOT JAR verified before registration |
| Policy/HOME-corrected fresh installation | Passed; launch change 78 Done/Ready; preflight exit0 | `final-launch*.log`, `final-preflight.exit`; ordinary-user Workshop `validation-final-782b8b9c`; diagnostics/library checks ran before test compilers were installed |
| Corrected Frida replacement | Passed SDKcraft pack, archive comparison and fresh Workshop installation | [Revision 2 receipt](edge-publication.json) and [edge results](edge-functional-results.md) |

The official suite retains its supported `vm: true` LXD backend. This VPS has no usable `/dev/kvm`; LXD reported `Instance type "virtual-machine" is not supported on this server: KVM support is missing (no /dev/kvm)`. Aborted jobs are not passes and do not diagnose provider failures. The final suite must still run on a supported KVM-enabled runner before that acceptance gate can be closed.

All long jobs run in tmux session `hermes-rea-validation`. The safe checkpoint at `/root/dev/rea-sdk/checkpoints/20261117T171942Z` retains the working tree, binary diff, source hashes, original index and Git bundle. Parallel contributions used isolated worktrees and scoped commits; primary integration and infrastructure operations are recorded in `validation-logs/coordination/`.

## Earlier installed artifact: operational evidence

These results used artifact SHA256 `77fc26d1660fe359511d41a3cc06c76d6224be8dda9b80367261bed61cad5af3`. The two packet cases required a scoped live AppArmor correction; their pass does not establish that correction was present in this earlier artifact. Replacement-artifact acceptance is separate.

| Functional proof | Actual result | Evidence / scope |
| --- | --- | --- |
| CLI diagnostics | `doctor`, `providers`, `capabilities` JSON contracts passed; doctor reported 15/18 healthy checks | Optional Hopper/IDA and client-skill configuration remain explicit; see retained preflight/CLI JSON |
| Full MCP catalog | Exact 259-tool equality with packaged contracts and `binary_session` inventory | Registration proof only; operations below supply separate functionality evidence |
| Main functional cases | 93 selected cases passed across retained first-run/retry records | Includes native Ghidra/Kuna/Rizin/GDB/Cutter/Frida, JavaScript/Wakaru, .NET/ILSpy, APK/JADX/Apktool, firmware extraction, WASM, browser/Electron/runtime evidence, static formats and desktop capture. Per-case assertions and limits are in the matrix |
| TShark policy | Both real DNS packet cases passed after live correction; profile remained enforced and an unauthorized write remained denied | `tshark-policy-{tests,proof,negative-audit}.log`; fresh c7373502 packaged-policy proof subsequently passed |
| NativeAOT extension | All eight unchanged upstream verifier modes passed | Symbol and stripped oracle recovery, ordinary/nonapplicable, unsupported, malformed, ambiguous, loader failure and default-native behavior; [full proof](nativeaot-validation.md) |
| Actual Workshop refresh | Prepare/verify passed; change 56 Done/Ready | Four file hashes and ownership retained, ephemeral witness removed, Evidence imported, two explicit-document Ghidra queries replayed with exact snapshot provenance; [session proof](mcp-session-validation.md) |
| Local SSH boundary | 6/6 passed | CLI/MCP dispatch, bounded artifact input, command rejection, lack of worker sudo and read-only public allowlist/root ownership |
| Network SSH | 6/6 passed | Pinned host key, authenticated MCP/exact 259-tool catalog, SHA-verified ELF upload, native disassembly, explicit Ghidra, shell exit 64 and forwarding exit 255 rejection |
| Finite reconstruction verification | Passed standalone; integrated as the 95th fresh-suite case | Real accepted/rejected/mixed/unknown outcomes, residual Unknown propagation, canonical claim digest and exact Evidence closure; [bounded proof](reconstruction-validation.md) |

The main 93-case aggregate is not a single clean final run. Original failures remain preserved. NativeAOT, SSH, persistence and reconstruction proofs are supplemental results, not additions to the official Spread success count.

## Retained evidence archives

All paths below are under `/root/dev/rea-sdk/validation-logs/installed-functional/` and contain owned synthetic fixtures/results, not private keys.

| Archive | SHA256 |
| --- | --- |
| `first-installed-evidence.tar.gz` | `ccfa96e601ff0c2a573412659e7b93703bb0de42e3baff198a97c2e6eedd3883` |
| `tshark-policy-evidence.tar.gz` | `9f61ff31d3a653e6bafe6cc200842ec289164880b990ff65e3ff4d128bfa7c2a` |
| `nativeaot-evidence.tar.gz` | `aa51b16ab9530e828f0d77de1293d68b912ea78478b1de2a500a8e095d9829a6` |
| `session-ssh-evidence.tar.gz` | `195b0ebf5987465ac0f4d656e60aece92317be6d4ecfd6ad3e83f1b289d5f083` |
| `reconstruction-evidence.tar.gz` | `c062208c2578ce08f6426370085e4536cd728b9e29e0d73c83399ab6526ea58f` |
| `policy-build-and-frida-evidence.tar.gz` | `c7b03a4b8e770aceb1ee2e2b3aa4e948b21533712adf2835ce74228c67bd3773` |

## Observed failures and corrections

- Root-launched Workshop failed at the LXCFS mount helper with host UID 0 mapped to guest UID 1000. A dedicated ordinary developer account reached Ready using standard Workshop configuration; no host daemon privilege workaround was applied. See `validation-logs/docker-workshop-probe/assessment.md` and its sanitized mount diagnostics.
- Automated Workshop commands needed both `exec -I` and stdin from `/dev/null` when launched inside tmux. The helper records this invocation explicitly.
- Early functional failures included fixture prerequisites and contract mistakes: GCC needed libc6-dev, Apktool 3 needed its current metadata shape, browser source paths and JADX method selection needed the real schemas, and Ghidra assembly assertions needed actual instruction text. Those attempts and successful corrections remain in the main archive.
- The TShark failure was a packaging policy defect: Ubuntu confinement denied inherited Node Unix sockets and declared capture paths. The source adds a narrow local include while preserving enforcement and unrelated local policy. No upstream REA patch or provider substitution was used.
- The first NativeAOT attempt failed before engine execution because the proof-support manifest omitted upstream `#dist` imports. The helper now copies unchanged installed package metadata; all eight unmodified verifier modes passed without a timeout adapter.
- The initial persistence fixture saved Evidence but zero cached primitive queries. Upstream snapshot eligibility requires an explicit document selector. The corrected fixture records two entries and proves replay after a real refresh.
- The first reconstruction fixture shared source Evidence between independent expectations. A changed comparison correctly propagated a residual Unknown into a later claim. Corrected independent pairs preserve strict pass/fail assertions, and an additional case deliberately verifies that propagation.

An earlier nested-container fallback probe installed LXD and Workshop but stalled creating the inner dir storage pool, including a bounded retry after stopping inner Workshop. No nested Workshop installation was achieved. This is a recorded host result, not a general LXD limitation. Its diagnostics remain in `nested-probe-assessment.md`, `nested-spread-investigation.log`, `nested-lxd-stall.log`, `nested-lxd-operations.log` and `nested-workshop-stop-probe.log`. The stopped disposable probe was removed only after retaining evidence.

## Desktop and external boundaries

Canonical `docker-ce` precedes `try-hermes-rea` in the full-engine Workshop definition. Its revision 13 metadata reports 29.5.1; the installed engine reported 29.10.0. Both its client and the packaged Docker 29.1.3 client executed real `hello-world` successfully, using image digest `sha256:1e4c05b897a751332ce85c7e9449da2d93514ea2dea6dbb0e2753c9e949b2bfa`. That early result established Docker execution only. The later `desktop-final2` case proved a real REA/AgentEnv computer, owned xterm typing, retained before/after INI values, decoded 1280×800 screenshots and confirmed teardown. Its runtime archive SHA256 is `2a9ffacca7ff13c5fb3398521226c383a09f88eca2cab02bf07a6248ae2ca638`. The first desktop fixture discarded the outer action response while unwrapping a nested result, producing a `computer_id` KeyError; its cleanup succeeded. Correcting the fixture decoder yielded the real pass without modifying REA. This is model-free execution, not model-driven solve/measure proof.

Licensed Hopper/IDA/JEB installations, selected Android devices, model-service configuration and native macOS/Windows execution remain separate explicit boundaries. Static Apple/Windows format analysis, recorded signals and local synthetic runtime targets are not claims about live foreign-platform or physical-device execution. See [provider parity review](provider-parity-review.md) for categorized causes and source references.

## Worker HOME and restricted SSH regression

Provider initialization exposed a packaging defect: the persistent HOME mount was owned by the Workshop user, so ADB failed to create `.android`. Setup now owns the fixed HOME mount as `rea:rea` with mode 0700 and performs all descendant directory/plugin writes as `rea`. The root-owned public SSH allowlist remains outside HOME. The account login shell is `/bin/sh`, preventing Bash from sourcing worker-controlled `.bashrc` before SSH's forced command.

The live corrected setup started ADB successfully. All 125 repository tests passed after these changes (`source-ci-home-fix.log`, exit0). A second actual authenticated SSH run passed all 6 checks, including Ghidra analysis, exact 259-tool parity and blocked shell/forwarding. Prepared harmless `.bashrc` and `.ssh/rc` probes were not sourced, and cleanup removed only the owned probe files. These SSH passes used live corrections on the previous artifact. The c7373502 artifact subsequently passed exact packaged-hook verification, fresh installation and ADB initialization; replacement-artifact SSH acceptance remains separate. The standalone ADB regression is also integrated as case 96; its initial listen-argument and directory-mode fixture assumptions were corrected to match the installed upstream ADB contract, retaining both failed attempts.

The integrated standalone `tshark-policy` case passed after restoring the exact source policy on the development worker. Its pre-correction run failed on the inherited Unix socket check, while valid stdin decoding passed. After correction, `tshark (enforce)`, valid capture round-trip, socket output and outside-work write refusal (exit 9) all passed. The helper is independent of other packet cases and is now case 97 plus a dedicated Spread variant.

Two isolated CLI cases passed on the installed engine: `cli-setup` installed all nine packaged skill files byte-for-byte, reported aligned skill version62, and left them unchanged on repeat; `cli-evidence` published a real JavaScript graph bundle, preserved its exact identities/content through import/export, and refused an existing destination with typed invalid-input error and exit1. These are cases98 and99 in fresh acceptance; no external client configuration or model service was used.

## Final build and storage checkpoint

The policy/HOME-corrected full cold `sdkcraft pack --verbose` completed successfully at approximately19:15UTC, with native compilation, source priming, linting and archive creation successful (`rebuild-final.exit`:0). Artifact verification, local `sdkcraft try` registration and fresh installation then passed. The 1,695,103,384-byte artifact SHA256 is `c7373502e97f32c34be99ba7fd92e7ea5832caf31121aa79a747badd27cf22c5`. This artifact retains upstream Frida 17.23.2 and is not the pending corrected-Frida package. Cleaning the completed builder freed its ZFS blocks; native `zpool trim` reclaimed the unused backing-file extents, leaving approximately16GB physically free and the pool ONLINE with no known data errors (`trim-completed-builder-space.log`, exit0). This uses the [documented OpenZFS TRIM operation](https://openzfs.github.io/openzfs-docs/Basic%20Concepts/Operations/TRIM.html), not a fabricated desktop capacity result.


## Fresh policy artifact and Frida sequencing correction

The first c7373502 suite passed 17 cases, including actual Frida injection, then a SQLite MCP request timed out after 180 seconds with an unreaped `ps` child. The remaining 81 selected cases were aborted, not independently observed failures. The owned MCP harness exhausted EOF/TERM shutdown and used its bounded kill; no package installation or build was interrupted. A fresh MCP process then passed 81 of 82 remaining cases, with the desktop fixture correction and rerun passing the final case. These 99 individual passes across runs do not conceal the failed process sequence.

The direct diagnostic reproduced the original Frida 17.23.2 failure in 15 of 37 records. It holds an owned Node sentinel alive while checking child exit delivery around Frida import, spawn, attach, script load/unload, resume, detach and target exit. A separate scratch runtime with the complete official Frida 17.25.1 npm package and matching Linux x64 native addon passed all 37 records. Its actual REA MCP session then passed JavaScript, Frida enumeration, injection, SQLite exact-row inspection, and Ghidra decompilation/snapshot reopen in one process. The scratch preparation verified 3,550 REA engine files unchanged; the installed SDK was not overwritten. See [Frida compatibility](frida-compatibility.md) and [sequencing validation](frida-sequencing-validation.md).

The updated source recipe discloses this provider override while preserving the original REA package, lock and source export. Final acceptance requires the replacement SDK contents and installed hashes to match, the 100-case suite including `frida-process-lifecycle` to pass, the persistence/SSH boundary to remain sound, and an independent clean reinstall. The official KVM-backed `sdkcraft test` gate is still unavailable on this VPS.

The new `policy-build-and-frida-evidence.tar.gz` archive retains `preflight-final`, `sdk-validation-final`, `sdk-validation-final-remaining`, `frida-process-baseline`, `frida-process-fixed`, `frida-mixed-fixed` and `desktop-final2`. Its digest above was checked against the actual archive. Baseline installed failures, aborted results, corrected fixture results and scratch-provider qualifiers are retained separately inside it.

## Historical worker retirement and retained state

After the evidence archive was verified, the two historical workers were stopped, their entire REA state mounts were relocated through official Workshop remount operations, and the disposable workers were removed through Workshop. The retained directories are:

- `/home/rea-sdk-dev/preserved-state/validation-65743ca5`
- `/home/rea-sdk-dev/preserved-state/validation-final-782b8b9c`

Both contain their original `work/` trees. Existing logs may name their former Workshop-managed mount paths; resolve the suffix below the old `state/` directory against the matching preserved directory. Raw evidence archives remain unchanged. Whole worker state is private local material and is not a release artifact; the selected evidence archives exclude private keys. The operation records are `retire-validation{,-final}-{stop,remount,remove}.log` and `retire-historical-workers*.log`. Completed removal shows each Workshop Off; neither old worker should be treated as a currently running validation environment.
