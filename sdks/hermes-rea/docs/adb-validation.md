# ADB initialization and provider-home regression

`tests/main/launch/adb_case.py` supplies case `adb-initialization`. **Corrected installed execution passed** on 2026-11-17 (case exit 0, 8.84 seconds) after the primary applied the generic HOME/setup fix live to the earlier SDK installation, based on archive SHA256 `77fc26d1660fe359511d41a3cc06c76d6224be8dda9b80367261bed61cad5af3`. **Final rebuilt-artifact/fresh-install validation remains pending.** This test qualifies real ADB server/key-directory initialization and REA device enumeration; it does not qualify physical/emulated device inspection, shells, packages or transfers. An empty device list is a valid observed result.

## Observed defect and contract

`/root/dev/rea-sdk/validation-logs/adb-initialization.log` records the original real failure as the `rea` user: ADB 34.0.5 exited 255 during startup because it could not create `/var/lib/hermes-rea/.android`. Device enumeration then exited 1 for the same reason. The mounted HOME was owned by `workshop` with mode 0755, so precreating selected cache children did not make other upstream default home writes possible. The primary owns the generic home-ownership/setup fix; this helper does not chmod/chown HOME or precreate `.android` to conceal a failure.

At pinned REA `51459cf203ae1eb6b586a95b21899eaa0f631823`:

- `src/contracts/adb/adbToolContracts.ts` and `src/domain/adb/adbDeviceAnalysis.ts` define `list_adb_devices({})` and its observed client, device array and `may_have_started_adb_server` result.
- `src/adb/AdbDeviceOperations.ts` performs real `start-server`, then `devices -l`.
- `src/adb/AdbServer.ts` deliberately treats the daemon as shared: REA may start it but never stops it. The test must therefore own its own server rather than kill a default or unrelated daemon.
- `src/adb/AdbConfiguration.ts` captures the environment and accepts absolute `REA_ADB_PATH`; `tests/boundary/providers/adb/adbSelectedLocalPaths.test.ts` explicitly proves captured `ADB_SERVER_SOCKET` propagation through version, startup and device calls.

AOSP documents `-L SOCKET`, `devices -l`, and foreground `server nodaemon`; its command parser selects `ADB_SERVER_SOCKET` when explicit connection flags are absent. The helper uses these actual routes rather than adding an upstream option. See the [ADB man page](https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/main/docs/user/adb.1.md) and [command parser](https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/main/client/commandline.cpp).

## First regression run and listener correction

The first new helper run failed before provider initialization: `/root/dev/rea-sdk/validation-logs/adb-provider-installed.log` reports `Owned adb server exited -6`; its `.exit` is `1`. Raw `adb-server.stderr` at `/home/rea-sdk-dev/.local/share/workshop/id/65743ca5/validation/mount/hermes-rea/state/work/adb-initialization-validation/` reports `listening on specified hostname currently unsupported`. The HOME/private-hidden-directory assertions had already passed after the live setup fix. `adb-cleanup.json` records the already-exited owned process and `listener_closed: true`.

This is a fixture compatibility error in `-L tcp:127.0.0.1:<port>`, distinct from the original unwritable-HOME defect. The helper now uses `-L tcp:<port>`, which keeps ADB's default loopback behavior because it does not pass `-a`. The exact `127.0.0.1` listener/PID ownership check is unchanged. AOSP's command parser explicitly handles the hostless `tcp:<port>` form; its help identifies `-a` as the option enabling all interfaces. The corrected run must still prove real daemon initialization, metadata and MCP enumeration.

The second run, `/root/dev/rea-sdk/validation-logs/adb-provider-installed2.log` (exit 1), started the owned daemon and successfully executed direct device enumeration, then rejected `.android` mode 0750. This is the packaged ADB-created directory mode, not a write-access defect: `rea` owns it, group/world write bits are absent, and its parent HOME is 0700. Raw metadata and cleanup are retained under the corresponding `adb-initialization-validation2/` host-state directory; cleanup terminated the owned foreground server and confirmed listener closure. The corrected assertion accepts 0700 or 0750 while preserving owner checks, private HOME0700 and private-key0600. No permissions are repaired by the helper. The third installed run passed with the evidence below; both earlier failures remain recorded.

## Verified installed result

Log: `/root/dev/rea-sdk/validation-logs/adb-provider-installed3.log`; `adb-provider-installed3.exit` contains `0`. Worker output is `/var/lib/hermes-rea/work/adb-initialization-validation3/`, visible on the host at `/home/rea-sdk-dev/.local/share/workshop/id/65743ca5/validation/mount/hermes-rea/state/work/adb-initialization-validation3/`.

| Recorded fact | Actual result |
| --- | --- |
| HOME and new hidden-directory probe | `rea`, UID 999, mode 0700 for both; probe removed. |
| Provider directory | `/var/lib/hermes-rea/.android`, `rea`, mode 0750. It already existed from the preceding real startup, so this third run alone is not a pristine key-generation proof. |
| Key metadata | Private key is a nonempty regular file owned by `rea`, mode 0600; public key is nonempty, owned by `rea`, mode 0644. No key contents were read or hashed by the helper/reviewer. |
| Owned ADB | Installed `/usr/lib/android-sdk/platform-tools/adb`, version `34.0.5-debian`; foreground PID 3105; selected socket `tcp:36403`, with the helper checking the exact owned `127.0.0.1` listener. |
| Direct and REA enumeration | Direct `adb-devices.stdout` contains only the device-list header; real `001-list_adb_devices.json` returns `devices: []`, the explicit environment-selected client, and `may_have_started_adb_server: false`. |
| REA Evidence | `ev_fd487ef9a2162ca221e7b88cac9d89b961a4b751226b727efbc5c0db27d0b26a`. |
| Server cleanup | `adb-cleanup.json`: terminated owned foreground process, exit -15, listener closed. |
| MCP cleanup | `mcp-shutdown.json`: stdin EOF, exit 0, 0.169 seconds. |

