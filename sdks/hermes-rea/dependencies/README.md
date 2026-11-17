# Provider dependency pins

These dependency selections were checked against REA source commit
`51459cf203ae1eb6b586a95b21899eaa0f631823` on 2026-11-17. Their presence or
version probes do not establish REA functional coverage; see the capability
matrix and integration results.

## Complete upstream repository

The `upstream-source` part retains every tracked file from the pinned REA
commit, including documentation, tests, inert fixtures, scripts, hidden
configuration, the full package lock, and all five exact Git submodules at
`$SDK/upstream/rea`. `preserve-upstream-source.py` reads Git blobs directly:
checkout line-ending filters and `export-ignore` attributes do not omit or
modify files. No `.git` histories, remotes/configuration, or credentials enter
the SDK. The adjacent `upstream/rea.manifest.json` records each file's path,
mode, Git object ID, size, SHA-256, and owning repository's commit.

Some Unblob fixtures intentionally contain malformed symlink targets. Craft's
staging collision scan follows those links and fails with `ENAMETOOLONG`.
The build therefore stages the complete deterministic `upstream/rea.source.tar.gz`
and its checksum, then uses the official `override-prime` hook to extract the
unchanged tree directly into the final SDK. The archive remains available beside
the tree. No fixture is removed, dereferenced, or rewritten.

Relative `dist`, `node_modules`, and `skills` links reuse the built runtime and
its production dependencies. The original source CLI can use those outputs.
The source export is separate from the production package: upstream packaging
scripts distinguish a checkout containing `src/` from an installed package.
Development build/test/release workflows additionally need a writable checkout,
their locked development dependencies and, where their scripts inspect Git,
repository metadata; these are not implicit runtime dependencies. The installed
`full-source` test verifies file hashes/modes, submodule revisions, links, and
the original CLI's real JavaScript analysis.

## Retained notices

[`assets/licenses/README.md`](../assets/licenses/README.md) inventories packaged
notice locations. [`PROVENANCE.json`](../assets/licenses/PROVENANCE.json) records
resolved release commits and SHA-256 values for copied upstream notice files;
`assets.json` links each binary provider to its retained notice paths. Wakaru
1.14.0's exact source license is Apache 2.0. WABT, Rizin, and mitmproxy binary
archives also omit standalone notices, so corresponding release-source files
are supplied alongside the binaries. Kuna's archive notices and JAR-embedded
JADX/Apktool notices remain intact. Chrome for Testing identifies itself as
Google Chrome in `ABOUT` and supplies its credits/terms through the browser;
its entire distribution is not described as BSD-licensed Chromium.

## Firmware packaging

Binwalk 3.1.0 is built from upstream's unmodified source and Cargo.lock.
`build-binwalk.sh` requires Ubuntu build packages `cargo`, `rustc`,
`pkg-config`, `liblzma-dev`, and `libbz2-dev`. The pinned source is
`https://codeload.github.com/ReFirmLabs/binwalk/tar.gz/4fdab3d464d97b68e0af9088df3f9e2e1545b21c`,
SHA-256 `81d9dbfbe4716446fe5167ed7046ebc3a6c33a18cc91f412a5392374c3622e20`.
The helper installs only `providers/bin/binwalk`. Runtime needs liblzma5 and
libbz2-1.0. REA accepts 3.1.x; Ubuntu 26.04's Binwalk 2.4.3 is incompatible.

`build-unblob.sh` installs Unblob 26.6.4 and its complete hashed wheel closure
into `providers/unblob` at SDK build time. This lock is intentionally specific
to CPython 3.14 and Linux amd64, matching ubuntu@26.04. Build requirements are
`python3`, `python3-pip`, and `libmagic1t64`. No wheel downloads occur at
Workshop initialization. Runtime invocation is:

```sh
PYTHONPATH="$SDK/providers/unblob" /usr/bin/python3 -m unblob.cli "$@"
```

There is no `unblob.__main__`; `python3 -m unblob` is invalid. The exact helper
was exercised against a separate target directory and returned `26.6.4`.
This is installation evidence, not a firmware extraction test. Avoid adding
the dependency directory to global Python paths; only its launcher needs it.

Both firmware adapters require `procps` and util-linux `prlimit`. Unblob's
Landlock sandbox must remain enabled. Kernel/container refusal is a platform
limitation to report, not a reason to bypass the sandbox.

Ubuntu extractor packages available on this base are `7zip`,
`android-sdk-libsparse-utils`, `e2fsprogs`, `erofs-utils`, `squashfs-tools`,
`unzip`, `xz-utils`, `zstd`, `lz4`, `cpio`, `lzip`, `lziprecover`, `lzop`,
`unar`, `partclone`, and `upx-ucl`. `p7zip-full`, `sasquatch`, and `jefferson`
have no apt candidate. Jefferson is included in the Python lock. `7zip`
provides `7zz`; check whether an explicit `7z` compatibility symlink is needed
by a selected extractor.

