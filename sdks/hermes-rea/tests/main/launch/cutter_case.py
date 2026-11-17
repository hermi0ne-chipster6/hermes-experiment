"""Exercise a real Cutter GUI and the unchanged upstream local bridge plugin."""
import hashlib
import os
from pathlib import Path
import selectors
import shlex
import shutil
import subprocess
import time

from functional import normalized, terminate


def run_cutter_case(command, output, work, test, unavailable, mcp_class, package_root):
    def cutter():
        executable = os.environ.get("REA_TEST_CUTTER") or shutil.which("cutter")
        if not executable:
            raise unavailable("Packaged Cutter executable is unavailable")
        xvfb_command, compiler = shutil.which("Xvfb"), shutil.which("gcc")
        if not xvfb_command or not compiler:
            raise unavailable("Cutter fixture requires Xvfb and gcc")
        case = output / "cutter"
        case.mkdir(exist_ok=True)
        data = case / "data"
        plugin = data / "rizin/cutter/plugins/python/rea_bridge.py"
        plugin.parent.mkdir(parents=True, exist_ok=True)
        original = package_root / "bridge/cutter/rea_bridge.py"
        assert original.is_file(), original
        shutil.copyfile(original, plugin)
        assert plugin.read_bytes() == original.read_bytes(), "Fixture bridge differs from upstream"
        bridge = case / "bridge"
        bridge.mkdir(mode=0o700, exist_ok=True)
        bridge.chmod(0o700)
        source, binary = work / "cutter-fixture.c", work / "cutter-fixture"
        source.write_text("int sdk_cutter_add(int x,int y){return x+y;} int main(void){return sdk_cutter_add(2,3)==5?0:1;}\n")
        subprocess.run([compiler, "-g", "-O0", "-rdynamic", "-o", str(binary), str(source)], check=True, capture_output=True, timeout=60)
        digest = hashlib.sha256(binary.read_bytes()).hexdigest()
        xvfb = child = mcp = None
        try:
            with (case / "xvfb.stderr").open("wb") as xerrors, (case / "cutter.stderr").open("wb") as errors:
                xvfb = subprocess.Popen([xvfb_command, "-displayfd", "1", "-screen", "0", "1024x768x24", "-nolisten", "tcp"], stdout=subprocess.PIPE, stderr=xerrors)
                with selectors.DefaultSelector() as ready:
                    ready.register(xvfb.stdout, selectors.EVENT_READ)
                    assert ready.select(15), "Xvfb did not allocate a display"
                display = xvfb.stdout.readline().decode().strip()
                assert display.isdigit(), "Invalid Xvfb display"
                environment = dict(os.environ, DISPLAY=":" + display, XDG_DATA_HOME=str(data),
                                   XDG_CONFIG_HOME=str(case / "config"), REA_CUTTER_BRIDGE_DIR=str(bridge))
                child = subprocess.Popen(shlex.split(executable) + ["--no-output-redirect", "-A", "0", str(binary)],
                                         env=environment, stdout=subprocess.DEVNULL, stderr=errors)
                mcp = mcp_class(["env", f"REA_CUTTER_BRIDGE_DIR={bridge}", *command, "mcp"], case)
                mcp.request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "hermes-sdk-cutter-test", "version": "1"}})
                mcp.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                deadline = time.monotonic() + 45
                session, discovery = None, None
                while time.monotonic() < deadline:
                    assert child.poll() is None, f"Cutter exited {child.returncode}; see cutter.stderr"
                    discovery = mcp.call("list_cutter_sessions")
                    session = next((item for item in discovery["sessions"] if item["current_file"] == str(binary)), None)
                    if session:
                        break
                    time.sleep(0.3)
                assert session, f"Real plugin did not expose owned document; discovery={discovery}; see cutter.stderr"
                assert discovery["bridge_directory_security"] == "private_verified", discovery
                assert session["bridge_source"] == "packaged", session
                generation = session["document_generation"]

                def query(statement):
                    result = normalized(mcp.call("cutter_command", {"session_id": session["session_id"],
                        "expected_generation": generation, "command": statement, "json": True}))
                    assert result["execution_state"] == "complete" and result["error"] is None, result
                    assert result["current_file"] == str(binary) and result["document_generation"] == generation, result
                    assert result["output_truncated"] is False, result
                    return result["output"]

                identity = query("ij")
                assert identity["bin"]["arch"] == "x86" and identity["bin"]["bits"] == 64, identity
                symbols = query("isj")
                assert any(item.get("name") == "sdk_cutter_add" for item in symbols), symbols
                instructions = query("pdj 12 @ sym.sdk_cutter_add")
                assert any(item.get("type") == "add" for item in instructions) and any(item.get("type") == "ret" for item in instructions), instructions
                assert hashlib.sha256(binary.read_bytes()).hexdigest() == digest, "Cutter test changed the owned input"
                terminate(child)
                child = None
                closed = mcp.call("list_cutter_sessions")
                assert not closed["sessions"], closed
                return {"cutter_version": session["cutter_version"], "bridge_source": session["bridge_source"],
                        "document_generation": generation, "fixture_sha256_before_and_after": digest,
                        "assertions": ["private authenticated local bridge", "ELF x86-64 metadata", "exact sdk_cutter_add symbol", "actual add/ret disassembly", "terminated owned GUI session"],
                        "identity_scope": "Upstream Cutter identity remains partial; input hash verified locally by fixture"}
        finally:
            if child:
                terminate(child)
            if mcp:
                mcp.close()
            if xvfb:
                terminate(xvfb)

    test("cutter", cutter)
