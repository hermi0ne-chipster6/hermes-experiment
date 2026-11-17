# Desktop acceptance

The fixtures use unchanged REA `51459cf203ae1eb6b586a95b21899eaa0f631823`
(6.9.0). `desktop-dconf` and `desktop-capture` exercise an owned local database
and X11 application. `desktop-build` separately exercises the actual AgentEnv
computer lifecycle through the installed REA MCP server, using xterm as its
owned application. No model endpoint is required for this lifecycle.

## Live build recipe

Run inside the installed Workshop as its normal user, with the official Docker
SDK connected and its daemon reachable. Set `TESTS` to the mounted SDK `tests`
directory, including `functional.py`, `desktop_cases.py`, `desktop_image.py` and
the other launch helpers. Use a persistent validation tmux window; first builds
can take many minutes.

```bash
SDK=/var/lib/workshop/sdk/hermes-rea
OUTPUT=$(mktemp -d /var/lib/hermes-rea/work/desktop-validation.XXXXXX)
python3 "$TESTS/main/launch/functional.py" \
    --rea rea --node "$SDK/node/bin/node" \
    --package-root "$SDK/rea/node_modules/rea-agents" \
    --output "$OUTPUT" --only desktop-build --require desktop-build \
    > "$OUTPUT/functional.stdout" 2> "$OUTPUT/functional.stderr"
```

The fixture first records the actual `rea doctor --provider desktop_build --json`
output and exit code. Upstream requires a reachable Docker daemon and at least
20,000,000,000 free bytes where Docker stores data. If either check refuses, the
test records `unavailable` and this required run exits nonzero before an image
pull or build. Capacity must be resolved on the real host; the fixture provides
no readiness override. Other doctor findings remain in the retained report.

When admitted, the fixture uses the unchanged installed runtime-archive producer
unless `REA_BUILD_COMPUTER_REA_ARCHIVE` explicitly supplies an existing archive.
It records that archive's SHA256. A successful run must prove all of these:

- `start_build_computer` creates an actual AgentEnv sandbox from the xterm package
  request and returns a screenshot.
- `start_build_capture` launches xterm with the owned shell command and returns
  its open-window screenshot; it explicitly retains `sdk-build-fixture.ini`.
- The `seed` checkpoint retains file bytes. Computer typing submits
  `hermes-build-after` to the waiting application, and the subsequent screenshot
  is returned by the live driver.
- The `end` checkpoint names the changed INI file and retains bytes.
  `stop_build_capture` returns the exact `hermes-build-before` to
  `hermes-build-after` structured value change in its seed/end draft.
- The installed AgentEnv Pillow dependency verifies and decodes every returned
  image, recording format, dimensions, byte count and SHA256.
- `close_build_computer` confirms teardown through `agentenv` or
  `container_label`. Process termination alone is not accepted as teardown.

Every successful tool result must identify the same computer. The desktop
decoder preserves the direct tool contract: an action's nested `result` holds
driver details, while `computer_id`, `action` and `action_index` remain at the
top level. Typing and wait must report the requested actions in consecutive
action-log positions. Full MCP responses,
screenshots, doctor output and MCP stderr remain under `desktop-build/`; the
functional harness writes `results.json` with `pass`, `fail` or `unavailable`.
Failed-start responses with an explicit computer UUID trigger a cleanup retry.
Cleanup failure remains a failure and its response is retained.

## Evidence boundaries

The installed runtime-archive producer and native CLI initialization have passed
in the parent validation record. Local Docker `hello-world` has also passed,
independently of this fixture. Those checks do not establish a desktop-build pass.

On 2026-11-17, the first actual lifecycle run passed the real prerequisites and
created computer `0bfbf499-1aba-474e-bcc1-1105952b9ac3` in AgentEnv sandbox
`local-bb3a1957`. The preserved responses `001` through `004` show initial and
capture screenshots, a seed checkpoint retaining one 37-byte INI file, and
typing accepted by the live driver (`applied: yes`). The fixture then failed
with `KeyError: computer_id`: its generic decoder unwrapped the action's domain
`result`, discarding the outer computer identity. This was a fixture error, not
an engine failure. The direct desktop decoder fixes that inappropriate
unwrapping without altering REA.

