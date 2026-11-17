# Finite reconstruction verification fixture

`tests/main/launch/reconstruction_case.py` adds one model-free case, `reconstruction-verification`, against unchanged REA at `51459cf203ae1eb6b586a95b21899eaa0f631823`. It requires Python's standard library, the existing `functional.py` MCP client and the installed REA launcher. It needs no external model, native decompiler, compiler, device or network service.

**Corrected installed execution passed** on 2026-11-17: standalone case exit 0, six real verification responses checked, duration 12.86 seconds. The development installation is based on the earlier SDK archive SHA256 `77fc26d1660fe359511d41a3cc06c76d6224be8dda9b80367261bed61cad5af3`. This proves the recorded finite structural-artifact case in that installation; **final rebuilt-artifact/fresh-install acceptance remains pending**. The expected verifier `fail` and `unknown` outcomes below were independently checked in raw responses, not inferred from registration or the case summary.

## Exact contract and scope

Source owners in the pinned upstream tree:

- `src/contracts/sessionToolContracts.ts`: `compare_artifacts` accepts complete retained inventory references; `verify_reconstruction` accepts a finite specification.
- `src/domain/reconstructionVerificationSchemas.ts`: the input is `{specification: {name, claims}}`; each tested claim is `{kind: "structural-artifact", claim_id, title, comparison_evidence_id, dimension: "overall"}`. Claim IDs and comparison selectors must be unique.
- `src/application/artifacts/ArtifactComparisonEvidence.ts`: comparisons retain the exact left/right source Evidence IDs and produce real comparison Evidence.
- `src/application/investigation/InvestigationWorkflows.ts`: verification reads the session's immutable Evidence bundle and resolves its Evidence closure.
- `src/domain/reconstructionVerification.ts`: structural claims require observed shipped-artifact authority, independent observations and corroborating retained artifact inventories; the verifier recomputes the artifact comparison. A changed observation fails; an unchanged observation without independent sources stays unknown. Pass applies only to the declared finite claims.

The helper generates four inert ZIP archives in a new owned directory. The positive pair contains identical bytes but is independently selected and inspected. A separate negative pair starts from another observation of the original bytes and changes only `payload.txt`'s bytes, retaining its length and fixed ZIP metadata. The two pairs have disjoint source Evidence IDs, so a residual Unknown created by the negative comparison does not affect the positive or mixed passing claim. The second member remains unchanged. All facts come from actual `open_binary`, `inspect_artifact`, `compare_artifacts` and `verify_reconstruction` requests, never fabricated Evidence records or mocked tool responses. Each opened artifact is closed in `finally`.

| Actual operation | Required semantic assertion |
| --- | --- |
| Inventory four selected ZIPs | Four distinct observed shipped-artifact Evidence IDs; original/equivalent SHA256 equal, changed SHA256 different, total sizes equal. |
| Compare original/equivalent | `unchanged` and no changed entries. |
| Compare original/changed | `changed`; exact `payload.txt` row is changed in the `content` dimension. |
| Verify equivalent-only specification | Overall and sole claim `pass`; one passed structural claim, zero failed/unknown. |
| Verify changed-only specification | Overall and sole claim `fail`; one failed structural claim, zero passed/unknown. This is expected behavior, not an engine failure. |
| Verify mixed specification | Overall `fail`, while retaining one passing and one failing claim with exact counts. Reversing claim order preserves `specification_sha256`. |
| Deliberately compare the positive original with the changed input after pass/fail/mixed checks | The original unchanged claim becomes `unknown`; its exact residual Unknown ID, question, supporting/contradicting source IDs and recommended-probe citation are preserved. |
| Compare an inventory to itself, then verify | Comparison is `unchanged`, but verification is `unknown` with the explicit independent-observation limitation. Self-comparison cannot manufacture reconstruction proof. |
| Every verification | Exact claim IDs, kind/dimension, observed statuses, comparison IDs, left/right source IDs and Evidence-link closure; the upstream global-equivalence limitation is retained. |

Fixtures, all six specification inputs, raw MCP responses and the exported Evidence bundle are retained for review. The successful case's detail includes their paths, fixture and bundle digests, Evidence identities and the expected outcome matrix. It does not claim behavioral or function reconstruction, arbitrary packaging equivalence, general residual-unknown resolution (the fixture checks propagation only) or a complete reconstruction-readiness/obligation-ledger audit. Existing `unknown-lifecycle` remains a separate case.

## Initial installed result and harness correction

The first installed run failed the strict positive assertion: the comparison was `unchanged`, but `verify_reconstruction` returned `unknown` with `unk_6ea0f0b4a066cf834fd8e5201367a7f2598e944c227ae807e33f81ac035a39f3`. The initial fixture reused the positive original Evidence in the changed comparison, which had already recorded an unresolved `artifact-comparison` question. This matches `ArtifactComparisonEvidence.ts#artifactUnknownInput` and `reconstructionUnknowns.ts#reconstructionClaimUnknowns`: unscoped unresolved questions are relevant when they cite any source of the selected claim.

Saved failure: `/root/dev/rea-sdk/validation-logs/reconstruction-installed.log`. Raw worker responses: `/home/rea-sdk-dev/.local/share/workshop/id/65743ca5/validation/mount/hermes-rea/state/work/reconstruction-installed/`, particularly `010-compare_artifacts.json`, `011-compare_artifacts.json` and `013-verify_reconstruction.json`.

