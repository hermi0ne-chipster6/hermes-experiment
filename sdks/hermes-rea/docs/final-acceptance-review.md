# Final acceptance review

## Current reconciliation: 2026-11-17

The full cold SDKcraft build produced artifact
`c7373502e97f32c34be99ba7fd92e7ea5832caf31121aa79a747badd27cf22c5`.
Its fresh Workshop `validation-final` (`782b8b9c`) reached Ready; retained
`final-launch-tasks.log` shows completed launch tasks, and
`final-launch-info.log` identifies local revision x2. Registration and installed
identity checks are recorded separately by the primary agent. These facts do
not establish final acceptance of the subsequent Frida replacement.

The first 99-case run exposed a real sequencing defect: 17 cases passed,
SQLite timed out after the Frida lifecycle, and 81 selected cases were aborted.
`final-initial-run-classification.json` distinguishes those categories; aborted
cases are not 81 independently observed capability failures. A fresh MCP run
of the remaining 82 cases passed 81, including SQLite and the independently
synthesized `tshark-policy` confinement proof. Its sole failure was the desktop
fixture's action-response decoder. After correcting that test without changing
REA, `desktop-final2` passed the complete real lifecycle; see
[desktop validation](desktop-validation.md) for raw response and screenshot
identities. Across these runs each original selected capability has a passing
case, but the original same-session Frida sequencing defect still disqualifies
that artifact as a complete SDK.

The proposed matched Frida 17.25.1 override subsequently passed the direct
37-record lifecycle probe and the five-case mixed MCP sequence in a disposable
runtime copy. Those results establish the candidate correction, not installation
of a newly built SDK. The corrected SDK needs a successful package build, strict
artifact comparison, fresh installed identity checks including Frida package,
native binding and compatibility disclosure hashes, and the complete required
suite in one session. The added `frida-process-lifecycle` case must run as part
of that acceptance. Fresh persistence/SSH checks and independent reinstall
must also be tied to the corrected artifact's SHA256.

The official `sdkcraft test` VM execution remains separately blocked by the
VPS's missing `/dev/kvm`; prior job aborts must not be reported as passes.
Container-based operational evidence does not change that infrastructure fact.

## Reuse candidate rejected before installation