For vendor-specific SquashFS, upstream Unblob uses the ONEKEY Sasquatch build:
`https://github.com/onekey-sec/sasquatch/releases/download/sasquatch-v4.5.1-6/sasquatch_1.0_amd64.deb`,
SHA-256 `efbc92bd27594e01211e1b582f105a463a0017360a0746a93de3f283906ade95`.
It contains `usr/bin/sasquatch`, `usr/bin/sasquatch-v4be`, and license notices.
It can be unpacked into an SDK part without installing a foreign apt package.
Its runtime dependencies are libc6, libgcc-s1, liblz4-1, liblzma5, liblzo2-2,
libstdc++6, libzstd1, and zlib1g.

Unblob's upstream install-deps also uses modified ONEKEY e2fsprogs builds.
Stock Ubuntu debugfs may support representative ext extraction but does not
establish parity with every modified extractor feature; test and document the
actual boundary. Do not overwrite Ubuntu's e2fsprogs with a foreign package.

## Browser

REA's locked playwright-core 1.64.1 selects Chromium revision 1248 / Chrome
for Testing 156.0.8078.4. The matching immutable version URL is
`https://cdn.playwright.dev/builds/cft/156.0.8078.4/linux64/chrome-linux64.zip`,
with locally verified SHA-256
`43fd31766c7533a02dda2ded5ad50c2f861cd5400be7509c0abad71129f79d79`.
Select its executable through the operation's `browser.executable_path`;
there is no general REA browser-executable environment override. Ubuntu's
`chromium-browser` package is a snap transition, not a self-contained browser.

The Playwright dependency table lists `libasound2t64`,
`libatk-bridge2.0-0t64`, `libatk1.0-0t64`, `libatspi2.0-0t64`, `libcairo2`,
`libcups2t64`, `libdbus-1-3`, `libdrm2`, `libgbm1`, `libglib2.0-0t64`,
`libnspr4`, `libnss3`, `libpango-1.0-0`, `libx11-6`, `libxcb1`,
`libxcomposite1`, `libxdamage1`, `libxext6`, `libxfixes3`, `libxkbcommon0`,
and `libxrandr2`; add fonts-liberation and fonts-noto-color-emoji. Headed
synthetic tests can use xvfb. A test must establish the browser's actual
sandbox behavior inside Workshop; a successful download is insufficient.

## Other providers

The companion JSON records immutable URLs and checksums. JADX is the
headless-MCP JAR that REA's bridge expects, not a generic jadx CLI. WABT needs
`wasm-validate`, `wasm-objdump`, and `wasm2wat`; the fixture compiler is
`wat2wasm`. Ubuntu 26.04's WABT 1.0.36 is too old. Wakaru needs the actual
native executable, not its npm shim. Rizin's static amd64 release is suitable
for the Linux CLI adapter; this does not provide an attached Cutter GUI.
TShark 4.6.4 and sigrok-cli 0.7.2/libsigrokdecode4 are available from Ubuntu.

Managed .NET inspection is implemented in REA's TypeScript parser; production
metadata/CIL analysis does not need .NET or ILSpy. The SDK additionally bundles
the official `ilspycmd.linux-x64` 11.2.0.10050 NativeAOT NuGet package, which
requires no separate .NET runtime. Its executable is on the provider PATH and
selected by `REA_ILSPY_CMD_PATH`; `libicu78` supports globalization. Optional
C# output can be imported as reconstruction inference and is not canonical
evidence. REA's production parser does not automatically invoke ILSpy: the
explicit external-tool workflow and upstream managed verification oracle use
it. `ilspy-reconstruction` compiles an owned C# fixture, decompiles it with the
real tool, imports the output against retained member Evidence, and asserts
that REA labels it inference rather than canonical observation.
NativeAOT's specialized Ghidra extension is a separate provider dependency.

Kuna 1.990 is an Apache-2.0 standalone Linux executable with SLEIGH specs
embedded. It does not require a separate spec download. Select it with
`REA_KUNA_COMMAND`. Both the downloaded archive digest and `kuna --version`
were checked on this host; REA's source baseline was previously verified on
macOS arm64, so Linux analysis still requires the integration test.

The mitmproxy 12.2.3 native archive includes its Python runtime. REA requires
this native profile, selected with `REA_MITMDUMP_COMMAND`, for offline native
capture decoding. The official archive SHA-256 matches REA's documented pin;
`mitmdump --version` reported 12.2.3 binary / Python 3.14.0 on this host. This
does not establish a capture decode pass.

NativeAOT can be built without changing upstream: initialize REA's pinned
`third_party/ghidra-nativeaot` submodule at
`effeb734fc570c32650f88b159608979dc7b423e`, set `GHIDRA_INSTALL_DIR` to the
staged Ghidra 12.1.4 root and `REA_NATIVEAOT_BUILD_ROOT` to the part's install
directory, then run `node scripts/build-ghidra-nativeaot.mjs` with JDK 25.
The script verifies the source revision and embeds the extension's license.
Select the resulting JAR through `REA_GHIDRA_NATIVEAOT_JAR`.