The revised fixture isolates the positive and negative source observations, preserves strict pass/fail/mixed assertions, then deliberately reproduces and asserts shared-source residual-Unknown propagation. It does not resolve or suppress upstream questions to manufacture a pass. The corrected installed rerun passed with the exact outcomes recorded below; the initial failure remains part of the validation history.

## Verified installed evidence

Worker output: `/var/lib/hermes-rea/work/reconstruction-installed2/`. The same files are readable on the host at `/home/rea-sdk-dev/.local/share/workshop/id/65743ca5/validation/mount/hermes-rea/state/work/reconstruction-installed2/`. The numbered response names in this table are relative to that directory.

| Raw response | Verified outcome |
| --- | --- |
| `013-compare_artifacts.json` | Independent equal pair: unchanged, no changes. |
| `014-compare_artifacts.json` | Disjoint negative pair: changed; `payload.txt` has a changed content dimension. |
| `015-compare_artifacts.json` | Same-source comparison: unchanged. |
| `016-verify_reconstruction.json` | Equivalent-only: pass; 1 passed, 0 failed, 0 unknown. |
| `017-verify_reconstruction.json` | Changed-only: fail; 0 passed, 1 failed, 0 unknown. |
| `018-verify_reconstruction.json`, `019-verify_reconstruction.json` | Mixed and reversed order: fail; each has 1 passed, 1 failed, 0 unknown; specification SHA256s are equal. |
| `020-compare_artifacts.json`, `021-list_unknowns.json`, `022-verify_reconstruction.json` | Deliberate shared-source change records `unk_53bc8fb67f25beea054d0c7870d2e044d1004a4cf4293377b996bed61d9755f3`; the previously unchanged claim becomes unknown and cites that exact residual question and recommended probe. |
| `023-verify_reconstruction.json` | Same-source verification: unknown; retains the explicit missing-independent-observation limitation. |
| `mcp-shutdown.json` | Normal stdin EOF; MCP process exit 0 in 0.165 seconds. |

The independent review checked all six raw verifier status/count results, the two mixed specification digests, exact changed member, propagated Unknown identity and same-source limitation. It also recomputed every ZIP digest and the exported bundle digest from retained files:

- Result log: `/root/dev/rea-sdk/validation-logs/reconstruction-installed2.log`; exit file `reconstruction-installed2.exit` contains `0`.
- `results.json` SHA256: `f3b9e6d73e9f0412a6fb350b005d888ad32f69aa8573becb684ce5df89edf299`.
- `fixtures/reconstruction-cah65las/{original,equivalent,change-original}.zip`: each SHA256 `60d3d6a7ce4ba09ffc86f9c06deb080aed27449041daaa74d4e10e712b76c896`.
- `fixtures/reconstruction-cah65las/changed.zip`: SHA256 `0833d4fc14e81cd21de3c8616a1f53945f8249be520962c1b7d394c2422d9919`.
- `fixtures/reconstruction-cah65las/reconstruction-evidence-bundle.json`: SHA256 `441a38562dfa8dc4db1ae5df615f53431c8577127c05b7599e4f9ccc791f3b71`.

These digests identify the saved case evidence, not a newly rebuilt SDK. No fresh 95-case suite result is claimed by this standalone pass.

## Standalone installed-worker invocation

Keep the helper beside the existing `functional.py`, then run as the same unprivileged worker user through the normal installed launcher:

```sh
python3 reconstruction_case.py \
  --rea /usr/local/bin/rea \
  --output /var/lib/hermes-rea/work/reconstruction-validation
```

The helper initializes MCP and writes `results.json`, `initialize.json`, numbered raw tool responses, `mcp-stderr.log` and `mcp-shutdown.json`. A success has case status `pass` and detail outcomes `equivalent: pass`, `changed: fail`, `mixed: fail`, `shared-source-residual: unknown`, `same-source: unknown`. It never marks a failed tool invocation or assertion as an expected negative result. Use an output directory dedicated to this invocation; separate runtime identities belong in separate output directories.

## Runner integration reference

The primary has integrated the helper into the functional runner and Spread variant. The registration uses the existing selection/result wrapper after MCP initialization and outside any active binary session:

```python
from reconstruction_case import run_reconstruction_case

test("reconstruction-verification", lambda: run_reconstruction_case(mcp, work))
```

Use the existing required-case semantics:

```sh
python3 functional.py --output /var/lib/hermes-rea/work/sdk-validation-reconstruction \
  --only reconstruction-verification --require reconstruction-verification
```

The matching `tests/main/providers/task.yaml` variant is `reconstruction_verification`, with this environment entry:

```yaml
  CHECK/reconstruction_verification: reconstruction-verification
```

The existing `cp ../launch/*.py .` already copies the new helper, and the variant's existing `--only "$CHECK" --require "$CHECK"` invokes it. This adds one job; it does not change the VM/KVM requirement or convert unavailable official jobs into passes. The primary's selected-case checklist now includes this case; coverage mapping must cite the actual installed run and retain the final-artifact qualifier. Keep the row scope restricted to finite structural-artifact verification; general unknown-resolution verification is still separate.

This evidence update changes only this document. The primary owns runner/Spread integration, capability-map reconciliation, final packaging and the queued fresh-install suite. This review did not modify upstream or operate shared containers.