The first Frida-corrected reuse artifact completed SDKcraft packing but failed
strict archive comparison: 32 unrelated nested metadata paths were missing
from AJV schemas and Zig's standard library. Artifact
`86deb4c23369a234fd65c08ba5097f0457181c5d37f992ed5e24f77632e774b6`
was rejected before registration or installation. Its archive, full comparison
report and nonzero acceptance results remain in
`validation-logs/frida-rebuild-attempt1/`; see
[rebuild provenance](rebuild-provenance.md#first-candidate-rejected-root-exclusion-correction).

The primary corrected GNU tar's unanchored `--exclude=meta` to a root-anchored
exclusion in both the context generator and generated recipe. Comparator rules
remain unchanged and a focused actual-tar regression reproduces the omission
and verifies the corrected boundary. The second official build, strict full
comparison and all installed-runtime acceptance gates remain pending; the
first build's successful pack command is not a successful SDK acceptance.

## Historical pre-install review

The following read-only review preceded the fresh installation and exposed
issues subsequently addressed or tested. It covers acceptance orchestration, package registration,
setup hooks, 96 selected checks and desktop fixture on 2026-11-17. This review
does not establish that the final package has been installed or accepted.

## Findings requiring integration attention

1. **Runtime policy proof was absent from the final sequence.** At review time,
   `validation-logs/postbuild-final-acceptance.sh` ended after the functional
   suite. Its packet-capture assertion proves successful decoding, but does not
   prove an enforced profile or a denied write outside the permitted paths.
   The old staged `tshark_policy_proof.py` also named the previous
   `sdk-validation-first` capture and assumed a pre-existing denial directory.
   Run the new standalone helper below against the final suite's capture before
   claiming final runtime-policy acceptance. No runtime-policy pass is claimed
   by this review or the helper's syntax validation.

2. **Desktop capacity is checked late.** The actual 20,000,000,000-byte Docker
   free-space gate is preserved, but `desktop-build` runs after compiler,
   Electron and other fixtures, including the desktop runtime archive, have
   consumed storage. Record real Docker-root free capacity after builder cleanup
   and fresh launch, before fixture installation. If headroom is marginal,
   execute the standalone desktop case earlier and retain its independent
   result, or reclaim verified disposable artifacts before the full sequence.
   Do not override the gate. A late `unavailable` is a failed required check,
   not successful desktop acceptance.

3. **Launch diagnostics need an explicit acceptance assertion.** The final
   script captures `changes`, `tasks` and `info`, but does not parse the captured
   terminal state. Require the launch change/tasks to be Done and the fresh
   Workshop to be Ready. Retain its identity so a retry against an existing
   instance is not described as an independent fresh install.

4. **Partial-run markers should not be reused as current success.** The overall
   script has an EXIT trap, but the preflight and functional `.exit` files are
   written only on success. Archive or clear prior run markers before retrying,
   and record actual per-step exits. Validate final `results.json` contains
   exactly the 96 unique requested IDs with `status: pass`; the existing
   `--only "$checks" --require "$checks"` correctly makes an unavailable
   selected case fail rather than silently skip it.

## Standalone enforced-policy proof

Stage `tests/main/launch/tshark_policy_case.py` alongside the final fixtures. Run
as the installed `rea` account after the final packet-capture fixture exists:

```bash
python3 /project/tshark_policy_case.py \
    --pcap /var/lib/hermes-rea/work/sdk-validation-final/fixtures/sdk-network.pcap \
    --output /var/lib/hermes-rea/work/tshark-policy-final
```

The helper checks the live child label through `/proc/<pid>/attr/current` while
the child waits for capture bytes. It requires `tshark (enforce)`, valid packet
decoding, output over an inherited unnamed Unix socket, and a write/read capture
round-trip inside the permitted work directory. It then creates a private
directory directly under the worker home, outside work/inbox, proves normal
same-user writes to the exact destination before and after the TShark refusal,
and requires the refusal to name that destination and report a permission error.
The identical valid input is supplied through stdin for both output tests, so
an unreadable input path or an invalid capture cannot explain the denied write.

The helper needs no root access or `aa-status` call and does not modify policy.
It retains `confinement-proof.json`, removes its own positive capture and denial
directory, and confirms the caller's input hash is unchanged. A zero exit plus
`status: pass` is required. Parent integration owns the real run; local review
performed syntax validation only.

## Existing acceptance strengths and limits

The registration verifier compares packed hooks, environment wrapper and TShark
policy bytes to current source, verifies the exact already-proven NativeAOT JAR
digest, and verifies the registered artifact digest against the newly packed
file. The fresh definition lists Docker before Hermes, allowing setup-base to
grant the worker access to the Docker group. Setup-project restores the mounted
home's owner/mode and executes the real native CLI under `rea`; the new ADB
case checks that account's home and provider-created key directory separately.

The desktop helper requires actual images at computer creation, app capture and
the post-typing wait, verifies/decodes them with the installed Pillow, checks the
same computer identity throughout, verifies retained seed/end bytes and exact
INI before/after values, and requires confirmed teardown. Those assertions do
not accept a runtime archive build or Docker `hello-world` as a desktop pass.
They establish the local model-free lifecycle, not export/replay or external
model orchestration. No additional desktop assertion defect was identified in
this review; the first live final run remains necessary.

## Primary integration follow-up

The primary integrated the policy helper as independent `tshark-policy` case 97 and a Spread provider variant. It synthesizes its own valid packet input, so it does not depend on another case running first. The integrated case passed after a live correction on the historical artifact; final-package acceptance remains pending. The pre-correction run is retained and failed at inherited Unix socket output after successful packet decoding.

The queued fresh-install and separate-account reinstall scripts now explicitly require `status: ready` and record real desktop doctor output before fixture installation. The build queue was suspended only while waiting on `sleep`, then safely requeued; the active build was untouched. Source preparation has 97 unique selected cases. Fresh phase records have no prior success markers; any retry must retain failed evidence and use distinct records.
