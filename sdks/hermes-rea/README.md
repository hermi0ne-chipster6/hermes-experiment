# Hermes REA SDK for Workshop

The existing `hermes-rea` worker SDK packages the upstream REA CLI and MCP
engine plus Linux analysis dependencies for **Ubuntu 26.04 amd64**. REA is
built without source patches from
[`51459cf203ae1eb6b586a95b21899eaa0f631823`](https://github.com/morluto/rea/commit/51459cf203ae1eb6b586a95b21899eaa0f631823)
(version 6.9.0). This source baseline includes changes beyond the npm 6.9.0
release; the version string alone does not identify the packaged code.

The complete upstream repository and all five pinned submodules are included at
`/var/lib/workshop/sdk/hermes-rea/upstream/rea`, alongside the built runtime.
`upstream/rea.manifest.json` records all 14,149 original files and symlinks;
the adjacent source archive retains the same tree. The original development
scripts are preserved. Running their build/test workflows requires a writable
copy and the locked development dependencies from the upstream package lock.

Store revision 2 publishes REA 6.9.0 to `latest/edge`. The
[edge release notes](docs/edge-release-notes.md) record the artifact checksum,
installed validation results, and limits for this release.

## Full engine reference workshop

```yaml
name: rea
base: ubuntu@26.04
sdks:
  - name: docker-ce
  - name: try-hermes-rea
```

This composes Canonical’s local Docker engine with the artifact built using
`sdkcraft try`, including the execution prerequisite for desktop build computers. Published revision
1 on `hermes-rea/latest/edge` contains the older 6.7.0 implementation. These
development changes have not been published.

For desktop build computers, use
[`examples/full-engine.workshop.yaml`](examples/full-engine.workshop.yaml): it
lists Canonical's `docker-ce` SDK **before** `try-hermes-rea`. Docker CE supplies
an owned daemon inside the same Workshop; Hermes-REA supplies the pinned clients
and adds `rea` to the Docker group when that group exists. Register the built
artifact and launch from an ordinary development account:

```sh
cd ~/integration
sdkcraft try /absolute/path/to/built-hermes-rea.sdk
# Save examples/full-engine.workshop.yaml here as workshop.yaml.
workshop launch
workshop exec -I -- docker version </dev/null
workshop exec -I -- rea doctor --provider desktop_build --json </dev/null
```

On this VPS, the dedicated account is `rea-sdk-dev`. Root-launched Workshop
hit an LXCFS mount-helper/user-mapping failure; the ordinary-user launch worked
with standard Workshop configuration. Canonical Docker SDK revision 13 reports
metadata version 29.5.1; its apt hook installed Engine 29.10.0 on 2026-11-17.
Both that client's and Hermes-REA's pinned Docker 29.1.3 client's real
`hello-world` execution passed. This establishes local container execution;
the [validation report](docs/validation.md) separately records desktop workflows.

REA's local AgentEnv adapter expects local published ports and paths, so a
generic remote `DOCKER_HOST` is not a drop-in replacement. Request-based desktop
builds also need the runtime archive produced by upstream `rea setup
--desktop-build` and sufficient image storage (doctor checks 20 GB free).
Only solver runs require model configuration. Docker group membership grants
the REA worker authority over its Workshop's daemon; the restricted SSH command
does not narrow that authority. No host Docker socket is shared by this example.

## Using the SDK

The local `rea` and `rea-agents` launchers preserve upstream arguments, current
directory, and caller-selected provider settings. They do not require an SSH key.

```sh
workshop exec -- rea doctor --json
workshop exec -- rea providers --json
workshop exec -- rea capabilities --json
workshop exec -- rea mcp
```

Local CLI work uses the invoking user's home and current directory. To use the
worker's persistent files, run as `rea` from its mounted work directory:

```sh
workshop exec -- sudo -Hu rea bash -lc \
  'cd /var/lib/hermes-rea/work && rea analyze /var/lib/hermes-rea/inbox/sample --provider ghidra --json'
```

Use upstream snapshot/export commands to retain session evidence. Active MCP
sessions are process-local and are not resurrected by Workshop refresh. The
`state` mount retains worker files, caches, and exported evidence.

### Restricted SSH transport

`hermes-rea-stdio` retains the fixed MCP launcher and bounded artifact-upload
protocol. Remote callers cannot select arbitrary CLI commands through it.
Supply a public `rea_authorized_keys` allowlist through the read-only
configuration mount and pin the worker's SSH host key at the client. Private
keys stay outside the worker. Without an allowlist, local CLI/MCP remain usable
but remote SSH access is not authorized. See the existing
[activation checklist](../../deployment/activation-checklist.md) and the
[MCP/session validation runbook](docs/mcp-session-validation.md).

### Included dependencies and external requirements

The build pins Node 24.22.1, Ghidra 12.1.4, Frida 17.25.1, JADX headless MCP
0.7.1, Apktool 3.0.3, WABT 1.0.42, Wakaru 1.14.0, Rizin 0.9.1, Kuna 1.990,
Binwalk 3.1.0, Unblob 26.6.4, mitmproxy 12.2.3, Chrome for Testing
156.0.8078.4, pwndbg 2026.09.15, Sasquatch, Cutter 2.5.0 Qt5, native ILSpy
11.2.0.10050, and the pinned Ghidra NativeAOT extension. An isolated pwntools
4.15.0 environment supplies REA's exact pyelftools 0.33/Unicorn 2.1.2 profile.
Desktop clients include AgentEnv 0.9.1485, Docker CLI 29.1.3, Buildx 0.30.1,
and Compose 2.40.3. The runtime hook installs the supported base's JDK, GDB,
binutils, ADB, TShark, sigrok, graphics libraries, and extraction utilities. See
[dependency pins and build notes](dependencies/README.md). The matched Frida JavaScript/native package is an explicit compatibility override of upstream’s 17.23.2 pin, fixing its reproduced SIGCHLD subprocess failure. The original REA source and lock remain unchanged; see [compatibility evidence](docs/frida-compatibility.md).

Browser operations take an explicit executable path in their input. Native
provider selection remains upstream's caller-visible choice. Managed .NET
metadata/CIL inspection is built in and requires no .NET runtime; optional
ILSpy reconstruction input remains inference.

Cutter and its unchanged REA bridge are packaged. Start it with an owned target
and a display (for headless operation, `xvfb-run -a cutter -A 0 /path/to/target`),
then use REA's Cutter session interface. See [Cutter validation](docs/cutter-validation.md).
Hopper, IDA and JEB require caller-provided installations and applicable licenses.
Live Android operations need a connected device or emulator. Desktop build
computers use the same-Workshop Docker composition above and a REA runtime
archive; solver workflows also need model configuration. macOS native UI/LLDB workflows and Windows-only
execution helpers cannot run on this Linux host. The matrix records the
complete boundary.

## Plugs (resources this SDK consumes)

| Plug | Interface and target | Connection |
| --- | --- | --- |
| `state` | mount, `/var/lib/hermes-rea` | automatic system mount |
| `configuration` | read-only mount, `/etc/hermes-experiment` | automatic system mount; operator supplies public-key allowlist |

## Slots (resources this SDK provides)

None. Restricted SSH uses the private LXD bridge.

## Build, test, and review

Use `sdkcraft pack`, `sdkcraft try`, and `sdkcraft test` from this directory.
Tests use real CLI/MCP operations and synthetic inputs. Read saved per-case
results and limitations before claiming a capability is functional. See the
[implementation plan](docs/implementation-plan.md) and
[capability matrix](docs/capability-matrix.md), plus the
[review and release procedure](docs/release-review.md). Publishing and remote Git pushes
require the operator's explicit approval.

## License and copyright

REA is MIT licensed. Provider binaries, Java/Python/Node dependencies, native
libraries, and system packages retain their upstream licenses and notices.
Provider license files are retained in the SDK; Ubuntu supplies package notices
under `/usr/share/doc`. Review the packed inventory and license expression
before a release.
