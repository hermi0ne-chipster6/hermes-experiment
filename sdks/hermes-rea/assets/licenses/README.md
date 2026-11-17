# Retained provider notices

These are unmodified notice files from the exact source revisions corresponding
to the packaged releases. `PROVENANCE.json` records the source URL, release tag,
resolved commit, installed SDK path, and SHA-256 for every copied source file.
The SDK's `assets` part installs this directory as `$SDK/licenses`.

| Provider | Retained files and original archive contents |
| --- | --- |
| Wakaru 1.14.0 | `wakaru/LICENSE` from release source. The release archive contains only the executable. This release's actual license text is Apache 2.0. |
| WABT 1.0.42 | `wabt/LICENSE` from release source; the Linux binary archive contains no standalone license/notice filename. |
| Rizin 0.9.1 | `rizin/COPYING` and `rizin/COPYING.LESSER` from release source. The static Linux archive contains no standalone license/notice filename. These are GPL v3 and LGPL v3 texts; they do not replace individual source-file attribution or bundled dependency notices. |
| Kuna 1.990 | `kuna/LICENSE` and `kuna/NOTICE` from release source; also retained in `$SDK/providers/kuna/LICENSE` and `NOTICE` from the release archive. NOTICE includes Ghidra, angr, and deark attribution. |
| mitmproxy 12.2.3 | `mitmproxy/LICENSE` from release source. The native archive contains three executables and no standalone notice file. Its embedded Python dependency closure retains the upstream executable's contents. |
| JADX headless MCP 0.7.1 | `jadx-headless-mcp/LICENSE` from release source. `$SDK/providers/jadx.jar` additionally retains its embedded `LICENSE`, `META-INF/LICENSE`, and `META-INF/LICENSE.txt` entries, including duplicate ZIP member names. |
| Apktool 3.0.3 | `apktool/LICENSE.md` from release source. `$SDK/providers/apktool.jar` retains `LICENSE`, `META-INF/LICENSE`, `META-INF/LICENSE.txt`, and `META-INF/NOTICE.txt`. |
| ILSpy 11.2.0.10050 | `ilspy/LICENSE`, `ilspy/doc/copyright.txt`, `ilspy/doc/third-party-notices.txt`, and `ilspy/ICSharpCode.Decompiler/Humanizer/LICENSE`, pinned to the source commit recorded in the native NuGet package. The NuGet metadata and signed package contents remain in `providers/ilspy`. |
| Unicorn 2.1.2 | `unicorn/src/AUTHORS.TXT` and `unicorn/src/qemu/{COPYING,COPYING.LIB,LICENSE}` copied from the checksum-pinned sdist used to build the private pwntools environment. Wheel-installed package metadata remains intact. |
| Chrome for Testing 156.0.8078.4 | `chrome-for-testing/ABOUT` is copied byte-for-byte from the archive; the runtime also retains `providers/chromium/chrome-linux64/ABOUT`. It identifies Google Chrome and directs users to `chrome://credits` and `chrome://terms`. This is a Google Chrome distribution, not a plain Chromium source build; no blanket BSD license is inferred for the archive. |

Other package locations retained by the build include Node's `node/LICENSE`,
Ghidra's root `LICENSE` and `licenses/` directory, upstream npm package notice
files under `rea/node_modules`, NativeAOT's notice embedded in its generated
JAR, Binwalk and Rust dependency notices under `providers/licenses/binwalk`,
Sasquatch's package documentation under `providers/licenses`, Unblob wheel
metadata and license directories under `providers/unblob`, and pwndbg wheel
metadata plus `providers/licenses/pwndbg`.

The AgentEnv private environment retains upstream wheel metadata and license
directories under `providers/agentenv-venv/lib/python3.14/site-packages`, including
`agentenv_framework-0.9.1485.dist-info/licenses/{LICENSE,NOTICE,THIRD_PARTY_NOTICES.md}`.
Its complete hashed dependency list is retained as
`providers/licenses/agentenv/requirements.txt`. The extracted Ubuntu Docker CLI,
Buildx and Compose clients retain each exact binary package's documentation,
copyright and notices under `providers/licenses/docker-client`,
`providers/licenses/docker-buildx`, and `providers/licenses/docker-compose`.
Their immutable package URLs and SHA-256 values are in `dependencies/assets.json`.

The browser part excludes the upstream `WidevineCdm` directory. Its own license
identifies that CDM as non-open-source software requiring a separate Google
agreement. REA's browser inspection does not require DRM playback.

This inventory records retained upstream material. It is not an assertion that
one top-level license describes every compiled dependency. Downloaded binary
assets remain unchanged except for separately documented packaging exclusions.
