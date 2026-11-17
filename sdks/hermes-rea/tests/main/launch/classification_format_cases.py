"""Real artifact directory inventory and native legacy/raw load-image checks.

Registration alone is not acceptance. The parent runner supplies its actual MCP
client and test recorder; this module neither provisions engines nor starts a
replacement server. Targets are inert and never executed.
"""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from functional import normalized

CLASSIFICATION_FORMAT_CASE_IDS = (
    "artifact-directory-classification", "native-load-mz", "native-load-com",
    "native-load-raw", "native-load-dol",
)


def fixture_records():
    document = json.loads(Path(__file__).with_name("classification-format-fixtures.json").read_text())
    assert document["schema_version"] == 1
    assert document["upstream_baseline"] == "51459cf203ae1eb6b586a95b21899eaa0f631823"
    fixtures = {}
    for name, record in document["fixtures"].items():
        assert Path(name).name == name and name not in {".", ".."}
        data = base64.b64decode(record["base64"], validate=True)
        assert len(data) == record["bytes"]
        assert hashlib.sha256(data).hexdigest() == record["sha256"]
        fixtures[name] = (record, data)
    return fixtures


def inventory_result(value):
    inspection = normalized(value)
    steps = [step for step in inspection["substeps"] if step["operation"] == "inventory_artifact"]
    assert len(steps) == 1 and steps[0]["status"] == "completed", inspection
    return normalized(steps[0]["evidence"])


