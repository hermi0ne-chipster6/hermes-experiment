# Built-in firmware and game-container validation

Fourteen independent MCP cases exercise the readers at upstream commit
`51459cf203ae1eb6b586a95b21899eaa0f631823` (REA 6.9.0). These are inert synthetic
format fixtures, not firmware intended for flashing, executable game ROMs or
payloads to run. No device, emulator, external decompiler or model service is
used. No packaging or upstream engine code is changed by these tests.

## Fixture provenance and regeneration

`tests/main/launch/firmware-format-fixtures.json` contains fourteen base64
fixtures, their byte counts and SHA256 values, independent expected extracted
member hashes/counts, the original upstream MIT license, and hashes of all
18 source files used by the factory loader. The member oracles come from the
bytes explicitly supplied to upstream fixture writers or their documented
source-owned constant patterns, not from a reader under test.

Regenerate with Node 24.22.1 and the exact upstream checkout:

```sh
node tests/main/launch/regenerate-firmware-format-fixtures.mjs \
  /path/to/upstream-rea /path/to/built/rea/node_modules/rea-agents
```

The generator refuses a different Git HEAD and compares every loaded source,
lockfile and license byte-for-byte with that commit, rejecting local edits.
It transforms the actual upstream
TypeScript fixture modules and their source dependencies using Node's built-in
TypeScript API. The supplied runtime root resolves the protobuf wire writer;
its package version must equal `@bufbuild/protobuf` 2.16.0 in the exact upstream
lock. The manifest records Node version, lock SHA256 and wire-module SHA256.
The generator does not import production artifact readers to produce expected
results. Generated fixtures total 130,065 bytes before base64 encoding.

Two successive generations produced identical manifest SHA256
`2b70d9f993424fca0622fcc3dbe728bc9a49f6c2bebfd72915fea9a08975396d`.
`validation-logs/agent-c-firmware-reproducibility2.log` and its zero exit record
retain this check and Python helper syntax validation. An earlier generator
metadata check stopped at protobuf's nested CommonJS package marker; it was
corrected to find the actual named package without changing any dependency.
The earlier nonzero result is retained.

## Operational assertions

The pinned interface is `open_binary` → `inspect_artifact` → `extract_artifact`
→ `close_binary`. There are no invented `open_artifact` or `list_artifact`
commands. Inspection returns an orchestration Evidence envelope; the helper
requires its completed `inventory_artifact` substep and matching nested
Evidence identity before examining the graph.

Each `format-<name>` case requires the exact root format and input digest, no
integrity contradictions, verified member hashes in content-addressed graph
nodes, and exact canonical occurrence IDs. Extraction selects those observed
regular members into an absent case-owned directory. The helper verifies the
returned manifest, selected IDs, containment/cleanup flags, exact output member
set, byte counts and SHA256 values both in the response and on disk. It checks
that the input digest is unchanged and closes the active target in `finally`.
Full response receipts are retained by the shared MCP harness. Merely opening
a target or enumerating a tool cannot pass these assertions.

Integrate the reusable callbacks alongside the existing helpers:

```python
from firmware_format_cases import CASE_IDS, run_firmware_format_cases
run_firmware_format_cases(mcp, work, test)
```

Copy the helper and its adjacent `firmware-format-fixtures.json` into each test
project. Register the fourteen `CASE_IDS` in required case lists and independent
Spread variants. Use a fresh work/output directory for each run; the helper
refuses to overwrite existing case directories. Shared runner and Spread edits
remain the primary agent's responsibility.

## Actual host contract results

On 2026-11-17 all fourteen cases passed against the unchanged `rea/` subtree
extracted from verified SDK artifact
`c7373502e97f32c34be99ba7fd92e7ea5832caf31121aa79a747badd27cf22c5`.
`host-contract-runtime/provenance.json` records that extraction and exact source
commit; a similarly numbered npm package was rejected as the test runtime
because it lacked some pinned-source modules. Node 24.22.1 ran an owned MCP
process with separate HOME, TMPDIR and working directories. This was a host
fixture-contract check, not a fresh Workshop installation or acceptance of the
later Frida-corrected artifact.

| Case suffix | Verified contents | Members | Extracted bytes | Host result |
| --- | --- | ---: | ---: | --- |
| `uimage` | CRC-bearing legacy image payload | 1 | 25 | Pass |
| `fit` | Embedded image with SHA256 hash node | 1 | 25 | Pass |
| `intel-hex` | Checksummed contiguous address region and EOF | 1 | 25 | Pass |
| `srec` | Checksummed S1 region and S9 termination | 1 | 25 | Pass |
| `esp-image` | Canonical ESP32-C3 descriptor and four segments | 4 | 400 | Pass |
| `uf2` | Two contiguous RP2040-family blocks | 1 | 512 | Pass |
| `dfuse` | CRC-bearing target element and address range | 1 | 25 | Pass |
| `esp-flash-image` | Bootloader, partition table and data partition | 3 | 40,960 | Pass |
| `android-boot-image` | v3 kernel and ramdisk regions | 2 | 48 | Pass |
| `android-ota-payload` | Full REPLACE operation reconstructs boot partition | 1 | 4,096 | Pass |
| `ines` | Header, two PRG banks and CHR bank | 4 | 40,976 | Pass |
| `godot-pck` | Plain v1 PCK member with MD5 integrity | 1 | 25 | Pass |
| `unityfs` | LZ4-compressed block directory and member | 1 | 25 | Pass |
| `wxapkg` | Plain mini-program package member | 1 | 25 | Pass |

Every returned inventory reported `container-entries` coverage `complete` for
its fixture. The MCP server then exited zero on stdin EOF in 0.118 seconds.
Evidence: `validation-logs/agent-c-firmware-contracts2.log` and zero exit record;
raw receipts and per-case results remain in the isolated worktree's
`.firmware-host-proof/results2/`. The prior failed fixture attempt is retained
in `results/`: it exposed the inspection envelope mistake and an inappropriate
single ESP segment sample. The corrected sample uses upstream's canonical
four-segment factory constant; the engine was not modified.

Both attempts' raw receipts are also archived at
`validation-logs/agent-c-firmware-contract-evidence.tar.gz`, SHA256
`412533a57ee1c59c5eeddeeae959ff08ff13e78677c27fd4c498b5e1d0c9ff91`.
Installed SDK runs of all fourteen cases remain required and must be recorded
against their actual final artifact SHA256.

## Coverage limits

Complete fixture traversal does not establish support for every producer
variant. These cases do not prove encrypted Godot/WeChat packages, arbitrary
Unity serialized object semantics, ESP flash decryption or actual boot state,
UF2 flashing, iNES mapper/emulator behavior, Android signature authentication,
OTA delta application, compressed/non-REPLACE OTA operations, or every boot
image version. The OTA reader explicitly limits reconstruction to supported
full-image operation types; this test selects REPLACE only. FIT external-data
layouts and other uImage compression/multi-image variants have upstream tests
but are not exercised here. Such branches must retain their own upstream or
platform limitations and separate verification status.