`build-pwndbg.sh` consumes the unchanged pwndbg Git source at
`55596aa676a2756efb8d67034f31675170eabe48` (2026.09.15), installs build-only
uv 0.12.0 by wheel hash, and syncs upstream's frozen `uv.lock` into a private
relocatable environment. Build packages are python3-venv, python3-pip,
python3-dev, build-essential, and git. The lock successfully installed on this
host's CPython 3.14. Its full dependency closure is approximately 644 MiB
uncompressed, including upstream optional command dependencies. The SDK does
not prune or modify upstream's dependency declaration.

The complete build helper passed, then its installed tree was moved to a new
path. The relocated interpreter found the pinned package, and host GDB loaded
the relocated `gdbinit.py`, reported 2026.09.15, and evaluated
`pwndbg.aglib.vmmap.get()` without a target. This proves installation,
relocation, and GDB imports; a core-context operation remains a separate test.

Select `REA_PWNDBG_GDBINIT=$SDK/providers/pwndbg-venv/share/pwndbg/gdbinit.py`
and `REA_PWNDBG_VENV_PATH=$SDK/providers/pwndbg-venv`. GDB must embed the same
Python ABI. REA's adapter sets `PWNDBG_NO_AUTOUPDATE=1` and uses only its
core-context path; no user GDB configuration is required. A successful lock
install is not a core-file analysis test.

## Exact offline ELF and recorded-core profile

REA hard-checks `pwntools==4.15.0`, `pyelftools==0.33`, and `unicorn==2.1.2`.
Ubuntu 26.04 supplies pyelftools 0.32 and Unicorn 2.1.4, so its Python packages
cannot satisfy this provider profile. `build-pwntools.sh` installs the complete
hashed dependency closure into `providers/pwntools-venv`, selected through
`REA_PWNTOOLS_PYTHON`. Python isolated mode still uses this private environment;
no system Python package is replaced.

Unicorn 2.1.2 has no CPython 3.14 wheel. The helper compiles its unchanged,
SHA-256-pinned source distribution using the base's CMake/compiler and a
separately hashed Python build-backend closure, including versioningit. It
retains wheel notices and makes generated console launchers relocatable.
The build probe checks all three versions and actually emulates an x86-64
instruction that sets RAX to 42. Independent SDK tests inspect a real ELF and
an owned GDB-recorded core; pwndbg enrichment remains a separate operation.

The environment wrapper must set absolute `REA_SIGROK_COMMAND=/usr/bin/sigrok-cli`:
the signal provider does not search PATH. TShark and capinfos do support PATH
discovery. The standard doctor probes Ghidra, IDA, JADX, Kuna, Hopper and an
explicit ILSpy path; it does not replace these auxiliary-provider checks.

## Desktop build clients and external prerequisites

The private `providers/agentenv-venv` installs upstream's exact desktop-build
client profile, agentenv-framework 0.9.1485 and protocol 0.1.500 with its
`computer` extra. `agentenv-requirements.txt` pins all 105 dependency wheels
with hashes for CPython 3.14/Linux amd64. `REA_AGENT_ENV_COMMAND` selects its
relocatable console script; sibling `python3` lets REA locate the interpreter
for `bridge/agentenv/computer.py`.

The SDK extracts only Docker's CLI from Ubuntu's checksum-pinned docker.io
29.1.3 package. It also supplies Buildx 0.30.1 and Compose 2.40.3: AgentEnv's
preflight checks both plugins for image builds and local multi-container
environments. Ubuntu's plugin packages are explicitly supported by AgentEnv.
Workshop setup links them into `/usr/local/lib/docker/cli-plugins` without
rewriting a caller's Docker configuration. Package copyright/NOTICE files are
retained under `providers/licenses/docker-*`.

Hermes-REA itself does not install a Docker daemon. The official full-engine
Workshop composition lists Canonical's `docker-ce` SDK first, providing an owned
local daemon in the same Workshop; Hermes-REA then adds its worker to the
existing Docker group. No host administrative socket, cloud credentials, or
model configuration is imported. REA's local AgentEnv adapter uses loopback
published ports and local paths, so an arbitrary remote `DOCKER_HOST` is not
sufficient. The caller still needs the documented storage capacity and REA
runtime archive; solver workflows additionally require a model endpoint.
Client imports/version checks establish installation only. Independent local
Docker execution passed with the bundled 29.1.3 client and the official SDK's
actual Engine 29.10.0; this does not establish desktop deployment or solver runs.
AgentEnv's local state/cache use `~/.local/state/agentenv` and
`~/.cache/agentenv`; sandbox bookkeeping also uses `~/.agent-env-sandboxes`.

Asset checksums were checked against downloaded bytes and, where available,
GitHub release digests. They establish repeatability, not a functional test
of each provider. apt package versions deliberately follow the supported base
repository for security updates; record `dpkg-query` output with each validation.