def run_classification_format_cases(mcp, work, test, package_root=None, node=None):
    """Register five independent cases; each closes its owned target."""
    work = Path(work)

    def directory_case():
        root = Path(tempfile.mkdtemp(prefix="format-directory-", dir=work)) / "Fixture.app"
        resources = root / "Contents/Resources"
        resources.mkdir(parents=True)
        (root / "Contents/Info.plist").write_text(
            '<?xml version="1.0"?><plist version="1.0"><dict>'
            '<key>CFBundleIdentifier</key><string>test.hermes.formats</string>'
            '</dict></plist>'
        )
        fixtures = fixture_records()
        for name, (_record, data) in fixtures.items():
            (resources / name).write_bytes(data)
        package = Path(package_root or "/var/lib/workshop/sdk/hermes-rea/rea/node_modules/rea-agents").resolve()
        inventory_module = package / "dist/artifacts/inventory/ArtifactInventory.js"
        resources_module = package / "dist/resources/index.js"
        assert inventory_module.is_file() and resources_module.is_file(), package
        sdk_node = package.parents[2] / "node/bin/node"
        executable = node or (str(sdk_node) if sdk_node.is_file() else shutil.which("node"))
        assert executable, "The packaged inventory proof requires Node"
        script = (
            "const {inventoryArtifact}=await import(process.argv[1]);"
            "const {ArtifactResourceScope}=await import(process.argv[2]);"
            "const scope=new ArtifactResourceScope();"
            "try{const result=await inventoryArtifact(process.argv[3],"
            "{resourceScope:scope,environment:process.env,integrity:'fail'});"
            "process.stdout.write(JSON.stringify(result));}finally{await scope.close();}"
        )
        observed = subprocess.run([executable, "--input-type=module", "-e", script,
                                   inventory_module.as_uri(), resources_module.as_uri(), str(root)],
                                  capture_output=True, text=True, timeout=180)
        (root.parent / "directory-inventory.stdout.json").write_text(observed.stdout)
        (root.parent / "directory-inventory.stderr.log").write_text(observed.stderr)
        assert observed.returncode == 0, observed.stderr
        directory = json.loads(observed.stdout)
        assert directory["manifest"]["root_format"] == "directory", directory["manifest"]
        # This public session deliberately exposes resource operations only.
        # Verify the refusal rather than pretending it admits native inventory.
        mcp.call("open_bundle_resources", {"path": str(root)})
        try:
            refused = mcp.request("tools/call", {"name": "inspect_artifact", "arguments": {}})
            (root.parent / "resource-only-inventory-refusal.json").write_text(json.dumps(refused, indent=2))
            assert refused.get("isError") is True, refused
            text = "\n".join(row["text"] for row in refused.get("content", []) if row.get("type") == "text")
            error = json.loads(text)["error"]
            assert error["code"] == "capability_unavailable", error
            assert error["details"]["provider_id"] == "bundle-resources", error
            assert "only app resource access" in error["details"]["reason"], error
        finally:
            mcp.call("close_binary")
        archive = root.parent / "classification.zip"
        with zipfile.ZipFile(archive, "x") as output:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    output.write(path, path.relative_to(root).as_posix())
        mcp.call("open_binary", {"path": str(archive)})
        try:
            zipped = inventory_result(mcp.call("inspect_artifact", {"detail": "complete"}))
            assert zipped["manifest"]["root_format"] == "zip", zipped["manifest"]
        finally:
            mcp.call("close_binary")
        reports = {}
        for source, result in [("installed-directory-reader", directory), ("mcp-zip-inventory", zipped)]:
            nodes = {node["artifact_id"]: node for node in result["nodes"]}
            occurrences = {row["logical_path"]: row for row in result["occurrences"]}
            if source == "installed-directory-reader":
                assert {".", "Contents", "Contents/Resources"}.issubset(
                    path for path, row in occurrences.items() if row["entry_kind"] == "directory")
            observed = {}
            for name, (record, data) in fixtures.items():
                row = occurrences["Contents/Resources/" + name]
                assert row["artifact_format"] == record["inventory_format"], row
                assert row["hash_status"] == "verified", row
                artifact_node = nodes[row["artifact_id"]]
                assert artifact_node["sha256"] == record["sha256"], artifact_node
                assert (resources / name).read_bytes() == data
                observed[name] = {"format": row["artifact_format"], "sha256": artifact_node["sha256"]}
            reports[source] = observed
        return {"members_by_interface": reports, "resource_only_inventory_refusal": error["code"],
                "scope": "Real installed directory-reader API and MCP ZIP inventory verify exact member identities; resource-only MCP refuses inspect_artifact. Native headers are classification only; no Hopper database validation"}

    def native_case(name, expected_format):
        record, data = fixture_records()[name]
        root = Path(tempfile.mkdtemp(prefix="native-load-", dir=work))
        path = root / name
        path.write_bytes(data)
        selection = {"path": str(path), "provider_id": "ghidra", **record["selection"]}
        mcp.call("open_binary", selection, timeout=900)
        try:
            session = normalized(mcp.call("binary_session"))
            binding = session["analysis_provider_binding"]
            assert binding["provider"]["id"] == "ghidra" and binding["selection_source"] == "request", binding
            result = normalized(mcp.call("inspect_native_load_image", {"detail": "complete"}, timeout=300))
            assert result["status"] == "verified" and result["format"] == expected_format, result
            assert result["target_sha256"] == record["sha256"], result
            assert result["checks"] and all(row["matched"] for row in result["checks"]), result["checks"]
            observation = result["observations"]
            assert any(row["original_sha256"] == record["sha256"] and row["size"] == len(data)
                       for row in observation["source_files"]), observation
            assert any(row["loaded"] and row["initialized"] and row["sha256"]
                       for row in observation["mappings"]), observation
            entry = result["entry"].get("address", result["entry"].get("linear_address"))
            assert entry, result
            instruction = normalized(mcp.call("inspect_native_instruction", {"address": entry}))
            assert instruction["status"] == "decoded", instruction
            assert instruction["mnemonic"].upper() == record["expected_instruction"], instruction
            assert "".join(instruction["bytes"].split()).lower() == record["expected_instruction_hex"], instruction
            if expected_format == "dos-com":
                assert result["header_bytes"] == 0 and result["module_bytes"] == len(data)
                assert observation["entry_context"], observation
            if expected_format == "raw-binary":
                assert result["architecture"] == "x86_64" and result["file_bytes"] == len(data)
                assert int(result["entry"]["address"].split(":")[-1], 16) == 0x400000
            if expected_format == "gamecube-dol":
                assert result["architecture"] == "powerpc", result
                assert {row["kind"] for row in result["sections"]} == {"text", "data"}, result
                assert int(result["bss"]["size"].split(":")[-1], 16) == 32, result
            assert path.read_bytes() == data, "Static analysis changed the owned input"
            return {"format": expected_format, "provider": "ghidra", "sha256": record["sha256"],
                    "verification": result["status"], "matched_checks": len(result["checks"]),
                    "entry": entry, "instruction": instruction["mnemonic"],
                    "instruction_bytes": instruction["bytes"],
                    "scope": "Actual static import, independent source/load verification and listed instruction; no target execution or complete decompiler qualification"}
        finally:
            mcp.call("close_binary", timeout=300)

    test("artifact-directory-classification", directory_case)
    for identifier, name, expected in [
        ("native-load-mz", "legacy.exe", "dos-mz"),
        ("native-load-com", "legacy.com", "dos-com"),
        ("native-load-raw", "raw.bin", "raw-binary"),
        ("native-load-dol", "fixture.dol", "gamecube-dol"),
    ]:
        test(identifier, lambda name=name, expected=expected: native_case(name, expected))