Independent review checked the raw MCP result against direct enumeration and the result metadata, and checked both cleanup files. `results.json` SHA256 is `e9d5ff1452d6a3d6033fc2b3d9b4f9a7e94a6b5219d50094a976e30fa9e7e395`; this is an evidence-file digest, not a key or SDK digest. The fresh final-artifact run must independently recheck HOME ownership, default provider storage and real startup. Device-specific operations remain untested.

## Assertions and cleanup

The helper requires the installed non-root `rea` account and its real passwd HOME. It checks HOME ownership and mode 0700, creates a unique empty hidden directory directly under HOME, checks that directory is `rea`-owned/mode 0700, and removes only that owned probe with `rmdir`. It does not substitute a writable fixture HOME.

It then starts the real installed ADB executable as an owned foreground child with `-L tcp:<port>` on an ephemeral TCP port other than 5037; it must actually bind `127.0.0.1`. Before any client request, Linux `/proc` socket metadata must prove that the listener belongs to that exact child; a competing process winning the port race fails the test. ADB mDNS auto-connect is disabled with an empty service list. No device-target command is issued.

The test runs direct `adb devices -l` and a dedicated initialized REA MCP child with matching `ADB_SERVER_SOCKET` and `REA_ADB_PATH`, then invokes `list_adb_devices({})`. It requires successful real enumeration, matching observed serial/state pairs, the exact selected executable, reported version, and the still-owned listener. Because the server already exists, the REA result must report that it did not start a new daemon.

The actual `$HOME/.android` must be a real directory owned by `rea`, mode 0700 or the packaged ADB default 0750, with no group/world write bits. Its parent HOME must remain mode 0700; the test does not chmod either directory. `adbkey` must be a nonempty regular file owned by `rea`, mode 0600; the nonempty public key permits mode 0600 or 0644. These checks use file metadata only: **no key bytes are read, hashed, logged, copied or exported**. Existing provider key material is retained. The helper unsets key-location/vendor-key overrides and ADB debug tracing in its children so it tests the default HOME path without dumping inherited authentication traces.

`finally` closes the owned MCP child and terminates/waits for the exact foreground ADB child, escalating only that child if necessary. It never issues `kill-server`, uses default port 5037, or removes `.android`. `adb-cleanup.json` must show listener closure before the case can pass. Raw server/client diagnostics and the MCP response are retained in the dedicated output directory; they are separate from private key files.

## Bounded audit of other default home paths

These source-owned defaults explain why a generic writable, private user HOME is needed; they are not additional execution-pass claims:

| Upstream owner | Default path/use |
| --- | --- |
| `src/application/SupportedClients.ts` | User client setup includes `.agents/skills` and `.agents/mcp.json`, including FreeBuff/shared user agents configuration. |
| `src/application/ClientConfigRoots.ts` | Client configuration defaults to `~/.config` where a valid explicit XDG root is absent. |
| `src/application/LinuxHopperCacheDirectory.ts` | Optional Hopper release cache defaults to `~/.cache/rea/hopper-releases`. |
| `src/desktop/BuildComputerEnvironment.ts`, `src/filesystem/cacheDirectory.ts` | Desktop setup runtime archives default beneath `~/.cache/rea/build-computer`. |
| `src/cutter/CutterBridgeClient.ts` | Bridge cache defaults beneath `~/.cache/rea/cutter-bridge`. The SDK Cutter wrapper also installs its user plugin under the XDG data root or `~/.local/share`. |
| `src/cli/updateNotice.ts` | Update-notice cache falls back to the user's `.cache` directory. |

Precreating just `.android` would address one symptom while leaving legitimate new home children unavailable. The unique hidden-directory probe exercises that generic requirement without invoking client registration, installing licensed engines or touching existing user configuration.

## Run and integrate

Keep `adb_case.py` beside `functional.py`, and execute as the installed worker user with normal HOME:

```sh
python3 adb_case.py --rea /usr/local/bin/rea \
  --output /var/lib/hermes-rea/work/adb-initialization-validation
```

A standalone run writes `results.json`. The importable helper owns its own MCP process so its socket selection is captured before REA starts; it must not reuse the functional runner's already-started MCP instance:

```python
from adb_case import run_adb_case

test("adb-initialization", lambda: run_adb_case(command, output / "adb-initialization"))
```

The primary has integrated Spread variant `adb_initialization` with `CHECK/adb_initialization: adb-initialization` and added the case to its 96-case checklist; the existing provider task copies `../launch/*.py`. Coverage must cite the actual runtime identity and keep `adbDevice` capped at partial because no device-specific operations run. Integration is not itself evidence that the queued fresh suite passed.

This evidence update changes only this document. Packaging, home ownership changes, live worker execution, runner/Spread integration and final rebuilt-artifact validation belong to the primary.