The first attempt remains at Workshop `782b8b9c`, under
`work/sdk-validation-final-remaining/desktop-build/`. Response `005` and
`cleanup-result.json` confirm teardown through `agentenv`; `mcp-shutdown.json`
records stdin-EOF shutdown with exit zero. Preserve that directory and use a
fresh output directory for the corrected rerun. This attempt does not establish
the wait, end checkpoint, stopped-capture draft, or complete lifecycle pass.

The remaining assertions were reviewed against pinned upstream
`src/contracts/desktopBuildToolContracts.ts`,
`src/contracts/desktopBuildTaskSchemas.ts`,
`src/domain/desktop/appTaskDraftValues.ts`,
`src/application/desktop/DesktopBuildComputers.ts`, and
`src/application/desktop/DesktopBuildCapture.ts`. They use the defined wait
arguments, checkpoint retained counts/relative changed-file paths, stop package
and seed/end draft fields, scalar before/after values, and confirmed teardown
enum. Source review is preparation for the rerun, not runtime acceptance.

## Successful corrected lifecycle

The corrected fixture passed on 2026-11-17 in 119.333 seconds against the
installed SDK artifact with SHA256
`c7373502e97f32c34be99ba7fd92e7ea5832caf31121aa79a747badd27cf22c5`.
Host records are `validation-logs/desktop-final2.log` and
`desktop-final2.exit` (zero). The raw receipts remain in Workshop `782b8b9c`,
under `work/desktop-final2/desktop-build/`; `work/desktop-final2/results.json`
contains the single required `desktop-build` pass.

The actual computer was `e511734d-f36f-4318-8c0c-db4b7ba836d6`, sandbox
`local-f9fe1856`. Response `006-mark_build_checkpoint.json` identifies the end
checkpoint and the changed `sdk-build-fixture.ini`, retaining one 36-byte file.
Response `007-stop_build_capture.json` records the exact changed value from
`hermes-build-before` to `hermes-build-after` at
`/groups/fixture/marker`, with complete values and no withheld files.
Response `008-close_build_computer.json` confirms `teardown: agentenv`.
Both the desktop helper and outer MCP server subsequently exited zero on stdin
EOF (0.115 and 0.117 seconds respectively).

The actual runtime archive SHA256 was
`2a9ffacca7ff13c5fb3398521226c383a09f88eca2cab02bf07a6248ae2ca638`.
All three returned screenshots decoded as 1280×800 RGB PNG images:

| Receipt | Bytes | SHA256 |
| --- | ---: | --- |
| Computer creation (`001-2.image`) | 9,702 | `879b81d7183456062a4543de0b7b0cb8fa8b3aac61f077b266985dc2aa058892` |
| App capture (`002-2.image`) | 25,876 | `c70414065f7eec4e00cc0184b5f6b19f9b9cc25362daa8633c15ce4c9648c280` |
| Post-typing wait (`005-2.image`) | 26,533 | `fe6c262a52b4d4ba487c76a6b904e349651db4a53f13ba60b516926dafe0ecf6` |

The earlier failed fixture remains retained. This successful rerun establishes
its formerly untested wait, end checkpoint, structured capture draft, and
complete local lifecycle. It does not claim execution against the subsequent
Frida-corrected SDK artifact, whose acceptance remains separate.

One diagnostic limitation is independently recorded in
`validation-logs/agentenv-direct-version.log`: two real `agent-env --version`
processes returned `agent-env 0.9.1485` with exit zero in 17.230 and 15.538
seconds during fixture installation. The pinned `Doctor.ts` host probe times
out after ten seconds, so its missing-version report under that load does not
establish a missing installation. The successful desktop lifecycle above is
operational evidence independent of that version probe. No diagnostic output
was fabricated or readiness gate bypassed.

The local X11 capture checks an actual window/process association, natural
application exit, verified cleanup, both retained INI byte hashes, and decoding
through `inspect-desktop-application-state`. A previous host-only fixture run
closed stdin too early and requested a stop before a window appeared; keeping
stdin open until application exit corrected that fixture behavior. That was a
fixture issue, not evidence of an engine defect.

Even a complete `desktop-build` pass establishes the listed local lifecycle and
state operations only. Exporting and replaying an environment bundle, external
model orchestration and authentication flows require their own acceptance.
