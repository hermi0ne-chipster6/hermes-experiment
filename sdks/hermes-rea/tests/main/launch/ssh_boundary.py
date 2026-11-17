#!/usr/bin/env python3
"""Exercise the installed forced-command boundary as the unprivileged REA user.

This checks the executable selected by sshd; it does not claim network/key
authentication coverage. All inputs are local synthetic commands and bytes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

from functional import MCP, normalized


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--wrapper", default="/usr/local/bin/hermes-rea-stdio")
    parser.add_argument("--authorized-keys-source", type=Path,
                        help="Require this public allowlist to be on a read-only mount; inspect metadata only")
    parser.add_argument("--authorized-keys-installed", type=Path, default=Path("/etc/ssh/hermes-rea/authorized_keys"))
    args = parser.parse_args()
    assert os.getuid() != 0, "Run as the same unprivileged REA account used by sshd"
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []

    def invoke(command, body=b"", arguments=()):
        response = subprocess.run([args.wrapper, *arguments], input=body, capture_output=True,
                                  env=dict(os.environ, SSH_ORIGINAL_COMMAND=command), timeout=30)
        return response

    def check(name, callback):
        try:
            detail = callback()
            results.append({"test": name, "status": "pass", "detail": detail})
        except Exception as error:
            results.append({"test": name, "status": "fail", "reason": str(error)})
        (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps(results[-1]), flush=True)

    def version():
        response = invoke("", arguments=("--version",))
        assert response.returncode == 0 and response.stdout.strip(), response.stderr.decode(errors="replace")
        return response.stdout.decode().strip()

    def native_mcp():
        mcp = MCP(["env", "SSH_ORIGINAL_COMMAND=rea-mcp", args.wrapper], output, profile=None)
        try:
            initialized = mcp.request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                      "clientInfo": {"name": "hermes-sdk-forced-command-test", "version": "1"}})
            mcp.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            tools = mcp.request("tools/list", {})["tools"]
            assert "binary_session" in {entry["name"] for entry in tools}
            session = normalized(mcp.call("binary_session"))
            assert isinstance(session, dict) and session, session
            available = {name for group in session["tool_availability"]["groups"] for name in group["names"]}
            advertised = {entry["name"] for entry in tools}
            assert advertised - {"discover_tools"} <= available, "Default catalog advertises names outside binary_session inventory"
            discovered = False
            if "discover_tools" in advertised:
                mcp.call("discover_tools", {"names": ["inspect_sqlite_database"]})
                expanded = {entry["name"] for entry in mcp.request("tools/list", {})["tools"]}
                assert "inspect_sqlite_database" in expanded, "Deferred discovery did not expose the selected contract"
                discovered = True
            (output / "tools-list.json").write_text(json.dumps(tools, indent=2))
            return {"server": initialized["serverInfo"], "default_advertised_tool_count": len(tools),
                    "binary_session_full_inventory_count": len(available), "binary_session_call": True,
                    "default_inventory_is_subset_excluding_discovery_control": True,
                    "deferred_tool_discovery_verified": discovered}
        finally:
            mcp.close()

    def rejects_commands():
        marker = output / "must-not-execute"
        commands = ["/bin/sh", "bash -lc id", "rea-mcp; touch " + str(marker),
                    "rea-mcp\ntouch " + str(marker), "artifact-put ../../escape 4",
                    "artifact-put " + "f" * 64 + " 4; id", "artifact-put " + "f" * 64 + " -1"]
        codes = []
        for command in commands:
            response = invoke(command)
            assert response.returncode == 64, (command, response.returncode, response.stderr.decode(errors="replace"))
            codes.append(response.returncode)
        assert not marker.exists(), "A refused command executed"
        extra = invoke("", arguments=("-c", "id"))
        assert extra.returncode == 64, extra.stderr
        return {"rejected_commands": len(commands), "exit_codes": codes, "extra_local_arguments_rejected": True}

    def bounded_artifact():
        body = b"hermes-sdk-owned-artifact-boundary-fixture\n"
        digest = hashlib.sha256(body).hexdigest()
        command = f"artifact-put {digest} {len(body)}"
        response = invoke(command, body)
        assert response.returncode == 0, response.stderr.decode(errors="replace")
        receipt = json.loads(response.stdout)
        path = Path("/var/lib/hermes-rea/inbox") / (digest + ".bin")
        assert receipt == {"protocol": "artifact-v1", "sha256": digest, "size": len(body), "path": str(path)}, receipt
        assert path.read_bytes() == body and stat.S_IMODE(path.stat().st_mode) == 0o400
        duplicate = invoke(command, body)
        assert duplicate.returncode == 0 and json.loads(duplicate.stdout) == receipt, duplicate.stderr
        for bad_command, bad_body in [(command, body[:-1]), (command, body + b"x"),
                                      (f"artifact-put {'0' * 64} {len(body)}", body),
                                      (f"artifact-put {digest} {32 * 1024 * 1024 + 1}", b"")]:
            refused = invoke(bad_command, bad_body)
            assert refused.returncode != 0, "Malformed artifact accepted"
        assert path.read_bytes() == body, "An invalid retry overwrote a verified artifact"
        return {"digest": digest, "bytes": len(body), "mode": "0400", "idempotent_duplicate": True,
                "rejected": ["truncated", "overlong", "digest-mismatch", "over-32-MiB"]}

    def readonly_key_boundary():
        source = args.authorized_keys_source
        installed = args.authorized_keys_installed
        assert source.is_file() and installed.is_file(), "Configured public allowlist paths must exist"
        mount = subprocess.run(["findmnt", "--noheadings", "--output", "OPTIONS", "--target", str(source)],
                               check=True, capture_output=True, text=True, timeout=10)
        assert "ro" in mount.stdout.strip().split(","), "Public allowlist source is not mounted read-only"
        metadata = installed.stat()
        assert metadata.st_uid == 0, "Installed allowlist must be root-owned"
        assert stat.S_IMODE(metadata.st_mode) & 0o022 == 0, "Installed allowlist is group/world writable"
        for path in (source, source.parent, installed, installed.parent):
            assert not os.access(path, os.W_OK), f"REA can modify public allowlist path or parent: {path}"
        return {"source_readonly_mount": True, "installed_owner_uid": metadata.st_uid,
                "installed_mode": oct(stat.S_IMODE(metadata.st_mode)), "rea_write_access": False,
                "key_contents_read_or_logged": False}

    def no_sudo():
        response = subprocess.run(["sudo", "-n", "true"], capture_output=True, timeout=10)
        assert response.returncode != 0, "REA worker unexpectedly has noninteractive root sudo access"
        policy = subprocess.run(["sudo", "-n", "-l"], capture_output=True, timeout=10)
        assert policy.returncode != 0, "REA worker unexpectedly has an available sudo policy listing"
        return {"uid": os.getuid(), "sudo_root_command_denied": True, "exit_code": response.returncode,
                "sudo_policy_listing_denied": True, "policy_exit_code": policy.returncode}

    check("forced-command-version", version)
    check("forced-command-mcp", native_mcp)
    check("forced-command-rejections", rejects_commands)
    check("forced-command-artifact", bounded_artifact)
    check("worker-no-sudo", no_sudo)
    if args.authorized_keys_source:
        check("readonly-key-boundary", readonly_key_boundary)
    raise SystemExit(1 if any(row["status"] != "pass" for row in results) else 0)


if __name__ == "__main__":
    main()
