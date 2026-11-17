# Hermes REA operational tests

`sdkcraft test` packs the SDK and runs the Spread launch, provider variants and
persistence jobs. Provider variants use synthetic local inputs and assert actual
produced facts; they do not count tool registration or version banners as provider
functionality. Fixture-only compilers (`gcc`, `libc6-dev`, `mono-mcs`, `golang-go`) and the
fixture window manager (`openbox`) are installed in the test workshop. Android
fixtures use the packaged Apktool compiler and embedded aapt.

For diagnosis in an existing fresh Workshop, make `main/launch/*.py`, `main/launch/*.mjs`, and
`main/launch/static-fixtures.json` visible under `/project`, then run:

```sh
workshop exec -I </dev/null -- sudo -Hu rea bash -c 'cd /var/lib/hermes-rea/work && exec "$@"' -- python3 /project/functional.py \
  --output /var/lib/hermes-rea/work/sdk-validation
```

Use `--only javascript,archive,evidence` to run selected cases serially.
`--require browser` makes an unavailable browser prerequisite fail the command.
All actual operation failures fail the command regardless of `--require`.
`--rea`, `--node`, and `--package-root` can select an installation for development;
results outside a Workshop are not SDK installation evidence.

Each output directory contains `results.json`, individual raw MCP responses,
the complete advertised `tools-list.json`, initialization metadata, stderr and
CLI doctor/providers/capabilities JSON. The catalog check compares exact name sets
from the packaged upstream canonical contracts, `tools/list`, and every group in
`binary_session.tool_availability`. Catalog checks are interface checks only.
The forced-command check separately uses the unmodified default catalog, records
its advertised inventory versus the full session inventory, and exercises deferred
`discover_tools` registration when that control tool is present.

The `cli` case preserves doctor's actual exit code and findings, including
unconfigured external providers. A CLI-contract pass does not mean doctor found
every optional provider ready. `frida` tests actual device/process enumeration;
`frida-injection` spawns an owned native fixture and injects a script that reads
its exact exported memory and PID, then unloads, resumes and closes the session.
The fixture cleanup uses a PID file descriptor; no system ptrace setting changes.
`javascript` proves static Electron IPC analysis;
`runtime` independently proves Node Inspector observation and evidence correlation.
Commercial, remote, physical-device and macOS-only providers are not simulated.

`browser-scenario` drives a real local click and asserts changed accessibility
content. `web-runtime` inspects a registered listener and its source;
`web-export`, `web-source`, and `web-modules` verify captured bytes, source-map
mapping and native ES import resolution respectively. Browser fixtures first try
the sandbox. If the host refuses it, the fixture-only retry records the exact
failure and disabled mode; SDK defaults remain unchanged.

`ssh_boundary.py` exercises the installed forced-command executable as user
`rea`, including native MCP, rejected command syntax, and immutable bounded
artifact inputs. It does not claim SSH network or key-authentication coverage.
It also verifies that the worker cannot run a noninteractive root command with
sudo. `provider-no-fallback` deliberately supplies a missing Ghidra directory to
a separate MCP process, selects Ghidra explicitly, and requires both a clear
error and no active substitute analysis session. Full Hermes A plugin routing
and external A-to-C orchestration are outside these SDK-local tests.

The `electron-passive` and `electron-active` cases use a caller-owned Electron
45.3.3 target under Xvfb. `install_electron_fixture.py` verifies the pinned
official SHA256 and deletes the download after extracting it. The runtime is a
test artifact, not an SDK dependency. The default path is
`/var/lib/hermes-rea/work/electron-fixture/electron`; `REA_TEST_ELECTRON` can select
the same verified runtime elsewhere. Passive inspection asserts real file-page
DOM and renderer source; active capture clicks a button and checks that the
registered main-process IPC handler actually ran and provider cleanup completed.

For actual network SSH validation, first provision only a disposable C worker
with an ephemeral public key allowlist and pin its host public key. Run the host
helper with existing private-key and known-hosts paths:

```sh
python3 main/launch/ssh_transport.py --host WORKER_IP --port 22 \
  --key /private/dev-key --known-hosts /private/known_hosts --output /tmp/ssh-results
```

The helper ignores ambient SSH configuration and agent identities. It verifies
native MCP, transfers an owned ELF through `artifact-put`, asserts real remote
disassembly and matching hashes, and tests shell/forwarding refusals. `--ghidra`
also performs explicit remote Ghidra decompilation. The caller owns provisioning,
key generation and trust pinning; the helper never prints private-key material.

`cutter` launches the packaged Qt5 Cutter GUI under Xvfb with the unchanged
upstream bridge in a private data directory. It checks authenticated discovery,
the exact fixture symbol, actual instructions and observed document generation.
The test verifies input hashes locally and preserves upstream's partial document
identity limitation. The Qt6 asset rejected the upstream Python bridge during
development, so GUI startup alone was not accepted as compatibility evidence.

`full-source` verifies every preserved upstream/submodule blob against its
manifest and Git identity, runtime links and executable modes, then executes the
original upstream CLI on a real JavaScript fixture. `desktop-runtime-pack`
exercises the unchanged runtime packaging script as the unprivileged worker.
Each MCP process records its EOF/termination behavior in `mcp-shutdown.json`.

Evidence persistence is verified by exporting a real bundle, hashing it across
Workshop refresh, then importing and checking all saved Evidence identities in a
new MCP process. Ghidra's separate test saves and reopens a target-bound snapshot.

`desktop-capture` launches an owned X11 application under real Xvfb/Openbox,
checks EWMH window ownership, natural application exit and cleanup, then decodes
both retained INI state versions through the REA CLI. `desktop-dconf` compiles an
offline database and checks exact values through unchanged REA's database reader;
it does not access live user settings. `firmware-ext2` creates an owned filesystem
image without mounting it, launches REA with `/usr/bin:/bin` as its caller PATH,
and requires Unblob/debugfs to extract exact payload bytes. This catches missing
system sbin paths even when gzip extraction works.

`desktop-build` composes Canonical `docker-ce` before Hermes in its isolated
Spread fixture. It records actual desktop doctor diagnostics and requires the
upstream Docker-daemon and 20 GB free-space checks before any image pull. It uses
the real runtime archive, starts a local xterm computer without a model service,
captures an owned command, types a value through the computer driver, checks the
retained before/after INI values and screenshot bytes, and confirms teardown.
Capacity or daemon refusals are recorded unavailable; required cases fail
acceptance until exercised. It does not weaken upstream admission or host limits.

`environment-export` also starts unchanged `rea environment-serve` on an ephemeral
loopback port, initializes real HTTP MCP, compares the served catalog with the
exported manifest, invokes the fixture's read tool and checks exact captured JSON
and target-content provenance. It verifies state was served, graceful SIGTERM
exit143 and listener closure. This local HTTP server requires no external model,
Docker container or live capture-origin connection.
