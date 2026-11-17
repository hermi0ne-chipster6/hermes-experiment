"""Real MCP firmware/game-container checks using inert pinned-source fixtures."""
import base64
import hashlib
import json
from pathlib import Path

BASELINE = "51459cf203ae1eb6b586a95b21899eaa0f631823"
FORMATS = ("uimage", "fit", "intel-hex", "srec", "esp-image", "uf2", "dfuse",
           "esp-flash-image", "android-boot-image", "android-ota-payload", "ines",
           "godot-pck", "unityfs", "wxapkg")
CASE_IDS = tuple("format-" + name for name in FORMATS)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _evidence(value, tool):
    assert isinstance(value, dict) and value.get("evidence_id"), f"{tool} omitted retained Evidence"
    result = value.get("normalized_result")
    assert isinstance(result, dict), f"{tool} omitted its normalized result"
    return result


def run_firmware_format_cases(mcp, work, test):
    """Register independent callbacks with functional.py's test(name, callback)."""
    manifest = json.loads(Path(__file__).with_name("firmware-format-fixtures.json").read_text())
    assert manifest["schema_version"] == 1 and manifest["upstream_commit"] == BASELINE
    assert set(manifest["fixtures"]) == set(FORMATS)
    for format_name in FORMATS:
        def check(format_name=format_name):
            fixture = manifest["fixtures"][format_name]
            root = Path(work).resolve() / "firmware-formats" / format_name
            root.mkdir(parents=True, exist_ok=False)
            path = root / fixture["filename"]
            payload = base64.b64decode(fixture["base64"], validate=True)
            assert len(payload) == fixture["bytes"] and _digest(payload) == fixture["sha256"]
            path.write_bytes(payload)
            expected = fixture["expected_members"]
            destination = root / "extracted"
            opened = False
            try:
                mcp.call("open_binary", {"path": str(path)})
                opened = True
                inventory_evidence = mcp.call("inspect_artifact", {"detail": "complete"})
                inspection = _evidence(inventory_evidence, "inspect_artifact")
                steps = [step for step in inspection["substeps"] if step["operation"] == "inventory_artifact"]
                assert len(steps) == 1 and steps[0]["status"] == "completed", steps
                graph_evidence = steps[0]["evidence"]
                assert graph_evidence["evidence_id"] == steps[0]["evidence_id"]
                inventory = _evidence(graph_evidence, "inventory_artifact")
                assert inspection["subject"]["manifest_id"] == inventory["manifest"]["manifest_id"]
                assert inventory["manifest"]["root_format"] == format_name, inventory["manifest"]
                assert inventory["manifest"]["root_sha256"] == fixture["sha256"]
                assert inventory["integrity_contradictions"] == [], inventory["integrity_contradictions"]
                nodes = {row["artifact_id"]: row for row in inventory["nodes"]}
                occurrences = {}
                for member, wanted in expected.items():
                    matches = [row for row in inventory["occurrences"] if row["logical_path"] == member]
                    assert len(matches) == 1, {"member": member, "matches": matches}
                    row = matches[0]
                    assert row["entry_kind"] in ("file", "slice") and not row["encrypted"]
                    assert row["hash_status"] == "verified", row
                    node = nodes[row["artifact_id"]]
                    assert node["sha256"] == wanted["sha256"] and node["size"] == wanted["bytes"], node
                    occurrences[member] = row["occurrence_id"]
                # Select exactly the inventoried regular regions. This exercises
                # canonical occurrence identity and does not recurse into payloads.
                extracted_evidence = mcp.call("extract_artifact", {
                    "output_root": str(destination), "occurrence_ids": list(occurrences.values())})
                extracted = _evidence(extracted_evidence, "extract_artifact")
                assert Path(extracted["output_root"]).resolve() == destination
                assert extracted["manifest"] == inventory["manifest"]
                assert set(extracted["extraction_manifest"]["selected_occurrence_ids"]) == set(occurrences.values())
                assert extracted["containment_verified"] and extracted["cleanup"]["verified"]
                assert extracted["cleanup"]["residual_paths"] == []
                assert extracted["integrity_contradictions"] == []
                actual = {row["relative_path"]: row for row in extracted["artifacts"]}
                assert set(actual) == set(expected), {"actual": sorted(actual), "expected": sorted(expected)}
                observed = {}
                for member, wanted in expected.items():
                    output = destination / member
                    assert not output.is_symlink() and output.is_file()
                    assert output.resolve().is_relative_to(destination)
                    data = output.read_bytes()
                    assert len(data) == wanted["bytes"] and _digest(data) == wanted["sha256"]
                    row = actual[member]
                    assert row["created"] and row["bytes_written"] == len(data) and row["sha256"] == _digest(data)
                    observed[member] = {"bytes": len(data), "sha256": _digest(data)}
                assert _digest(path.read_bytes()) == fixture["sha256"], "Input was modified"
                return {"format": format_name, "fixture_sha256": fixture["sha256"],
                        "inspection_evidence_id": inventory_evidence["evidence_id"],
                        "inventory_evidence_id": graph_evidence["evidence_id"],
                        "extraction_evidence_id": extracted_evidence["evidence_id"],
                        "members": observed, "inventory_coverage": inventory["coverage"],
                        "limitations": inventory["limitations"], "scope": fixture["note"],
                        "payload_executed": False, "upstream_commit": BASELINE}
            finally:
                if opened:
                    mcp.call("close_binary")
        test("format-" + format_name, check)
