#!/usr/bin/env python3
"""Real CLI/MCP integration checks using disposable, locally generated inputs.

Run as the same unprivileged user that runs REA. Results retain the raw JSON
responses; availability is never counted as an operational provider pass.
"""
import argparse
import gzip
import hashlib
import http.client
import json
import os
import pty
from pathlib import Path
import selectors
import shlex
import shutil
import signal
import socket
import sqlite3
import subprocess
import tempfile
import time
import urllib.request
import zipfile


class Unavailable(Exception):
    pass


def require_program(name):
    path = shutil.which(name)
    if not path:
        raise Unavailable(f"Missing fixture prerequisite: {name}")
    return path


def run(argv, **kwargs):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=180, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{argv[0]} exited {result.returncode}: {result.stderr[-2000:]}")
    return result.stdout


def flatten(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def contains(value, marker):
    # Do not accidentally match a request echoed in Evidence.parameters.
    assert marker in flatten(normalized(value)), f"Expected fixture marker {marker!r} in produced result"


def normalized(value):
    return value.get("normalized_result", value.get("result", value)) if isinstance(value, dict) else value


class MCP:
    def __init__(self, command, output, profile="full"):
        self.output = output
        self.errors = (output / "mcp-stderr.log").open("wb")
        env = dict(os.environ)
        if profile is None:
            env.pop("REA_MCP_TOOL_CATALOG_PROFILE", None)
        else:
            env["REA_MCP_TOOL_CATALOG_PROFILE"] = profile
        env.pop("REA_MCP_TOOL_FAMILIES", None)
        self.child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=self.errors, env=env)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.child.stdout, selectors.EVENT_READ)
        self.pending = b""
        self.counter = 0
        self.serial = 0

    def request(self, method, params, timeout=180):
        self.counter += 1
        request_id = self.counter
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            while b"\n" in self.pending:
                line, self.pending = self.pending.split(b"\n", 1)
                if not line:
                    continue
                response = json.loads(line)
                if response.get("id") == request_id:
                    if "error" in response:
                        raise RuntimeError(flatten(response["error"]))
                    return response["result"]
            if not self.selector.select(min(1, max(0, deadline - time.monotonic()))):
                continue
            data = os.read(self.child.stdout.fileno(), 1024 * 1024)
            if not data:
                raise RuntimeError(f"MCP closed stdout (exit {self.child.poll()}); see mcp-stderr.log")
            self.pending += data
        raise TimeoutError(f"MCP {method} exceeded {timeout}s")

    def send(self, value):
        self.child.stdin.write((json.dumps(value) + "\n").encode())
        self.child.stdin.flush()

    def call(self, name, arguments=None, timeout=180):
        self.serial += 1
        result = self.request("tools/call", {"name": name, "arguments": arguments or {}}, timeout)
        (self.output / f"{self.serial:03d}-{name}.json").write_text(json.dumps(result, indent=2))
        if result.get("isError"):
            raise RuntimeError(f"{name}: {flatten(result)[:2400]}")
        value = result.get("structuredContent")
        if value is None:
            texts = [c["text"] for c in result.get("content", []) if c.get("type") == "text"]
            try:
                value = json.loads("\n".join(texts))
            except json.JSONDecodeError as error:
                raise AssertionError(f"{name} has neither structuredContent nor JSON text") from error
        return value

    def close(self):
        started = time.monotonic()
        shutdown_mode = "already-exited"
        if self.child.poll() is None:
            shutdown_mode = "stdin-eof"
            self.child.stdin.close()
            try:
                self.child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                shutdown_mode = "terminated-after-eof-timeout"
                self.child.terminate()
                try:
                    self.child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    shutdown_mode = "killed-after-terminate-timeout"
                    self.child.kill()
                    self.child.wait()
        self.selector.close()
        self.errors.close()
        (self.output / "mcp-shutdown.json").write_text(json.dumps({"mode": shutdown_mode,
            "exit_code": self.child.returncode, "duration_seconds": round(time.monotonic() - started, 3)}, indent=2) + "\n")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_json(url, child):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError(f"Fixture process exited {child.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return json.load(response)
        except (OSError, ValueError):
            time.sleep(0.1)
    raise TimeoutError(f"Fixture endpoint did not become ready: {url}")


def terminate(child):
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rea", default="rea", help="CLI command, shell-like argument splitting")
    parser.add_argument("--node", default="node")
    parser.add_argument("--package-root", default="/var/lib/workshop/sdk/hermes-rea/rea/node_modules/rea-agents")
    parser.add_argument("--output", required=True)
    parser.add_argument("--only", help="Comma-separated test IDs")
    parser.add_argument("--import-bundle", help="Evidence bundle saved by a previous server/workshop lifecycle")
    parser.add_argument("--require", default="cli,mcp-catalog,javascript,archive,evidence", help="Unavailable required tests fail the run")
    args = parser.parse_args()
    sdk_root = Path(args.package_root).resolve().parents[2]
    os.environ["PATH"] = ":".join([str(sdk_root / "node/bin"), str(sdk_root / "providers/bin"), os.environ.get("PATH", "/usr/bin:/bin")])
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    work = output / "fixtures"
    work.mkdir(exist_ok=True)
    command = shlex.split(args.rea)
    results = []
    selected = set(args.only.split(",")) if args.only else None
    required = set(args.require.split(","))
    mcp = None
    binary = work / "native-fixture"
    app = work / "javascript-app"
    app.mkdir(exist_ok=True)
    (app / "package.json").write_text(json.dumps({"name": "hermes-rea-fixture", "version": "1.0.0", "main": "main.js"}))
    (app / "main.js").write_text("const {ipcMain} = require('electron');\nconst helper = require('./helper');\nipcMain.handle('sdk-greeting', () => helper.greet('world'));\n")
    (app / "helper.js").write_text("exports.greet = name => 'sdk-hello-' + name;\n")
    (work / "native.c").write_text('#include <stdio.h>\nint sdk_add(int a,int b){return a+b;}\nint main(void){puts("hermes-rea-native-fixture");return sdk_add(2,3)==5?0:1;}\n')
    archive = work / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("sdk-fixture.txt", "hermes-rea-archive-fixture\n")
        z.writestr("nested/package.json", '{"name":"nested-sdk-fixture","version":"1.0.0"}')
    firmware = work / "firmware.bin"
    firmware.write_bytes(b"HERMES-FIRMWARE\x00" * 32 + gzip.compress(b"hermes-firmware-payload\n" * 200, mtime=0))
    wasm = work / "fixture.wasm"
    # Valid module: (func (export "sdk_add") (param i32 i32) (result i32) local.get 0 local.get 1 i32.add)
    wasm.write_bytes(bytes.fromhex("0061736d0100000001070160027f7f017f03020100070b010773646b5f61646400000a09010700200020016a0b"))
    database = work / "fixture.sqlite"
    if database.exists():
        database.unlink()
    with sqlite3.connect(database) as db:
        db.execute("create table sdk_items (id integer primary key, name text)")
        db.execute("insert into sdk_items values (1, 'hermes-sqlite-fixture')")

    def test(name, fn):
        if selected is not None and name not in selected:
            return
        started = time.monotonic()
        try:
            detail = fn()
            record = {"test": name, "status": "pass", "detail": detail}
        except Unavailable as error:
            record = {"test": name, "status": "unavailable", "reason": str(error)}
        except Exception as error:
            record = {"test": name, "status": "fail", "reason": f"{type(error).__name__}: {error}"}
        record["duration_seconds"] = round(time.monotonic() - started, 3)
        results.append(record)
        (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps(record), flush=True)

    def cli():
        version = run(command + ["--version"]).strip()
        assert version, "CLI returned an empty version"
        reports = {}
        for subcommand in ("doctor", "providers", "capabilities"):
            result = subprocess.run(command + [subcommand, "--json"], capture_output=True, text=True, timeout=180)
            (output / f"cli-{subcommand}.json").write_text(result.stdout)
            (output / f"cli-{subcommand}.stderr").write_text(result.stderr)
            value = json.loads(result.stdout)
            assert isinstance(value, dict) and value, f"{subcommand} returned no JSON object"
            # Doctor intentionally reports unavailable external providers. Keep the exit
            # code and full findings; successful JSON is a CLI-contract pass only.
            if subcommand != "doctor":
                assert result.returncode == 0, f"{subcommand} exited {result.returncode}"
            reports[subcommand] = {"exit_code": result.returncode, "keys": sorted(value)}
        return {"version": version, "reports": reports, "scope": "CLI contracts; provider readiness is recorded separately"}

    def full_source():
        source_root = sdk_root / "upstream/rea"
        manifest_path = sdk_root / "upstream/rea.manifest.json"
        assert manifest_path.is_file(), f"Full upstream source manifest missing: {manifest_path}"
        manifest = json.loads(manifest_path.read_text())
        assert manifest["schema_version"] == 1, manifest
        assert manifest["upstream_commit"] == "51459cf203ae1eb6b586a95b21899eaa0f631823", manifest["upstream_commit"]
        assert len(manifest["repositories"]) == 6, "Main repository plus all five pinned submodules are required"
        assert {repo["path"] for repo in manifest["repositories"]} == {".", "third_party/jadx-headless-mcp", "third_party/binwalk", "third_party/unblob", "third_party/ghidra-nativeaot", "third_party/wakaru"}
        assert all(repo["file_count"] > 0 for repo in manifest["repositories"]), "An upstream repository is empty"
        assert sum(repo["file_count"] for repo in manifest["repositories"]) == len(manifest["files"])
        verified_bytes = 0
        for entry in manifest["files"]:
            relative = Path(entry["path"])
            assert not relative.is_absolute() and ".." not in relative.parts, entry
            path = source_root / relative
            if entry["kind"] == "symlink":
                assert path.is_symlink(), entry
                payload = os.fsencode(os.readlink(path))
            else:
                assert path.is_file() and not path.is_symlink(), entry
                payload = path.read_bytes()
                if entry["git_mode"] == "100755":
                    assert os.access(path, os.X_OK), entry
            assert len(payload) == entry["bytes"], entry
            assert hashlib.sha256(payload).hexdigest() == entry["sha256"], entry
            assert hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest() == entry["git_object"], entry
            verified_bytes += len(payload)
        for link in manifest["runtime_links"]:
            path = source_root / link["path"]
            assert path.is_symlink() and os.readlink(path) == link["target"] and path.exists(), link
        source_cli = [args.node, str(source_root / "scripts/rea.mjs")]
        version = run(source_cli + ["--version"]).strip()
        assert version == run(command + ["--version"]).strip(), version
        graph = json.loads(run(source_cli + ["analyze-javascript-application", str(app), "--json"]))
        (output / "full-source-javascript.json").write_text(json.dumps(graph, indent=2))
        contains(graph, "sdk-greeting")
        contains(graph, "helper.js")
        return {"source_commit": manifest["upstream_commit"], "repositories": len(manifest["repositories"]),
                "verified_files": len(manifest["files"]), "verified_bytes": verified_bytes,
                "runtime_links": len(manifest["runtime_links"]), "original_source_cli_version": version,
                "original_cli_javascript_operation": True}

    def catalog():
        initialized = mcp.request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "hermes-sdk-functional", "version": "1"}})
        (output / "initialize.json").write_text(json.dumps(initialized, indent=2))
        mcp.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        inventory = []
        cursor = None
        while True:
            page = mcp.request("tools/list", {"cursor": cursor} if cursor else {})
            inventory.extend(page["tools"])
            cursor = page.get("nextCursor")
            if not cursor:
                break
        (output / "tools-list.json").write_text(json.dumps(inventory, indent=2))
        names = {tool["name"] for tool in inventory}
        assert len(names) == len(inventory), "Duplicate tool names"
        assert "binary_session" in names
        session = normalized(mcp.call("binary_session"))
        groups = session["tool_availability"]["groups"]
        available_names = {name for group in groups for name in group["names"]}
        assert names == available_names, f"Inventory mismatch: list-only={sorted(names-available_names)}, session-only={sorted(available_names-names)}"
        contracts = Path(args.package_root) / "dist/contracts/toolContracts.js"
        assert contracts.is_file(), f"Packaged canonical contracts missing: {contracts}"
        script = "const {TOOL_CONTRACTS}=await import(process.argv[1]);process.stdout.write(JSON.stringify(TOOL_CONTRACTS.map(x=>x.name)))"
        canonical = set(json.loads(run([args.node, "--input-type=module", "-e", script, contracts.as_uri()])))
        assert names == canonical, f"Canonical mismatch: missing={sorted(canonical-names)}, extra={sorted(names-canonical)}"
        return {"tool_count": len(names), "binary_session_inventory_matches": True, "packaged_canonical_contracts_match": True}

    def javascript():
        evidence = mcp.call("analyze_javascript_application", {"input_path": str(app)})
        contains(evidence, "sdk-greeting")
        contains(evidence, "helper.js")
        contains(evidence, "main.js")
        assert evidence.get("evidence_id") or evidence.get("id"), "No retained Evidence identity"
        cli_result = json.loads(run(command + ["analyze-javascript-application", str(app), "--json"]))
        (output / "cli-javascript.json").write_text(json.dumps(cli_result, indent=2))
        contains(cli_result, "sdk-greeting")
        contains(cli_result, "helper.js")
        return {"assertions": ["CLI/MCP main/helper module graph", "Electron IPC sdk-greeting", "retained Evidence identity"], "scope": "Static source analysis; no Electron runtime claim"}

    def archive_test():
        mcp.call("open_binary", {"path": str(archive)})
        result = mcp.call("inspect_artifact")
        contains(result, "sdk-fixture.txt")
        contains(result, "nested/package.json")
        mcp.call("close_binary")
        return "ZIP inventory contains both exact member paths"

    def evidence_test():
        evidence = mcp.call("analyze_javascript_application", {"input_path": str(app)})
        evidence_id = evidence.get("evidence_id", evidence.get("id"))
        assert evidence_id, "Producer supplied no Evidence identity"
        path = output / "evidence-bundle.json"
        mcp.call("export_evidence_bundle", {"path": str(path), "overwrite": True})
        bundle = json.loads(path.read_text())
        contains(bundle, evidence_id)
        mcp.call("reset_investigation")
        mcp.call("import_evidence_bundle", {"path": str(path)})
        restored = mcp.call("get_evidence_bundle")
        contains(restored, evidence_id)
        return {"evidence_id": evidence_id, "export_reset_import": True, "bundle_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def evidence_import():
        if not args.import_bundle:
            raise Unavailable("Select --import-bundle from the previous lifecycle")
        path = Path(args.import_bundle).resolve()
        original = json.loads(path.read_text())
        def identities(value):
            found = set()
            if isinstance(value, dict):
                if isinstance(value.get("evidence_id"), str):
                    found.add(value["evidence_id"])
                for child in value.values():
                    found.update(identities(child))
            elif isinstance(value, list):
                for child in value:
                    found.update(identities(child))
            return found
        wanted = identities(original)
        assert wanted, "Saved bundle contains no Evidence identity"
        mcp.call("import_evidence_bundle", {"path": str(path)})
        restored = mcp.call("get_evidence_bundle")
        for evidence_id in wanted:
            contains(restored, evidence_id)
        return {"imported_evidence_count": len(wanted), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def compile_native():
        if not binary.exists():
            run([require_program("gcc"), "-g", "-O0", "-o", str(binary), str(work / "native.c")])

    def provider_no_fallback():
        compile_native()
        missing_ghidra = work / "deliberately-absent-ghidra"
        assert not missing_ghidra.exists()
        case = output / "provider-no-fallback"
        case.mkdir(exist_ok=True)
        isolated = MCP(["env", f"GHIDRA_INSTALL_DIR={missing_ghidra}", *command, "mcp"], case)
        try:
            isolated.request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "hermes-provider-selection-regression", "version": "1"}})
            isolated.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            result = isolated.request("tools/call", {"name": "open_binary", "arguments": {"path": str(binary), "provider_id": "ghidra"}})
            (case / "unavailable-selected-provider.json").write_text(json.dumps(result, indent=2))
            assert result.get("isError") is True, "Unavailable explicit Ghidra selection unexpectedly succeeded"
            failure = result.get("structuredContent")
            if failure is None:
                failure = json.loads("\n".join(item["text"] for item in result["content"] if item["type"] == "text"))
            assert "ghidra" in flatten(failure).lower(), failure
            assert isinstance(failure.get("error"), dict), failure
            state = normalized(isolated.call("binary_session"))
            assert state["open"] is False and state["analysis_provider_binding"] is None, state
            return {"selected_provider": "ghidra", "error_code": failure["error"].get("code"),
                    "error_message": failure["error"].get("message"), "raw_error": str(case / "unavailable-selected-provider.json"), "open_after_failure": False,
                    "analysis_provider_binding": None, "scope": "Explicit selected-provider failure; no implicit local substitute"}
        finally:
            isolated.close()

    def native():
        compile_native()
        mcp.call("open_binary", {"path": str(binary), "provider_id": "ghidra"}, timeout=900)
        opened = True
        try:
            state = normalized(mcp.call("binary_session"))
            assert state["analysis_provider_binding"]["provider"]["id"] == "ghidra", state
            assert state["analysis_provider_binding"]["selection_source"] == "request", state
            code = mcp.call("procedure_pseudo_code", {"procedure": "sdk_add"}, timeout=300)
            contains(code, "+")
            asm = normalized(mcp.call("procedure_assembly", {"procedure": "sdk_add"}))
            assert isinstance(asm, str) and ": ADD " in asm and ": RET" in asm, asm
            snapshot = output / "native-snapshot.json"
            mcp.call("close_binary", {"snapshot_path": str(snapshot), "overwrite": True}, timeout=300)
            opened = False
            assert snapshot.is_file() and snapshot.stat().st_size > 0
            mcp.call("open_binary", {"path": str(binary), "provider_id": "ghidra", "snapshot_path": str(snapshot)}, timeout=900)
            opened = True
            contains(mcp.call("procedure_pseudo_code", {"procedure": "sdk_add"}, timeout=300), "+")
        finally:
            if opened:
                mcp.call("close_binary", timeout=300)
        return "Ghidra decompiled sdk_add, read assembly, saved/reopened target-bound snapshot"

    def kuna():
        compile_native()
        mcp.call("open_binary", {"path": str(binary), "provider_id": "kuna"}, timeout=300)
        try:
            state = normalized(mcp.call("binary_session"))
            assert state["analysis_provider_binding"]["provider"]["id"] == "kuna", state
            assert state["analysis_provider_binding"]["selection_source"] == "request", state
            code = mcp.call("procedure_pseudo_code", {"procedure": "sdk_add"}, timeout=300)
            contains(code, "+")
        finally:
            mcp.call("close_binary", timeout=300)
        return "Selected Kuna explicitly and decompiled the synthetic addition function"

    def objdump():
        compile_native()
        result = normalized(mcp.call("inspect_with_objdump", {"path": str(binary), "operation": "disassemble", "symbol": "sdk_add"}))
        assert result["completion_status"] == "complete" and result["exit_code"] == 0, result
        assert "<sdk_add>" in result["stdout"] and "\tret" in result["stdout"] and "\tadd" in result["stdout"], result
        return "GNU objdump disassembled the synthetic sdk_add function"

    def binary_layout():
        compile_native()
        result = mcp.call("inspect_binary_layout", {"path": str(binary)})
        contains(result, "sdk_add")
        contains(result, ".text")
        return "Real pwntools ELF symbol/section inspection"

    def rizin():
        compile_native()
        result = normalized(mcp.call("execute_rizin_command", {"path": str(binary), "command": "isj"}))
        assert result["completion_status"] == "complete" and result["exit_code"] == 0, result
        symbols = json.loads(result["stdout"])
        assert any(symbol.get("name") == "sdk_add" for symbol in symbols), symbols
        return "Real Rizin symbol inventory includes sdk_add"

    def gdb():
        compile_native()
        session = mcp.call("start_gdb_session", {"executable": str(binary)})
        session_id = session["session_id"]
        try:
            result = normalized(mcp.call("gdb_console", {"session_id": session_id, "command": "disassemble sdk_add"}))
            assert result["completion_status"] == "complete", result
            assert "sdk_add" in result["console"] and "ret" in result["console"] and "add" in result["console"], result
        finally:
            mcp.call("close_gdb_session", {"session_id": session_id})
        return "Persistent real GDB/MI session disassembled sdk_add and closed"

    def rizin_debugger():
        compile_native()
        master, slave = pty.openpty()
        session_id = None
        try:
            session = mcp.call("start_rizin_debug_session", {"path": str(binary), "inferior_tty": os.ttyname(slave)})
            session_id = session["session_id"]
            status = mcp.call("rizin_debug_session_status", {"session_id": session_id})
            assert status["state"] == "ready", status
            registers = normalized(mcp.call("rizin_debug_command", {"session_id": session_id, "command": "drj"}))
            assert registers["completion_status"] == "complete", registers
            observed = json.loads(registers["output"].strip())
            assert isinstance(observed, dict) and int(observed.get("rip", 0)) > 0, registers
            # Run only this source-owned fixture to completion before closing.
            mcp.call("rizin_debug_command", {"session_id": session_id, "command": "dc"})
            return {"assertion": "Real Rizin debugger lifecycle, register read and owned inferior execution", "register_count": len(observed)}
        finally:
            if session_id:
                mcp.call("close_rizin_debug_session", {"session_id": session_id})
            os.close(slave)
            os.close(master)

    def frida():
        devices = mcp.call("list_frida_devices")
        contains(devices, "local")
        processes = mcp.call("list_frida_processes", {"device_id": "local"})
        def has_pid(value):
            if isinstance(value, dict):
                return value.get("pid") == os.getpid() or any(has_pid(v) for v in value.values())
            if isinstance(value, list):
                return any(has_pid(v) for v in value)
            return False
        assert has_pid(processes), "Frida did not enumerate this test process PID"
        return "Real Frida native binding enumerated local device and this test process; injection is separate coverage"

    def frida_injection():
        source = work / "frida-fixture.c"
        executable = work / "frida-fixture"
        source.write_text('#include <unistd.h>\nconst char sdk_marker[]="hermes-frida-injected-marker";\nint main(void){sleep(2);return 0;}\n')
        run([require_program("gcc"), "-g", "-O0", "-rdynamic", "-o", str(executable), str(source)])
        session_id, script_id, pidfd = None, None, None
        try:
            started = mcp.call("start_frida_session", {"mode": "spawn", "device_id": "local", "program": str(executable)})
            session_id = started["session_id"]
            assert started["state"] == "paused", started
            pidfd = os.pidfd_open(started["pid"])
            script = "const symbol = Process.mainModule.enumerateSymbols().find(item => item.name === 'sdk_marker'); if (!symbol) throw new Error('Owned sdk_marker symbol missing'); send({fixture: symbol.address.readUtf8String(), pid: Process.id});"
            loaded = normalized(mcp.call("load_frida_script", {"session_id": session_id, "source_kind": "inline", "source": script}))
            script_id = loaded["script_id"]
            assert loaded["source_sha256"] == hashlib.sha256(script.encode()).hexdigest(), loaded
            contains(loaded["messages"], "hermes-frida-injected-marker")
            def observed_pid(value):
                if isinstance(value, dict):
                    return value.get("pid") == started["pid"] or any(observed_pid(child) for child in value.values())
                return any(observed_pid(child) for child in value) if isinstance(value, list) else False
            assert observed_pid(loaded["messages"]), loaded
            status = normalized(mcp.call("frida_session_status", {"session_id": session_id}))
            assert any(item["script_id"] == script_id for item in status["scripts"]), status
            assert mcp.call("unload_frida_script", {"session_id": session_id, "script_id": script_id})["unloaded"]
            script_id = None
            assert mcp.call("resume_frida_session", {"session_id": session_id})["state"] == "running"
            return {"assertion": "Spawned owned native process, injected script, read exact exported memory and PID, unloaded and resumed", "pid": started["pid"], "script_sha256": loaded["source_sha256"]}
        finally:
            try:
                if session_id:
                    mcp.call("close_frida_session", {"session_id": session_id})
            finally:
                if pidfd is not None:
                    with selectors.DefaultSelector() as exits:
                        exits.register(pidfd, selectors.EVENT_READ)
                        if not exits.select(4):
                            signal.pidfd_send_signal(pidfd, signal.SIGTERM)
                            if not exits.select(2):
                                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                    os.close(pidfd)

    def sqlite_test():
        result = mcp.call("inspect_sqlite_database", {"path": str(database), "table": "sdk_items", "columns": ["id", "name"]})
        contains(result, "hermes-sqlite-fixture")
        contains(result, "sdk_items")
        return "Built-in SQLite provider read exact fixture table and row"

    def managed():
        compiler = require_program("mcs")
        source = work / "ManagedFixture.cs"
        assembly = work / "ManagedFixture.dll"
        source.write_text('namespace HermesSdk { public class Marker { public static string Greet() { return "hermes-managed-fixture"; } } }\n')
        run([compiler, "-target:library", f"-out:{assembly}", str(source)])
        identity = mcp.call("inspect_managed_artifact", {"path": str(assembly)})
        contains(identity, "ManagedFixture")
        members = mcp.call("inspect_managed_members", {"path": str(assembly)})
        contains(members, "HermesSdk.Marker")
        contains(members, "Greet")
        contains(members, "hermes-managed-fixture")
        return "Built-in PE/CLI metadata and CIL member/string inspection; assembly was not executed"

    def build_apk():
        apk = work / "android-fixture.apk"
        if apk.is_file():
            return apk
        source_dir = work / "android-source"
        smali_dir = source_dir / "smali/fixture"
        smali_dir.mkdir(parents=True, exist_ok=True)
        (source_dir / "apktool.yml").write_text("version: 3.0.3\napkFileName: fixture.apk\nusesFramework:\n  ids:\n  - 1\nsdkInfo:\n  minSdkVersion: 21\n  targetSdkVersion: 28\npackageInfo:\n  forcedPackageId: 127\nversionInfo:\n  versionCode: 1\n  versionName: 1.0\ndoNotCompress: []\n")
        (source_dir / "AndroidManifest.xml").write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="fixture.sdk"><uses-sdk android:minSdkVersion="21" android:targetSdkVersion="28"/><application android:label="HermesSdkFixture"/></manifest>')
        (smali_dir / "Marker.smali").write_text('.class public Lfixture/Marker;\n.super Ljava/lang/Object;\n.method public static greet()Ljava/lang/String;\n .registers 1\n const-string v0, "hermes-jadx-fixture"\n return-object v0\n.end method\n')
        apktool_command = os.environ.get("REA_APKTOOL_COMMAND")
        if not apktool_command and (sdk_root / "wrappers/apktool").is_file():
            apktool_command = str(sdk_root / "wrappers/apktool")
        run([apktool_command or require_program("apktool"), "build", str(source_dir), "-o", str(apk)])
        return apk

    def android():
        apk = build_apk()
        package = mcp.call("inspect_android_package", {"path": str(apk)}, timeout=300)
        contains(package, "fixture.sdk")
        klass = normalized(mcp.call("inspect_android_class", {"path": str(apk), "class_name": "fixture.Marker"}, timeout=300))
        member = next(item for item in klass["methods"] if item["name"] == "greet" and item["dex_descriptor"] == "()Ljava/lang/String;")
        method = normalized(mcp.call("inspect_android_method", {"path": str(apk), "class_name": "fixture.Marker", "method_name": "greet", "overload_index": member["overload_index"]}, timeout=300))
        assert method["representation"] == "java" and method["body_status"] == "available" and method["fell_back"] is False, method
        contains(method["source"], "hermes-jadx-fixture")
        return "Real APK manifest/package and class metadata inspection plus exact JADX method decompilation; no device execution"

    def apktool():
        apk = build_apk()
        result = mcp.call("decode_android_resources", {"path": str(apk)}, timeout=300)
        contains(result, "fixture.sdk")
        contains(result, "HermesSdkFixture")
        return "Real Apktool decoded synthetic APK manifest and application label"

    def javascript_recovery():
        source = work / "minified.js"
        source.write_text('(()=>{var a="hermes-wakaru-fixture";console.log(a)})();\n')
        destination = work / "wakaru-output"
        if destination.exists():
            shutil.rmtree(destination)
        result = mcp.call("recover_javascript_sources", {"path": str(source), "output_directory": str(destination)})
        assert destination.is_dir(), "Wakaru did not publish derived output"
        assert any(b"hermes-wakaru-fixture" in p.read_bytes() for p in destination.rglob("*") if p.is_file()), "Derived source lacks fixture string"
        contains(result, "wakaru")
        return "Real Wakaru recovery produced derived source containing the exact fixture string"

    def wasm_test():
        result = mcp.call("inspect_wasm_artifact", {"path": str(wasm)})
        contains(result, "sdk_add")
        contains(result, "i32.add")
        return "Real WABT validation, export inventory and WAT decoding"

    def firmware_test():
        result = mcp.call("inspect_firmware_regions", {"path": str(firmware)})
        assert "gzip" in flatten(result).lower(), "Embedded gzip signature was not identified"
        return "Real Binwalk found the embedded gzip signature"

    def firmware_extract():
        compressed = work / "payload.gz"
        compressed.write_bytes(gzip.compress(b"hermes-firmware-payload\n" * 20, mtime=0))
        destination = work / "unblob-output"
        if destination.exists():
            shutil.rmtree(destination)
        result = mcp.call("extract_firmware", {"path": str(compressed), "output_directory": str(destination)}, timeout=300)
        assert destination.is_dir(), "Unblob did not publish output"
        files = [p for p in destination.rglob("*") if p.is_file()]
        assert any(b"hermes-firmware-payload" in p.read_bytes() for p in files), "No extracted file contains exact payload"
        return {"assertion": "Real Unblob extracted exact gzip payload bytes", "output_files": len(files)}

    def firmware_ext2():
        maker = Path("/usr/sbin/mke2fs")
        if not maker.is_file():
            raise Unavailable("Declared e2fsprogs runtime lacks /usr/sbin/mke2fs")
        case = output / "firmware-ext2"
        case.mkdir(exist_ok=True)
        source = case / "owned-root"
        source.mkdir(exist_ok=True)
        payload = b"hermes-rea-ext2-extraction-fixture\n"
        (source / "sdk-marker.txt").write_bytes(payload)
        disk = case / "fixture.ext2"
        with disk.open("wb") as stream:
            stream.truncate(8 * 1024 * 1024)
        run([str(maker), "-q", "-F", "-t", "ext2", "-d", str(source), str(disk)])
        destination = case / "extracted"
        executable = shutil.which(command[0])
        assert executable, "REA launcher must resolve before restricted-PATH regression"
        narrow = MCP(["/usr/bin/env", "PATH=/usr/bin:/bin", executable, *command[1:], "mcp"], case)
        try:
            narrow.request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "hermes-sdk-ext2-path-test", "version": "1"}})
            narrow.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            narrow.call("extract_firmware", {"path": str(disk), "output_directory": str(destination)}, timeout=300)
        finally:
            narrow.close()
        matches = [entry for entry in destination.rglob("sdk-marker.txt") if entry.is_file() and entry.read_bytes() == payload]
        assert matches, "Unblob/debugfs did not extract the exact ext2 fixture payload"
        return {"assertion": "Real Unblob/debugfs extracted owned ext2 file with exact bytes after REA launched with PATH=/usr/bin:/bin",
                "payload_sha256": hashlib.sha256(payload).hexdigest(), "extracted_paths": [str(entry) for entry in matches],
                "scope": "Mounted no filesystem; generated an owned 8 MiB ext2 image with declared e2fsprogs"}

    def runtime():
        port = free_port()
        script = app / "runtime-fixture.cjs"
        script.write_text("global.sdkFixture = 'hermes-runtime-fixture'; setInterval(()=>{},1000);\n")
        with (output / "runtime-fixture.stderr").open("wb") as errors:
            child = subprocess.Popen([args.node, f"--inspect=127.0.0.1:{port}", str(script)], stdout=subprocess.DEVNULL, stderr=errors)
            try:
                endpoint = f"http://127.0.0.1:{port}"
                targets = wait_json(endpoint + "/json/list", child)
                target_id = targets[0]["id"]
                listing = mcp.call("list_javascript_runtime_targets", {"inspector_endpoint": endpoint})
                contains(listing, target_id)
                observed = mcp.call("observe_javascript_runtime", {"inspector_endpoint": endpoint, "target_id": target_id, "runtime_kind": "node", "observation_ms": 250})
                contains(observed, "runtime-fixture.cjs")
                static = mcp.call("analyze_javascript_application", {"input_path": str(app)})
                reconciled = mcp.call("reconcile_javascript_runtime", {"static_layers": [{"analysis": {"kind": "retained-evidence", "evidence_id": static["evidence_id"]}, "runtime_mappings": [{"kind": "file-root", "root": str(app)}]}], "runtime_observations": [{"kind": "retained-evidence", "evidence_id": observed["evidence_id"]}]})
                contains(reconciled, "runtime-fixture.cjs")
            finally:
                terminate(child)
        return "Real local Node Inspector observation and correlation with static application Evidence"

    def process_capture():
        result = mcp.call("capture_process_scenario", {"executable": "/bin/echo", "arguments": ["hermes-process-fixture"], "working_directory": str(work), "timeout_ms": 10000})
        contains(result, "hermes-process-fixture")
        return "Owned PTY process capture recorded actual echo output"

    def browser(mode="passive"):
        browser_path = os.environ.get("REA_TEST_BROWSER")
        if not browser_path:
            browser_path = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
        if not browser_path:
            browser_path = next((str(p) for p in (sdk_root / "providers/chromium").rglob("chrome") if p.is_file() and os.access(p, os.X_OK)), None)
        if not browser_path:
            raise Unavailable("Set REA_TEST_BROWSER to a real Chromium/Chrome executable")
        page = work / "browser-page"
        page.mkdir(exist_ok=True)
        (page / "index.html").write_text('<!doctype html><title>Hermes SDK Browser Fixture</title><h1 id="sdk-marker">hermes-browser-fixture</h1><button id="sdk-action">Apply fixture action</button><script type="module" src="fixture.js"></script>')
        script_text = "import {marker} from './dependency.js';\ndocument.body.dataset.sdkFixture = marker;\ndocument.querySelector('#sdk-action').addEventListener('click', function sdkFixtureClick(){document.querySelector('#sdk-marker').textContent='hermes-scenario-complete';});\ndocument.title = 'Hermes SDK Browser Fixture Ready';\n//# sourceMappingURL=fixture.js.map\n"
        (page / "fixture.js").write_text(script_text)
        (page / "dependency.js").write_text("export const marker = 'loaded';\n")
        (page / "fixture.js.map").write_text(json.dumps({"version": 3, "sources": ["original-fixture.ts"], "names": [], "mappings": "AAAA", "sourcesContent": ["// hermes-original-source-fixture\n"]}))
        (page / "ready.json").write_text('{"ready":true}')
        http_port, cdp_port = free_port(), free_port()
        origin = f"http://127.0.0.1:{http_port}"
        with (output / "browser-fixture.stderr").open("wb") as errors:
            server = subprocess.Popen(["python3", "-m", "http.server", str(http_port), "--bind", "127.0.0.1", "--directory", str(page)], stdout=subprocess.DEVNULL, stderr=errors)
            wait_json(origin + "/ready.json", server)
            browser_args = [browser_path, "--headless", "--disable-dev-shm-usage", "--disable-gpu", f"--remote-debugging-port={cdp_port}", f"--user-data-dir={work / 'chrome-profile'}", origin]
            child = subprocess.Popen(browser_args, stdout=subprocess.DEVNULL, stderr=errors)
            sandbox_mode = "enabled"
            sandbox_failure = None
            try:
                endpoint = f"http://127.0.0.1:{cdp_port}"
                try:
                    targets = wait_json(endpoint + "/json/list", child)
                except (RuntimeError, TimeoutError):
                    terminate(child)
                    errors.flush()
                    diagnostics = (output / "browser-fixture.stderr").read_text(errors="replace")
                    if not any(marker in diagnostics.lower() for marker in ("sandbox", "operation not permitted", "namespace")):
                        raise
                    # This fallback applies only to our generated localhost test page.
                    # Keep the failure and weakened mode in the result, never in SDK defaults.
                    sandbox_failure = diagnostics[-1600:]
                    sandbox_mode = "disabled-for-synthetic-fixture-after-host-refusal"
                    child = subprocess.Popen(browser_args[:-1] + ["--no-sandbox", origin], stdout=subprocess.DEVNULL, stderr=errors)
                    targets = wait_json(endpoint + "/json/list", child)
                ready_deadline = time.monotonic() + 15
                target = None
                while time.monotonic() < ready_deadline:
                    target = next((t for t in targets if t.get("type") == "page" and t.get("title") == "Hermes SDK Browser Fixture Ready"), None)
                    if target:
                        break
                    time.sleep(0.1)
                    targets = wait_json(endpoint + "/json/list", child)
                assert target, "Browser fixture did not finish loading its real ES modules"
                if mode == "scenario":
                    result = mcp.call("capture_browser_scenario", {
                        "browser": {"mode": "connect", "cdp_endpoint": endpoint, "target_id": target["id"]},
                        "start_url": {"url": origin + "/"},
                        "actions": [{"step_id": "apply-fixture", "action": "click", "locator": {"kind": "css", "selector": "#sdk-action"}}],
                        "capture": {"at_end": ["dom", "accessibility", "url"]},
                    })
                    produced = normalized(result)
                    assert all(step["status"] == "completed" for step in produced["steps"]), produced["steps"]
                    contains(produced["steps"][-1]["artifacts"]["accessibility"], "hermes-scenario-complete")
                elif mode == "runtime":
                    result = normalized(mcp.call("inspect_web_event_listeners", {"cdp_endpoint": endpoint, "target_id": target["id"], "selector": "#sdk-action", "allowed_origins": [origin]}))
                    assert result["selected_node"]["match"] == "found", result
                    assert any(listener["type"] == "click" for listener in result["listeners"]), result
                    contains(result["sources"], "sdkFixtureClick")
                elif mode in ("export", "source", "modules"):
                    capture = mcp.call("inspect_web_page", {"cdp_endpoint": endpoint, "target_id": target["id"], "allowed_origins": [origin], "include_script_sources": True})
                    capture_path = output / f"web-{mode}-capture.json"
                    capture_path.write_text(json.dumps(capture))
                    export_path = work / f"web-{mode}-export"
                    if export_path.exists():
                        shutil.rmtree(export_path)
                    exported = normalized(mcp.call("export_web_scripts", {"capture_path": str(capture_path), "output_directory": str(export_path)}))
                    script_index, script = next((i, entry) for i, entry in enumerate(exported["scripts"]) if entry["url"] == origin + "/fixture.js")
                    assert script["content"]["state"] == "exported", script
                    script_file = Path(exported["analysis_input"]["input_path"]) / script["content"]["relative_path"]
                    assert script_file.read_text() == script_text, script
                    assert hashlib.sha256(script_file.read_bytes()).hexdigest() == script["content"]["sha256"], script
                    if mode == "source":
                        traced = mcp.call("trace_web_source_location", {"manifest_path": exported["manifest"]["path"], "script_index": script_index,
                            "source_map": {"path": str(page / "fixture.js.map"), "url": origin + "/fixture.js.map"}, "generated_position": {"line": 1, "column": 0}})
                        contains(traced, "original-fixture.ts")
                        contains(traced, "hermes-original-source-fixture")
                    elif mode == "modules":
                        traced = normalized(mcp.call("trace_web_module_imports", {"manifest_path": exported["manifest"]["path"], "script_index": script_index}))
                        assert any(entry["specifier"] == "./dependency.js" and entry["resolution"] == {"state": "resolved", "url": origin + "/dependency.js"} and entry["captured_candidates"] for entry in traced["imports"]), traced
                else:
                    listing = mcp.call("list_browser_targets", {"cdp_endpoint": endpoint, "allowed_origins": [origin]})
                    contains(listing, target["id"])
                    result = mcp.call("inspect_web_page", {"cdp_endpoint": endpoint, "target_id": target["id"], "allowed_origins": [origin], "include_accessibility_text": True})
                    contains(result, "hermes-browser-fixture")
            finally:
                terminate(child)
                terminate(server)
        assertions = {"scenario": "Real browser click action changed captured accessibility", "runtime": "Inspected a real registered click listener and its source", "export": "Captured and exported exact browser script bytes and SHA256", "source": "Traced exported script position to exact embedded original source", "modules": "Native browser resolver resolved an ES import to its captured dependency", "passive": "Real headless browser CDP target discovery and DOM/accessibility inspection"}
        return {"assertion": assertions[mode], "sandbox_mode": sandbox_mode, "sandbox_failure": sandbox_failure}

    def mitmproxy():
        mitmdump = os.environ.get("REA_MITMDUMP_COMMAND")
        if not mitmdump and (sdk_root / "providers/mitmproxy/mitmdump").is_file():
            mitmdump = str(sdk_root / "providers/mitmproxy/mitmdump")
        mitmdump = mitmdump or require_program("mitmdump")
        page = work / "proxy-page"
        page.mkdir(exist_ok=True)
        (page / "sdk-mitm-fixture.txt").write_text("hermes-mitmproxy-fixture\n")
        http_port, proxy_port = free_port(), free_port()
        capture = work / "fixture.mitm"
        if capture.exists():
            capture.unlink()
        with (output / "mitmproxy-fixture.stderr").open("wb") as errors:
            server = subprocess.Popen(["python3", "-m", "http.server", str(http_port), "--bind", "127.0.0.1", "--directory", str(page)], stdout=subprocess.DEVNULL, stderr=errors)
            proxy = subprocess.Popen([mitmdump, "--listen-host", "127.0.0.1", "--listen-port", str(proxy_port), "-w", str(capture), "--set", "block_global=false", "--set", f"confdir={work / 'mitmproxy-config'}"], stdout=subprocess.DEVNULL, stderr=errors)
            try:
                deadline = time.monotonic() + 30
                while True:
                    try:
                        connection = http.client.HTTPConnection("127.0.0.1", proxy_port, timeout=2)
                        connection.request("GET", f"http://127.0.0.1:{http_port}/sdk-mitm-fixture.txt")
                        response = connection.getresponse()
                        data = response.read()
                        connection.close()
                        assert response.status == 200 and b"hermes-mitmproxy-fixture" in data
                        break
                    except OSError:
                        if time.monotonic() >= deadline or proxy.poll() is not None:
                            raise
                        time.sleep(0.2)
            finally:
                terminate(proxy)
                terminate(server)
        assert capture.is_file() and capture.stat().st_size > 0
        result = mcp.call("inspect_web_network_capture", {"capture_path": str(capture), "format": "mitmproxy"})
        contains(result, "sdk-mitm-fixture.txt")
        return "Recorded a real local HTTP proxy transaction and decoded its saved mitmproxy flow"

    try:
        test("cli", cli)
        from cli_cases import run_cli_cases
        run_cli_cases(command, output, work, test)
        test("full-source", full_source)
        mcp = MCP(command + ["mcp"], output)
        # Initialization is required even when only an individual operation is selected.
        if selected is not None and "mcp-catalog" not in selected:
            catalog()
        test("mcp-catalog", catalog)
        for name, fn in [("javascript", javascript), ("archive", archive_test), ("evidence", evidence_test),
                         ("objdump", objdump), ("binary-layout", binary_layout), ("rizin", rizin),
                         ("provider-no-fallback", provider_no_fallback),
                         ("gdb", gdb), ("rizin-debugger", rizin_debugger), ("frida", frida), ("frida-injection", frida_injection), ("sqlite", sqlite_test),
                         ("managed", managed), ("android", android), ("apktool", apktool),
                         ("javascript-recovery", javascript_recovery), ("wasm", wasm_test),
                         ("firmware", firmware_test), ("firmware-extract", firmware_extract), ("firmware-ext2", firmware_ext2),
                         ("runtime", runtime), ("browser", browser), ("browser-scenario", lambda: browser("scenario")),
                         ("web-runtime", lambda: browser("runtime")), ("web-export", lambda: browser("export")),
                         ("web-source", lambda: browser("source")), ("web-modules", lambda: browser("modules")), ("process", process_capture),
                         ("mitmproxy", mitmproxy), ("kuna", kuna), ("ghidra", native)]:
            test(name, fn)
        if args.import_bundle:
            test("evidence-import", evidence_import)
        from static_cases import run_static_cases
        run_static_cases(mcp, work, test, package_root=Path(args.package_root))
        from external_cases import run_external_cases
        run_external_cases(mcp, work, test, unavailable=Unavailable)
        def tshark_policy():
            from external_cases import _write_pcap
            pcap = work / "sdk-policy-network.pcap"
            _write_pcap(pcap)
            return json.loads(run(["python3", str(Path(__file__).with_name("tshark_policy_case.py")), "--pcap", str(pcap), "--output", str(output / "tshark-policy")]))
        test("tshark-policy", tshark_policy)
        from frida_lifecycle_case import run_frida_lifecycle
        test("frida-process-lifecycle", lambda: run_frida_lifecycle(Path(args.package_root), output, work))
        from adb_case import run_adb_case
        test("adb-initialization", lambda: run_adb_case(command, output / "adb-initialization"))
        from reconstruction_case import run_reconstruction_case
        test("reconstruction-verification", lambda: run_reconstruction_case(mcp, work))
        from electron_cases import run_electron_cases
        run_electron_cases(command, output, work, test, Unavailable, MCP)
        from cutter_case import run_cutter_case
        run_cutter_case(command, output, work, test, Unavailable, MCP, Path(args.package_root))
        from desktop_cases import run_desktop_cases, run_desktop_build_case
        run_desktop_cases(command, output, work, test, Unavailable, Path(args.package_root), node_command=shutil.which(args.node) or args.node)
        run_desktop_build_case(command, output, work, test, Unavailable, Path(args.package_root), node_command=shutil.which(args.node) or args.node)
        from container_format_cases import run_container_format_cases
        run_container_format_cases(mcp, work, test)
        from firmware_format_cases import run_firmware_format_cases
        run_firmware_format_cases(mcp, work, test)
        from classification_format_cases import run_classification_format_cases
        run_classification_format_cases(mcp, work, test, package_root=Path(args.package_root), node=shutil.which(args.node) or args.node)
    finally:
        if mcp:
            mcp.close()
        if selected is not None:
            for missing in sorted(selected - {r["test"] for r in results}):
                results.append({"test": missing, "status": "fail", "reason": "Requested test was not registered or did not run"})
        (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    shutdowns = [{"path": str(path.relative_to(output)), **json.loads(path.read_text())}
                 for path in sorted(output.rglob("mcp-shutdown.json"))]
    shutdown_errors = [row for row in shutdowns
                       if row.get("exit_code") != 0 or row.get("mode") != "stdin-eof"]
    shutdown_ok = bool(shutdowns) and not shutdown_errors
    (output / "mcp-shutdown-validation.json").write_text(json.dumps({
        "status": "pass" if shutdown_ok else "fail", "receipts": shutdowns,
        "errors": shutdown_errors}, indent=2) + "\n")
    failures = [r for r in results if r["status"] == "fail" or (r["status"] == "unavailable" and r["test"] in required)]
    raise SystemExit(1 if failures or not shutdown_ok else 0)


if __name__ == "__main__":
    main()
