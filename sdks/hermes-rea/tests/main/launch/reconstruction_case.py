#!/usr/bin/env python3
"""Real finite reconstruction verification over retained, inert ZIP inventories.

Import run_reconstruction_case(mcp, work) into functional.py, or run this file
beside functional.py with --rea 'rea' --output /absolute/owned/output.
The existing MCP client retains raw responses. No model or native provider is
required. A successful case includes expected verifier fail/unknown outcomes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import tempfile
import time
import zipfile


CASE_ID = "reconstruction-verification"
UPSTREAM_COMMIT = "51459cf203ae1eb6b586a95b21899eaa0f631823"


def run_reconstruction_case(mcp, work):
    """Use an initialized MCP client with no active binary; retain all fixtures."""
    work = Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    owned = Path(tempfile.mkdtemp(prefix="reconstruction-", dir=work))

    def evidence(call, arguments):
        value = mcp.call(call, arguments)
        assert re.fullmatch(r"ev_[a-f0-9]{64}", value.get("evidence_id", "")), value
        assert value["operation"] == call, value
        assert isinstance(value.get("normalized_result"), dict), value
        return value

    def write_zip(name, payload):
        path = owned / name
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            # Fixed headers make two independently selected files byte-identical.
            for member, content in (("payload.txt", payload), ("unchanged.txt", b"stable\n")):
                entry = zipfile.ZipInfo(member, date_time=(2020, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, content)
        return path

    paths = [write_zip("original.zip", b"hermes-original\n"),
             write_zip("equivalent.zip", b"hermes-original\n"),
             write_zip("change-original.zip", b"hermes-original\n"),
             write_zip("changed.zip", b"hermes-modified\n")]
    digests = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    assert digests[0] == digests[1] == digests[2] and digests[0] != digests[3]
    assert len({path.stat().st_size for path in paths}) == 1
    inventories = []
    for path in paths:
        mcp.call("open_binary", {"path": str(path)})
        try:
            inventory = evidence("inspect_artifact", {"detail": "complete"})
            assert inventory["authority"] == "shipped-artifact"
            assert inventory["confidence"] == "observed"
            inventories.append(inventory)
        finally:
            mcp.call("close_binary")
    assert len({item["evidence_id"] for item in inventories}) == 4, "Need independent observations for both comparison pairs"

    def compare(left, right):
        result = evidence("compare_artifacts", {
            "left": {"kind": "retained-evidence", "evidence_id": left["evidence_id"]},
            "right": {"kind": "retained-evidence", "evidence_id": right["evidence_id"]}})
        assert result["parameters"]["left_evidence_ids"] == [left["evidence_id"]]
        assert result["parameters"]["right_evidence_ids"] == [right["evidence_id"]]
        return result

    equivalent = compare(inventories[0], inventories[1])
    # A changed comparison records a residual Unknown against its source IDs.
    # Keep those sources disjoint from the positive and mixed passing claim.
    changed = compare(inventories[2], inventories[3])
    assert set(equivalent["evidence_links"]).isdisjoint(changed["evidence_links"])
    self_comparison = compare(inventories[0], inventories[0])
    assert equivalent["normalized_result"]["status"] == "unchanged"
    assert equivalent["normalized_result"]["changes"] == []
    assert changed["normalized_result"]["status"] == "changed"
    payload_changes = [item for item in changed["normalized_result"]["changes"]
                       if item["logical_path"] == "payload.txt"]
    assert len(payload_changes) == 1, changed["normalized_result"]
    assert payload_changes[0]["classification"] == "changed"
    assert "content" in payload_changes[0]["dimensions"]
    assert self_comparison["normalized_result"]["status"] == "unchanged"

    comparisons = {item["evidence_id"]: item for item in (equivalent, changed, self_comparison)}

    def claim(name, comparison):
        return {"kind": "structural-artifact", "claim_id": name,
                "title": "The declared artifact inventory remains equivalent",
                "comparison_evidence_id": comparison["evidence_id"], "dimension": "overall"}

    passing = claim("equivalent-artifact", equivalent)
    failing = claim("changed-artifact", changed)
    unresolved = claim("independent-observation-required", self_comparison)

    def verify(label, claims, expected, filename=None):
        specification = {"name": label, "claims": claims}
        (owned / ((filename or label) + "-specification.json")).write_text(json.dumps(specification, indent=2) + "\n")
        value = evidence("verify_reconstruction", {"specification": specification})
        result = value["normalized_result"]
        items = {item["claim_id"]: item for item in result["claims"]["items"]}
        assert set(items) == set(expected), result
        expected_overall = "fail" if "fail" in expected.values() else "unknown" if "unknown" in expected.values() else "pass"
        assert result["status"] == expected_overall, result
        assert result["summary"] == {"total": len(claims), "passed": list(expected.values()).count("pass"),
                                     "failed": list(expected.values()).count("fail"),
                                     "unknown": list(expected.values()).count("unknown"),
                                     "behavioral": 0, "structural": len(claims)}, result
        assert re.fullmatch(r"[a-f0-9]{64}", result["specification_sha256"])
        all_links = set()
        for selected in claims:
            item = items[selected["claim_id"]]
            comparison = comparisons[selected["comparison_evidence_id"]]
            assert item["status"] == expected[selected["claim_id"]], item
            assert item["observed_status"] == comparison["normalized_result"]["status"], item
            assert item["kind"] == "structural-artifact" and item["dimension"] == "overall"
            assert item["comparison_evidence_id"] == comparison["evidence_id"]
            assert item["left_evidence_ids"] == comparison["parameters"]["left_evidence_ids"]
            assert item["right_evidence_ids"] == comparison["parameters"]["right_evidence_ids"]
            expected_links = {comparison["evidence_id"], *comparison["evidence_links"]}
            assert set(item["evidence_links"]) == expected_links, item
            all_links.update(expected_links)
        assert set(result["evidence_links"]) == all_links, result
        assert "Pass means every declared claim passed; it does not establish global implementation equivalence." in result["limitations"]
        return value

    passed = verify("equivalent", [passing], {passing["claim_id"]: "pass"})
    failed = verify("changed", [failing], {failing["claim_id"]: "fail"})
    mixed_expected = {passing["claim_id"]: "pass", failing["claim_id"]: "fail"}
    mixed = verify("mixed", [passing, failing], mixed_expected)
    reordered = verify("mixed", [failing, passing], mixed_expected, filename="mixed-reordered")
    assert mixed["normalized_result"]["specification_sha256"] == reordered["normalized_result"]["specification_sha256"]
    # Reproduce the original harness failure deliberately after proving pass/fail:
    # an unresolved comparison question follows shared source Evidence, even
    # when the selected comparison itself still says unchanged.
    shared_change = compare(inventories[0], inventories[3])
    assert shared_change["normalized_result"]["status"] == "changed"
    questions = mcp.call("list_unknowns", {"domain": "artifact-comparison", "offset": 0})["result"]
    assert questions["next_offset"] is None, questions
    question_text = f"Artifact comparison is changed (comparison {shared_change['evidence_id']})"
    related = [item for item in questions["items"] if item["question"] == question_text]
    assert len(related) == 1 and related[0]["status"] != "resolved", related
    assert inventories[0]["evidence_id"] in related[0]["supporting_evidence_ids"]
    assert inventories[3]["evidence_id"] in related[0]["contradicting_evidence_ids"]
    propagated = verify("shared-source-residual", [passing], {passing["claim_id"]: "unknown"})
    propagated_claim = propagated["normalized_result"]["claims"]["items"][0]
    assert related[0]["unknown_id"] in propagated_claim["unknown_ids"], propagated_claim
    assert "Residual unknown: " + question_text in propagated_claim["limitations"], propagated_claim
    assert any(related[0]["unknown_id"] in probe["unknown_ids"]
               for probe in propagated["normalized_result"]["recommended_probes"])
    unknown = verify("same-source", [unresolved], {unresolved["claim_id"]: "unknown"})
    assert any("independent original and reconstruction observations are unavailable" in message
               for message in unknown["normalized_result"]["claims"]["items"][0]["limitations"])
    bundle = owned / "reconstruction-evidence-bundle.json"
    mcp.call("export_evidence_bundle", {"path": str(bundle)})
    assert bundle.is_file() and bundle.stat().st_size > 0
    return {"upstream_contract_commit": UPSTREAM_COMMIT, "fixture_directory": str(owned),
            "fixture_sha256": dict(zip((path.name for path in paths), digests)),
            "inventory_evidence_ids": [item["evidence_id"] for item in inventories],
            "verification_evidence_ids": {label: item["evidence_id"] for label, item in
                                          (("pass", passed), ("fail", failed), ("mixed", mixed),
                                           ("shared-source-residual", propagated), ("unknown", unknown))},
            "outcomes": {"equivalent": "pass", "changed": "fail", "mixed": "fail", "shared-source-residual": "unknown", "same-source": "unknown"},
            "propagated_unknown_id": related[0]["unknown_id"],
            "canonical_claim_order_digest_equal": True, "changed_member": "payload.txt",
            "evidence_bundle": str(bundle), "evidence_bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
            "scope": "Finite structural-artifact claims over real retained ZIP inventories; no model, code execution, behavioral/function reconstruction, general unknown resolution, or global source-equivalence claim"}


def main():
    from functional import MCP

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rea", default="rea", help="CLI command, shell-like splitting without a shell")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    client = None
    try:
        client = MCP(shlex.split(args.rea) + ["mcp"], output)
        initialized = client.request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                    "clientInfo": {"name": "hermes-reconstruction-validation", "version": "1"}})
        (output / "initialize.json").write_text(json.dumps(initialized, indent=2) + "\n")
        client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        result = {"test": CASE_ID, "status": "pass", "detail": run_reconstruction_case(client, output / "fixtures")}
    except Exception as error:
        result = {"test": CASE_ID, "status": "fail", "reason": f"{type(error).__name__}: {error}"}
    finally:
        if client is not None:
            client.close()
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    (output / "results.json").write_text(json.dumps([result], indent=2) + "\n")
    print(json.dumps(result), flush=True)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
