# Frida provider compatibility override

Status: the controlled before/after regression and mixed REA session passed with official Frida 17.25.1. The primary source recipe now declares the complete matched npm/native override in `dependencies/frida-compatibility.json`. Rebuilt-artifact acceptance and clean reinstall remain pending; scratch runtime proof is not artifact proof.

REA remains version 6.9.0 at commit `51459cf203ae1eb6b586a95b21899eaa0f631823`. Its unchanged `package.json` has optional dependency `frida: 17.23.2` and an `allowScripts` entry for that version; its original `package-lock.json` pins the same npm distribution. Retain those files and the complete original source tree as historical engine inputs. Frida 17.25.1 is identified separately as an **SDK provider override**, not represented as the engine's original dependency.

## Reason for investigation

The official Node binding issue describes Linux Frida spawn/kill removing the host's SIGCHLD handler, leaving Node child processes unreaped and without exit events. Its reported environment used Frida 17.24.3, so it is a relevant mechanism, not itself proof about this SDK's 17.23.2 runtime. [Frida Node issue 121](https://github.com/frida/frida-node/issues/121).

Frida 17.25.0 documents changes to daemon spawning and GLib pidfd handling intended to preserve Node child reaping. It also changes native Linux injection substantially, so a minor-version increase alone does not establish runtime compatibility. [Official 17.25.0 release](https://frida.re/news/2026/10/30/frida-17-25-0-released/).

The 17.25.1 release adds a Linux regression test for preserving SIGCHLD and follows up on mapper behavior, including library-base selection and Android linker visibility, plus Windows fixes. This is why the proposed candidate includes the follow-up rather than stopping at 17.25.0. [Official 17.25.1 release, November 1, 2026](https://frida.re/news/2026/11/01/frida-17-25-1-released/).

## Exact package inputs

| Input | URL | Bytes | SHA256 |
| --- | --- | ---: | --- |
| Engine-pinned npm package | [frida-17.23.2.tgz](https://registry.npmjs.org/frida/-/frida-17.23.2.tgz) | 1,059,441 | `a28736d6d34d7984583951ad4310d9bacd6bd21ebcda86eb2a977e6a95cbbd55` |
| SDK override npm package | [frida-17.25.1.tgz](https://registry.npmjs.org/frida/-/frida-17.25.1.tgz) | 1,232,593 | `81c475d3425a3748007efdc80ebd2c747a44694627e2aab11999675536f9ec04` |
| SDK override native addon archive | [frida-v17.25.1-napi-v8-linux-x64.tar.gz](https://github.com/frida/frida/releases/download/17.25.1/frida-v17.25.1-napi-v8-linux-x64.tar.gz) | 52,530,484 | `28f6bf3a8926288ffe79f415777256a37213c2d217cdab4ee81b225b096854bb` |

Both npm archives were downloaded into memory on 2026-11-17, SHA256/SHA512 were computed, and SHA512 was checked against the exact-version registry metadata. Candidate SRI:

```text
sha512-Lh0+ymWrhBa9/6g8rJmmEtmmWij13wi1wdHzi4nTkx7fRyZFKYylLY8gXIVae+SFZsMuSaoK5K/Vm3gfVKpTCg==
```

Baseline SRI:

```text
sha512-gRCmmTUFdEILyHRN1b66erRoXafwsfWTqXyoBBqkSCFX0Ue7Jhvs/KhA3JO0XrgITNlPd91QAGsFvWzh0mhVgg==
```

The primary owner downloaded both candidate payloads and verified their bytes and SHA256 values; `validation-logs/frida-fixed-downloads.json` records the actual files. The extracted native binding SHA256 is `ac4e786dcadb35f1717bc44ab1ec92ee439a3f606bcc016fdeb9bd1cbc4aa665`. The release asset metadata independently agrees with the native archive size/hash. [Official release API](https://api.github.com/repos/frida/frida/releases/tags/17.25.1). Exact npm metadata: [17.23.2](https://registry.npmjs.org/frida/17.23.2), [17.25.1](https://registry.npmjs.org/frida/17.25.1).

## JavaScript and dependency comparison

The complete `package.json` objects differ only in `version`. All three published `build/src` JavaScript/declaration files are byte-identical: `frida.js`, `frida.d.ts`, and `frida_binding.d.ts`; their SHA256 values are recorded in the JSON proposal. No runtime JS/declaration file was added or removed. This comparison does not claim that native code, bundled source, or build tooling is identical.

Direct runtime dependencies are unchanged: `bindings ^1.5.0`, `minimatch ^10.0.1`, and `prebuild-install ^7.1.3`. The engine's existing lock resolves these to 1.5.0, 10.2.5, and 7.1.3 respectively. There are no declared optional or peer dependencies in either Frida package. All eight development dependency declarations are also identical and recorded in the proposal; they need not be installed in the SDK runtime.

Both packages declare Node `>=16`, ESM, `build/src/frida.js` as the entry point/export, Node-API version 8, and the same install script `node scripts/install.js`. Both declare license `LGPL-2.0 WITH WxWindows-exception-3.1`. Preserve applicable notices and the native distribution's source/license provenance when packaging the override; this metadata comparison is not a license audit of every linked component. [Candidate package metadata](https://registry.npmjs.org/frida/17.25.1).

The unchanged JS/type surface and dependency ranges support testing the candidate against the packaged Node runtime. They do not establish successful native loading, instrumentation, signal behavior, teardown, or compatibility with every Frida target.

## Observed failure and controlled correction

The freshly installed policy/HOME-corrected SDK has SHA256 `c7373502e97f32c34be99ba7fd92e7ea5832caf31121aa79a747badd27cf22c5` and retains upstream Frida 17.23.2. Its initial 99-case run passed 17 cases, including real Frida injection, before the SQLite request timed out after 180 seconds with an unreaped `ps` child. The remaining 81 cases were aborted, not independently observed provider failures. EOF and TERM did not complete MCP shutdown; the owned harness used its bounded final kill. A fresh MCP process subsequently passed SQLite. Raw interruption and classification records remain in `validation-logs/frida-sequencing-interruption.json` and `final-initial-run-classification.json`.

The direct diagnostic uses the same Node 24.22.1 runtime, a harmless owned fixture and a long-lived Node child sentinel. It checks ordinary `ps` and Node child exit events before/after Frida import, spawn, attach, script load/unload, resume/detach and target exit. The sentinel prevents a fresh libuv watcher from masking the failure. The `/proc` signal mask records a caught SIGCHLD bit before Frida and after the corrected target lifecycle; a caught bit alone does not identify which handler owns it.

| Run | Actual result | Evidence under `/root/dev/rea-sdk/validation-logs/` |
| --- | --- | --- |
| Installed Frida 17.23.2 direct lifecycle | 37 records, 15 failed; child completion first fails after Frida spawn and zombie children remain; exit 1 | `frida-direct-baseline.log`, `.exit` |
| Matched official 17.25.1 scratch lifecycle | 37 records, all passed; child exit delivery and owned sentinel cleanup verified; exit 0 | `frida-direct-fixed.log`, `frida-fixed-probe.exit` |
| Same MCP process using scratch override | Five cases passed in sequence: JavaScript, Frida discovery, actual injection, SQLite exact row, Ghidra decompilation and snapshot reopen; exit 0 | `frida-mixed-fixed.log`, `.exit` |

The scratch runtime verifies 3,550 REA engine files unchanged and replaces the complete Frida package and its native binding together. The original installed SDK is not rewritten. These results reproduce the Linux SIGCHLD mechanism locally and qualify the official candidate for this tested process sequence; they do not establish arbitrary target/device compatibility.

## Remaining acceptance gates

The full source recipe preserves the original REA package and lock, removes the deployed original Frida module, then stages the verified complete 17.25.1 npm package and matching Node-API 8 Linux x64 addon. Its unchanged runtime dependencies remain resolved by the original lock. The override disclosure must travel with the deployed module; replacing only a native binary under 17.23.2 metadata is not acceptable.

Build and inspect the resulting SDK, verify its installed package/native hashes, then rerun the full supported-provider suite in one MCP session and perform a separate clean reinstall. The durable `frida-process-lifecycle` case must pass in that installed artifact. Keep the original failing evidence. No final artifact or release acceptance is implied by the scratch results.
