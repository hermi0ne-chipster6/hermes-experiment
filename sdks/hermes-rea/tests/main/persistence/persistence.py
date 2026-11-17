#!/usr/bin/env python3
"""Prepare durable REA evidence/snapshot, then verify them after an actual refresh.

Run both phases as the REA account with a state directory on the SDK state mount.
The caller owns Workshop refresh and must retain its change/tasks/status evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "launch"))
from functional import MCP, normalized

REPLAY_LIMITATION = "Loaded from a local REA analysis snapshot; this call did not re-run the provider."


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record_for(bundle, identity):
    records = [record for record in normalized(bundle)["records"] if record["evidence_id"] == identity]
    assert len(records) == 1, f"Expected exactly one Evidence record {identity}, got {len(records)}"
    return records[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "verify"))
    parser.add_argument("--state", type=Path, required=True, help="New dedicated persistent directory; reuse only for verify")
    parser.add_argument("--rea", default="rea", help="CLI argv parsed with shlex, without a shell")
    args = parser.parse_args()
    assert os.getuid() != 0, "Run as the unprivileged REA account"
    state = args.state.resolve()
    manifest_path = state / "manifest.json"
    if args.phase == "prepare":
        state.mkdir(parents=True, exist_ok=False)
    else:
        assert manifest_path.is_file(), "No completed prepare manifest"
    output = state / args.phase
    output.mkdir(exist_ok=False)
    binary, snapshot, bundle_path = (state / name for name in ("fixture", "snapshot.json", "evidence-bundle.json"))
    command = shlex.split(args.rea)
    records = []
    mcp = None
    opened = False
    started = time.monotonic()
    try:
        if args.phase == "verify":
            manifest = json.loads(manifest_path.read_text())
            assert manifest["uid"] == os.getuid(), "State ownership account changed"
            assert not Path(manifest["ephemeral_marker"]).exists(), "Refresh witness still exists: an actual filesystem refresh must separate phases"
            for name, sha256 in manifest["files"].items():
                path = state / name
                assert path.is_file() and path.stat().st_uid == os.getuid(), f"Durable file ownership changed: {name}"
                assert digest(path) == sha256, f"Durable file changed across refresh: {name}"
        mcp = MCP(command + ["mcp"], output)
        initialized = mcp.request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "hermes-sdk-persistence", "version": "1"}})
        mcp.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        (output / "initialize.json").write_text(json.dumps(initialized, indent=2))
        initial = normalized(mcp.call("binary_session"))
        assert initial["open"] is False, "New MCP process unexpectedly owns an open binary"
        if args.phase == "prepare":
            source = state / "fixture.c"
            source.write_text("int sdk_persist_add(int x,int y){return x+y;} int main(void){return sdk_persist_add(2,3)==5?0:1;}\n")
            compiled = subprocess.run(["gcc", "-g", "-O0", "-o", str(binary), str(source)], capture_output=True, text=True, timeout=60)
            assert compiled.returncode == 0, compiled.stderr
            mcp.call("open_binary", {"path": str(binary), "provider_id": "ghidra"}, timeout=900)
            opened = True
            session = normalized(mcp.call("binary_session"))
            assert session["analysis_provider_binding"]["provider"]["id"] == "ghidra"
            assert session["analysis_provider_binding"]["selection_source"] == "request"
            documents = normalized(mcp.call("list_documents"))
            assert isinstance(documents, list) and len(documents) == 1 and isinstance(documents[0], str), documents
            query = {"procedure": "sdk_persist_add", "document": documents[0]}
            pseudo = mcp.call("procedure_pseudo_code", query, timeout=300)
            assert isinstance(normalized(pseudo), str) and "+" in normalized(pseudo), pseudo
            assembly = normalized(mcp.call("procedure_assembly", query, timeout=300))
            assert isinstance(assembly, str) and ": ADD " in assembly and ": RET" in assembly, assembly
            identity = pseudo["evidence_id"]
            mcp.call("export_evidence_bundle", {"path": str(bundle_path)})
            bundle = json.loads(bundle_path.read_text())
            retained = record_for(bundle, identity)
            assert retained["normalized_result"] == normalized(pseudo)
            mcp.call("close_binary", {"snapshot_path": str(snapshot)}, timeout=300)
            opened = False
            saved = json.loads(snapshot.read_text())
            assert saved["target"]["identity"]["sha256"] == digest(binary)
            assert saved["binding"]["provider"]["id"] == "ghidra"
            assert saved["entries"], "Snapshot contains no replayable queries"
            assert record_for(saved["evidence_bundle"], identity)["normalized_result"] == normalized(pseudo)
            descriptor, marker_name = tempfile.mkstemp(prefix="hermes-rea-refresh-witness-", dir="/var/tmp")
            os.close(descriptor)
            manifest = {"uid": os.getuid(), "ephemeral_marker": marker_name, "evidence_id": identity,
                        "normalized_pseudocode": normalized(pseudo), "normalized_assembly": assembly, "query": query,
                        "files": {path.name: digest(path) for path in (source, binary, snapshot, bundle_path)}}
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            detail = {"evidence_id": identity, "snapshot_entries": len(saved["entries"]),
                      "durable_files_sha256": manifest["files"], "refresh_required": True}
        else:
            original = json.loads(bundle_path.read_text())
            mcp.call("import_evidence_bundle", {"path": str(bundle_path)})
            imported = mcp.call("get_evidence_bundle")
            actual = record_for(imported, manifest["evidence_id"])
            assert actual["normalized_result"] == record_for(original, manifest["evidence_id"])["normalized_result"]
            assert actual["normalized_result"] == manifest["normalized_pseudocode"]
            # Clear imported observations so the next check proves snapshot restoration independently.
            mcp.call("reset_investigation")
            mcp.call("open_binary", {"path": str(binary), "provider_id": "ghidra", "snapshot_path": str(snapshot)}, timeout=900)
            opened = True
            session = normalized(mcp.call("binary_session"))
            assert session["open"] is True
            assert session["analysis_provider_binding"]["provider"]["id"] == "ghidra"
            pseudo = mcp.call("procedure_pseudo_code", manifest["query"], timeout=300)
            assert normalized(pseudo) == manifest["normalized_pseudocode"], "Snapshot pseudocode semantics changed"
            assert REPLAY_LIMITATION in pseudo["limitations"], "Query was recomputed rather than replayed from the saved snapshot"
            assembly = mcp.call("procedure_assembly", manifest["query"], timeout=300)
            assert normalized(assembly) == manifest["normalized_assembly"], "Snapshot assembly semantics changed"
            assert REPLAY_LIMITATION in assembly["limitations"], "Assembly was not replayed from snapshot"
            mcp.call("close_binary", timeout=300)
            opened = False
            assert normalized(mcp.call("binary_session"))["open"] is False
            for name, sha256 in manifest["files"].items():
                assert digest(state / name) == sha256, f"Verification modified durable input {name}"
            detail = {"evidence_id": manifest["evidence_id"], "durable_hashes_and_ownership_preserved": True,
                      "ephemeral_witness_removed": True, "imported_evidence_semantics_match": True,
                      "snapshot_pseudocode_and_assembly_replayed": True, "closed_session": True}
        records.append({"test": "persistence-" + args.phase, "status": "pass", "detail": detail})
    except Exception as error:
        records.append({"test": "persistence-" + args.phase, "status": "fail", "reason": f"{type(error).__name__}: {error}"})
    finally:
        if mcp:
            try:
                if opened:
                    mcp.call("close_binary", timeout=300)
            finally:
                mcp.close()
        records[-1]["duration_seconds"] = round(time.monotonic() - started, 3)
        (output / "results.json").write_text(json.dumps(records, indent=2) + "\n")
        print(json.dumps(records[-1]), flush=True)
    raise SystemExit(0 if records[-1]["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
