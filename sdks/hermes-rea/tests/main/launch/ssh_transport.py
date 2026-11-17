#!/usr/bin/env python3
"""Real SSH transport checks against the caller-selected disposable C worker.

The caller supplies an ephemeral development key and already-pinned host keys.
This never reads/prints key bytes or changes SSH trust/configuration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from functional import MCP, normalized


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--key", required=True, type=Path)
    parser.add_argument("--known-hosts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-inventory", type=Path, help="Retained installed full tools-list.json for independent name equality")
    parser.add_argument("--ghidra", action="store_true", help="Also decompile the transferred fixture with explicit Ghidra")
    args = parser.parse_args()
    assert args.key.is_file() and args.known_hosts.is_file(), "Caller-supplied key and pinned known-hosts files must exist"
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    ssh = ["ssh", "-F", "/dev/null", "-T", "-p", str(args.port), "-i", str(args.key.resolve()),
           "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes",
           "-o", "IdentityAgent=none", "-o", "UpdateHostKeys=no",
           "-o", f"UserKnownHostsFile={args.known_hosts.resolve()}", "-o", "GlobalKnownHostsFile=/dev/null",
           "-o", "PasswordAuthentication=no", "-o", "KbdInteractiveAuthentication=no",
           "-o", "ConnectTimeout=10", "-o", "ConnectionAttempts=1", "-o", "LogLevel=ERROR"]
    destination = "rea@" + args.host
    records = []
    mcp = None
    receipt = None

    def check(name, callback):
        began = time.monotonic()
        try:
            detail = callback()
            record = {"test": name, "status": "pass", "detail": detail}
        except Exception as error:
            record = {"test": name, "status": "fail", "reason": str(error)}
        record["duration_seconds"] = round(time.monotonic() - began, 3)
        records.append(record)
        (output / "results.json").write_text(json.dumps(records, indent=2) + "\n")
        print(json.dumps(record), flush=True)

    def authenticated_mcp():
        nonlocal mcp
        mcp = MCP([*ssh, destination, "rea-mcp"], output, profile=None)
        initialized = mcp.request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                  "clientInfo": {"name": "hermes-sdk-real-ssh-test", "version": "1"}})
        mcp.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        inventory, cursor = [], None
        while True:
            page = mcp.request("tools/list", {"cursor": cursor} if cursor else {})
            inventory.extend(page["tools"])
            cursor = page.get("nextCursor")
            if not cursor:
                break
        names = {entry["name"] for entry in inventory}
        assert "binary_session" in names, "Restricted remote MCP does not advertise binary_session"
        state = normalized(mcp.call("binary_session"))
        full = {name for group in state["tool_availability"]["groups"] for name in group["names"]}
        assert len(names) == len(inventory), "Duplicate advertised tool names"
        assert names - {"discover_tools"} <= full
        assert len(full) == 259, f"Pinned REA 6.9.0 inventory changed: {len(full)}"
        if args.expected_inventory:
            expected = {entry["name"] for entry in json.loads(args.expected_inventory.read_text())}
            assert full == expected, f"Inventory mismatch: missing={sorted(expected-full)}, extra={sorted(full-expected)}"
        if "discover_tools" in names:
            missing = sorted(full - names)
            for offset in range(0, len(missing), 20):
                mcp.call("discover_tools", {"names": missing[offset:offset + 20]})
        expanded, cursor = [], None
        while True:
            page = mcp.request("tools/list", {"cursor": cursor} if cursor else {})
            expanded.extend(page["tools"])
            cursor = page.get("nextCursor")
            if not cursor:
                break
        expanded_names = {entry["name"] for entry in expanded}
        assert len(expanded_names) == len(expanded), "Duplicate expanded tool names"
        assert expanded_names - {"discover_tools"} == full, "Discovery did not expose the exact canonical inventory"
        (output / "tools-list-expanded.json").write_text(json.dumps(expanded, indent=2))
        assert "inspect_with_objdump" in full, "Remote canonical inventory lacks the native command"
        if "inspect_with_objdump" not in names:
            mcp.call("discover_tools", {"names": ["inspect_with_objdump"]})
        (output / "initialize.json").write_text(json.dumps(initialized, indent=2))
        (output / "tools-list.json").write_text(json.dumps(inventory, indent=2))
        return {"host": args.host, "port": args.port, "user": "rea", "host_key_policy": "strict caller-pinned known-hosts",
                "authentication": "caller-supplied ephemeral key only", "server": initialized["serverInfo"],
                "advertised_tools": len(names), "full_inventory_tools": len(full), "binary_session_operational": True,
                "expanded_inventory_exact": True, "independent_inventory_compared": args.expected_inventory is not None}

    def bounded_artifact():
        nonlocal receipt
        compiler = shutil.which("gcc")
        assert compiler, "Host gcc is required to produce the owned ELF fixture"
        source, binary = output / "ssh-fixture.c", output / "ssh-fixture"
        source.write_text("int sdk_ssh_add(int x,int y){return x+y;} int main(void){return sdk_ssh_add(2,3)==5?0:1;}\n")
        subprocess.run([compiler, "-g", "-O0", "-o", str(binary), str(source)], check=True, capture_output=True, timeout=60)
        payload = binary.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        response = subprocess.run([*ssh, destination, f"artifact-put {digest} {len(payload)}"], input=payload,
                                  capture_output=True, timeout=60)
        (output / "artifact-transfer.stderr").write_bytes(response.stderr)
        assert response.returncode == 0, f"Artifact upload failed ({response.returncode}): {response.stderr.decode(errors='replace')}"
        receipt = json.loads(response.stdout)
        expected = {"protocol": "artifact-v1", "sha256": digest, "size": len(payload),
                    "path": f"/var/lib/hermes-rea/inbox/{digest}.bin"}
        assert receipt == expected, receipt
        (output / "artifact-receipt.json").write_text(json.dumps(receipt, indent=2))
        return receipt

    def native_operation():
        assert mcp and receipt, "Authenticated MCP and bounded upload must succeed first"
        result = normalized(mcp.call("inspect_with_objdump", {"path": receipt["path"], "operation": "disassemble", "symbol": "sdk_ssh_add"}))
        assert result["exit_code"] == 0 and result["completion_status"] == "complete", result
        assert "<sdk_ssh_add>" in result["stdout"] and "\tadd" in result["stdout"] and "\tret" in result["stdout"], result
        assert result["artifact_sha256_after"] == receipt["sha256"] and not result["artifact_changed"], result
        return {"assertion": "Remote native analysis disassembled actual add/ret instructions from the checksum-verified transferred ELF",
                "artifact_sha256": receipt["sha256"], "transport": "native MCP over authenticated restricted SSH"}

    def ghidra_operation():
        assert mcp and receipt
        mcp.call("open_binary", {"path": receipt["path"], "provider_id": "ghidra"}, timeout=900)
        try:
            state = normalized(mcp.call("binary_session"))
            binding = state["analysis_provider_binding"]
            assert binding["provider"]["id"] == "ghidra" and binding["selection_source"] == "request", binding
            result = normalized(mcp.call("procedure_pseudo_code", {"procedure": "sdk_ssh_add"}, timeout=300))
            assert "+" in json.dumps(result), result
        finally:
            mcp.call("close_binary", timeout=300)
        return "Explicit remote Ghidra decompiled the transferred owned addition function"

    def shell_denied():
        response = subprocess.run([*ssh, destination, "/bin/sh -c id"], capture_output=True, timeout=30)
        (output / "denied-shell.stderr").write_bytes(response.stderr)
        assert response.returncode == 64, f"Expected forced-command refusal 64, got {response.returncode}: {response.stderr.decode(errors='replace')}"
        assert not response.stdout, "Denied shell unexpectedly returned output"
        return {"exit_code": response.returncode, "arbitrary_shell_denied_after_authentication": True}

    def forwarding_denied():
        try:
            response = subprocess.run([*ssh, "-N", "-o", "ExitOnForwardFailure=yes", "-R", "127.0.0.1:0:127.0.0.1:9", destination],
                                      capture_output=True, timeout=15)
        except subprocess.TimeoutExpired as error:
            raise AssertionError("SSH did not refuse remote forwarding within 15 seconds; owned client was terminated") from error
        (output / "denied-forwarding.stderr").write_bytes(response.stderr)
        diagnostic = response.stderr.decode(errors="replace")
        assert response.returncode != 0 and "remote port forwarding failed" in diagnostic.lower(), diagnostic
        return {"exit_code": response.returncode, "loopback_remote_forwarding_refused": True}

    try:
        check("ssh-authenticated-mcp", authenticated_mcp)
        check("ssh-bounded-artifact", bounded_artifact)
        check("ssh-native-operation", native_operation)
        if args.ghidra:
            check("ssh-ghidra-operation", ghidra_operation)
        check("ssh-shell-denied", shell_denied)
        check("ssh-forwarding-denied", forwarding_denied)
    finally:
        if mcp:
            mcp.close()
    raise SystemExit(1 if any(row["status"] != "pass" for row in records) else 0)


if __name__ == "__main__":
    main()
