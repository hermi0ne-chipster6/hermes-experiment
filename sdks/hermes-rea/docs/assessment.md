# Existing SDK assessment

The existing source was located through authenticated GitHub access in
`hermi0ne-chipster6/hermes-experiment`, at `sdks/hermes-rea`. Its history was
preserved by a full clone; development continues on `dev/hermes-rea-full-parity`
from `df4d649`. The SDK sources entered this repository in `e5ddd8f`; the later
commit adds maintenance CI. No replacement SDK was created.

The live Store inspection on 2026-11-17 found publisher Cody Prevost
(`codyprevost`), one published revision, version 6.7.0 on `latest/edge`,
Ubuntu 26.04 amd64, approximately 637 MB. Stable/candidate/beta had no releases.

The original package uses SDKcraft dump parts for Node 26.13.0, locked npm
REA 6.7.0, Ghidra 12.1.4, and Frida 17.23.2's native binding. Its setup-base
hook installs JDK 25, SSH, binutils, GDB, file, and Python pwntools. A separate
`rea` system account owns analysis directories on a persistent state mount.
An operator-supplied public key allowlist authorizes a forced SSH command;
the original wrapper accepts native MCP stdio, a local version probe, and
bounded digest-verified artifact input. It is not an arbitrary remote shell.

That design is retained. Its principal gaps for this task were the lack of
a normal local CLI entrypoint, missing provider dependencies beyond Ghidra,
and insufficient capability coverage. The original Spread job checks a version,
Java, SSH configuration, readiness and a nonempty MCP inventory. It does not
assert full inventory parity or exercise the broad REA engine.

The repository's historical `reports/verification.md` reports actual Ghidra
procedure discovery, objdump, 207 MCP tools, restricted SSH boundary checks,
and Frida loading on the previous development host. Those are historical
observations, not fresh validation on this VPS. Its Spread section already
records a missing KVM boundary. The raw historical logs were not all included
in this source snapshot.

Current upstream main and npm 6.9.0 are different code. The SDK now builds
unmodified upstream source at the exact commit and checksum in `SOURCE.json`.
The baseline dependency lock is the upstream archive's `package-lock.json`;
the old `npm/` files are retained as historical 6.7.0 packaging inputs and are
no longer consumed by SDKcraft. Node follows upstream's `.nvmrc` (24.22.1).

The added local `rea` and `rea-agents` launchers forward all arguments and
preserve explicit provider environment selections. The SSH launcher retains
its command restrictions and uses the same packaged runtime defaults. Local
CLI users retain their own HOME and working directory. Use the `rea` account
and `/var/lib/hermes-rea/work` for the shared persistent worker state; arbitrary
files in a container's writable layer do not survive Workshop refresh.

Provider binaries and Python dependencies are built into immutable SDK parts.
Distribution libraries remain setup-base apt dependencies, following Canonical
conventions and the base's security updates. Immutable upstream source/assets,
Cargo/npm locks and hashed Python wheels constrain build inputs; apt package
versions are recorded at validation time, so installation is reproducible in
procedure and functionality rather than promised byte-for-byte across future
Ubuntu archive updates.

The full upstream repository and five exact submodules are also retained as
14,149 tracked entries, with an independent per-file manifest. Original malformed
symlink fixtures are preserved through deterministic archive staging and final
prime extraction; this avoids SDKcraft's staging traversal of those fixtures.
The operational `rea setup --desktop-build` archive producer additionally needs
three unchanged files omitted by upstream's npm publish list; those files are
copied into the production runtime package.

The expanded package includes separate native, managed, Android, JavaScript,
browser, firmware, capture, signals, debugger and runtime toolchains. Cutter's
official Qt5 distribution accepts the unchanged REA bridge; the same-version
Qt6 distribution was tested and rejected that bridge. Desktop-build clients
include AgentEnv and Docker with its required Buildx/Compose plugins. External
computer services, model configuration, licensed engines and live devices remain
explicit caller requirements rather than implicit provider substitutions.

The archive's intended A/B/C architecture is reconciled in
[project-context-reconciliation.md](project-context-reconciliation.md). This
branch validates C's SDK and interfaces; production Hermes routing, independent
audit and other VPS instances are outside this development work.


Current implementation and acceptance are distinct. The full cold policy/HOME-corrected SDK build completed and its 1,695,103,384-byte artifact, SHA256 `c7373502e97f32c34be99ba7fd92e7ea5832caf31121aa79a747badd27cf22c5`, installed in a fresh ordinary-user Workshop with verified hooks, source archive and native extension. Packet confinement remained enforced, ADB initialized its owned HOME, and a real no-model AgentEnv desktop ran, changed retained file state, produced decoded screenshots and tore down successfully. All 99 selected individual cases have passing observations across runs, but the first single-session run exposed a real Frida 17.23.2 subprocess lifecycle defect. It must not be described as a passing full suite.

The correction is an explicitly disclosed **provider override**, not a REA fork: install the complete official Frida 17.25.1 npm package and matching native addon while retaining the original REA source and lock. The baseline direct diagnostic failed 15 of 37 records; the corrected scratch runtime passed 37 of 37 and a five-case JavaScript/Frida/SQLite/Ghidra sequence in one MCP process. Scratch proof does not establish package contents. The corrected artifact is being built; strict artifact comparison, installed regression coverage and an independent clean reinstall remain acceptance gates. Source checks passed 125 repository tests, and official discovery now finds 97 jobs for the expanded 100-case functional coverage; execution of the KVM-backed official suite remains blocked by the missing `/dev/kvm`.

The earlier workers were retired with official Workshop operations only after their complete REA state mounts were preserved at `/home/rea-sdk-dev/preserved-state/validation-65743ca5` and `/home/rea-sdk-dev/preserved-state/validation-final-782b8b9c`. Immutable selected evidence includes `validation-logs/installed-functional/policy-build-and-frida-evidence.tar.gz`, SHA256 `c7b03a4b8e770aceb1ee2e2b3aa4e948b21533712adf2835ce74228c67bd3773`. No source history, uncommitted implementation work or raw failed-run evidence was discarded. [Validation](validation.md) records the artifact-specific outcomes and remaining gates.
