"""Real public MCP inventory/extraction of inert packaged executable formats.

Fixtures are never executed. Generated carrier bytes originate from the exact
pinned upstream fixture factories; ZIP fixtures use Python's standard writer.
"""
import base64
import hashlib
import json
from pathlib import Path
import plistlib
import zipfile


CONTAINER_FORMAT_CASES = (
    "container-asar", "container-dotnet-bundle", "container-bun-standalone",
    "container-deno-standalone", "container-node-sea", "container-pyinstaller",
    "container-msix", "container-appx", "container-hsp", "container-app-pack",
    "container-plist-resources",
)


def run_container_format_cases(mcp, work, test):
    """Register independent cases through the parent runner's test callback."""
    work = Path(work)
    fixture_file = Path(__file__).with_name("container-format-fixtures.json")

    def evidence(name, arguments=None):
        result = mcp.call(name, arguments or {})
        assert result.get("evidence_id"), f"{name} did not retain Evidence"
        return result["normalized_result"]

    def verify(name, path, expected_format, members, member_formats=None):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        opened = False
        try:
            mcp.call("open_binary", {"path": str(path)})
            opened = True
            inspection = evidence("inspect_artifact")
            inventories = [step["evidence"]["normalized_result"] for step in inspection["substeps"]
                           if step["operation"] == "inventory_artifact"]
            assert len(inventories) == 1, "Expected one retained inventory graph"
            graph = inventories[0]
            assert graph["manifest"]["root_format"] == expected_format, graph["manifest"]
            nodes = {row["artifact_id"]: row for row in graph["nodes"]}
            ids = []
            for logical, data in members.items():
                matches = [row for row in graph["occurrences"] if row["logical_path"] == logical]
                assert len(matches) == 1, f"Missing or ambiguous member {logical}"
                row = matches[0]
                assert nodes[row["artifact_id"]]["sha256"] == hashlib.sha256(data).hexdigest(), logical
                if member_formats and logical in member_formats:
                    assert row["artifact_format"] == member_formats[logical], row
                ids.append(row["occurrence_id"])
            destination = work / (name + "-extracted")
            assert not destination.exists()
            extracted = evidence("extract_artifact", {"output_root": str(destination), "occurrence_ids": ids})
            assert extracted["containment_verified"] is True
            assert Path(extracted["output_root"]).resolve() == destination.resolve()
            for logical, data in members.items():
                extracted_path = destination / logical
                assert extracted_path.resolve().is_relative_to(destination.resolve())
                assert extracted_path.is_file() and not extracted_path.is_symlink()
                assert extracted_path.read_bytes() == data, logical
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, "Reader mutated input"
            return {"root_format": expected_format, "input_sha256": digest,
                    "verified_members": {logical: hashlib.sha256(data).hexdigest() for logical, data in members.items()},
                    "selected_extraction": len(ids), "containment_verified": True,
                    "input_unchanged": True, "payload_execution": False,
                    "scope": "Artifact format recognition, retained member hashes and exact-byte extraction; no application execution"}
        finally:
            if opened:
                mcp.call("close_binary")

    def generated(name):
        fixture = json.loads(fixture_file.read_text())
        assert fixture["provenance"]["commit"] == "51459cf203ae1eb6b586a95b21899eaa0f631823"
        row = fixture["fixtures"][name]
        data = base64.b64decode(row["bytes_base64"], validate=True)
        assert hashlib.sha256(data).hexdigest() == row["sha256"]
        suffix = ".asar" if name == "asar" else ".exe" if name == "dotnet-bundle" else ".bin"
        path = work / ("container-" + name + suffix)
        path.write_bytes(data)
        members = {logical: base64.b64decode(value, validate=True) for logical, value in row["members"].items()}
        return verify("container-" + name, path, row["format"], members)

    def zip_case(name):
        members = {"data/marker.txt": b"hermes-container-zip-fixture\n"}
        formats = None
        expected_format = name
        if name in ("msix", "appx"):
            members["AppxManifest.xml"] = b'<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"><Identity Name="HermesFixture" Publisher="CN=Fixture" Version="1.0.0.0" /></Package>'
        elif name == "hsp":
            members["module.json"] = b'{"app":{"bundleName":"org.hermes.fixture"},"module":{"name":"fixture","type":"shared"}}'
        elif name == "app-pack":
            members["pack.info"] = b'{"summary":{"app":{"bundleName":"org.hermes.fixture"},"modules":[]},"packages":[]}'
        else:
            assert name == "plist-resources"
            expected_format = "zip"
            members["Info.plist"] = plistlib.dumps({"CFBundleIdentifier": "org.hermes.fixture", "HermesValue": 37}, fmt=plistlib.FMT_BINARY)
            members["fixture.entitlements"] = plistlib.dumps({"com.apple.security.app-sandbox": True}, fmt=plistlib.FMT_XML)
            formats = {"Info.plist": "plist", "fixture.entitlements": "entitlements"}
        suffix = {"app-pack": "app", "plist-resources": "zip"}.get(name, name)
        path = work / ("container-" + name + "." + suffix)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for logical, data in sorted(members.items()):
                info = zipfile.ZipInfo(logical, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
        result = verify("container-" + name, path, expected_format, members, formats)
        if name == "plist-resources":
            result["scope"] = "Binary plist and XML entitlement classification and byte-preserving ZIP extraction; no native plist semantic decoding or signature validation"
        else:
            result["scope"] = "Verified ZIP container recognized by package suffix, member hashes and exact extraction; no OS installation, manifest certification or signature trust claim"
        return result

    for name in ("asar", "dotnet-bundle", "bun-standalone", "deno-standalone", "node-sea", "pyinstaller"):
        test("container-" + name, lambda name=name: generated(name))
    for name in ("msix", "appx", "hsp", "app-pack", "plist-resources"):
        test("container-" + name, lambda name=name: zip_case(name))
