"""Real caller-owned Electron targets; runtime download is test-only."""
import json
import hashlib
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import time

from functional import free_port, normalized, terminate, wait_json


def run_electron_cases(command, output, work, test, unavailable, mcp_class):
    def electron(active):
        executable = Path(os.environ.get("REA_TEST_ELECTRON", "/var/lib/hermes-rea/work/electron-fixture/electron"))
        if not executable.is_file():
            raise unavailable("Pinned caller-owned Electron target absent: run install_electron_fixture.py or set REA_TEST_ELECTRON")
        xvfb_command = shutil.which("Xvfb")
        if not xvfb_command:
            raise unavailable("Electron fixture requires Xvfb")
        case = output / ("electron-active" if active else "electron-passive")
        case.mkdir(exist_ok=True)
        app = work / "owned-electron-app"
        app.mkdir(exist_ok=True)
        (app / "package.json").write_text('{"name":"hermes-owned-electron-fixture","version":"1.0.0","main":"main.cjs"}')
        (app / "main.cjs").write_text("const {app,BrowserWindow,ipcMain}=require('electron');\nconst path=require('path');\n"
            "ipcMain.handle('sdk-electron-marker',()=> 'hermes-electron-clicked');\n"
            "app.whenReady().then(()=>{const win=new BrowserWindow({width:640,height:480,webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,sandbox:true}});win.loadFile(path.join(__dirname,'index.html'));});\n"
            "app.on('window-all-closed',()=>app.quit());\n")
        (app / "preload.cjs").write_text("const {contextBridge,ipcRenderer}=require('electron');contextBridge.exposeInMainWorld('sdk',{invoke:()=>ipcRenderer.invoke('sdk-electron-marker')});\n")
        (app / "index.html").write_text('<!doctype html><title>Hermes Electron Fixture Ready</title><h1 id="marker">hermes-electron-fixture</h1><button id="run">Run owned IPC fixture</button><script src="renderer.js"></script>')
        (app / "renderer.js").write_text("document.querySelector('#run').addEventListener('click',async()=>{document.querySelector('#marker').textContent=await window.sdk.invoke();});\n")
        xvfb = child = mcp = None
        sandbox_mode, sandbox_failure = "enabled", None
        try:
            with (case / "xvfb.stderr").open("wb") as errors:
                xvfb = subprocess.Popen([xvfb_command, "-displayfd", "1", "-screen", "0", "1024x768x24", "-nolisten", "tcp"], stdout=subprocess.PIPE, stderr=errors)
                with selectors.DefaultSelector() as ready:
                    ready.register(xvfb.stdout, selectors.EVENT_READ)
                    assert ready.select(15), "Xvfb did not allocate a display"
                display = xvfb.stdout.readline().decode().strip()
                assert display.isdigit(), f"Xvfb display allocation failed: {display}"
                environment = dict(os.environ, DISPLAY=":" + display, XDG_CONFIG_HOME=str(case / "config"))
                mcp = mcp_class(["env", f"DISPLAY=:{display}", f"XDG_CONFIG_HOME={case / 'config'}", *command, "mcp"], case)
                mcp.request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "hermes-sdk-electron-test", "version": "1"}})
                mcp.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                if active:
                    arguments = {"executable_path": str(executable), "application_path": str(app),
                        "actions": [{"step_id": "owned-ipc-click", "kind": "click", "selector": "#run"}, {"step_id": "settle", "kind": "wait", "duration_ms": 250}]}
                    try:
                        result = normalized(mcp.call("capture_electron_scenario", arguments, timeout=240))
                    except RuntimeError as error:
                        diagnostics = str(error)
                        if not any(marker in diagnostics.lower() for marker in ("sandbox", "operation not permitted", "namespace")):
                            raise
                        sandbox_failure = diagnostics
                        sandbox_mode = "disabled-for-synthetic-fixture-after-host-refusal"
                        result = normalized(mcp.call("capture_electron_scenario", dict(arguments, args=["--no-sandbox"]), timeout=240))
                    assert result["application"]["cleanup"] == "terminated-owned-process", result
                    assert all(action["status"] == "completed" for action in result["actions"]), result["actions"]
                    assert any(event.get("channel") == "sdk-electron-marker" and event["kind"] == "main-handler-invocation" for event in result["ipc"]["events"]), result["ipc"]
                    detail = {"ipc_events": len(result["ipc"]["events"]), "electron_version": result["application"]["electron_version"], "cleanup": result["application"]["cleanup"]}
                else:
                    port = free_port()
                    endpoint = f"http://127.0.0.1:{port}"
                    with (case / "electron.stderr").open("wb") as stderr:
                        args = [str(executable), f"--remote-debugging-port={port}", str(app)]
                        child = subprocess.Popen(args, env=environment, stdout=subprocess.DEVNULL, stderr=stderr)
                        try:
                            targets = wait_json(endpoint + "/json/list", child)
                        except (RuntimeError, TimeoutError):
                            terminate(child)
                            stderr.flush()
                            diagnostics = (case / "electron.stderr").read_text(errors="replace")
                            if not any(marker in diagnostics.lower() for marker in ("sandbox", "operation not permitted", "namespace")):
                                raise
                            sandbox_failure = diagnostics[-2000:]
                            sandbox_mode = "disabled-for-synthetic-fixture-after-host-refusal"
                            child = subprocess.Popen(args[:-1] + ["--no-sandbox", str(app)], env=environment, stdout=subprocess.DEVNULL, stderr=stderr)
                            targets = wait_json(endpoint + "/json/list", child)
                        deadline = time.monotonic() + 15
                        while time.monotonic() < deadline:
                            if any(target.get("url") == (app / "index.html").as_uri() for target in targets):
                                break
                            time.sleep(0.1)
                            targets = wait_json(endpoint + "/json/list", child)
                        listing = normalized(mcp.call("list_electron_targets", {"cdp_endpoint": endpoint}))
                        target = next(target for target in listing["targets"] if target["file_path"] == str(app / "index.html"))
                        result = normalized(mcp.call("inspect_electron_page", {"cdp_endpoint": endpoint, "target_id": target["target_id"], "include_script_sources": True}))
                        assert result["target"]["title"] == "Hermes Electron Fixture Ready", result["target"]
                        # Passive Electron observation intentionally retains DOM
                        # structure/lengths, not text values. Check that contract
                        # and the exact explicitly requested runtime source.
                        assert {node["node_name"] for node in result["dom"]["nodes"]} >= {"H1", "BUTTON", "SCRIPT"}, result["dom"]
                        script = next(item for item in result["scripts"]["items"] if item["file_path"] == str(app / "renderer.js"))
                        artifact = script["source"]["artifact"]
                        expected = (app / "renderer.js").read_bytes()
                        assert artifact["text"].encode() == expected and artifact["sha256"] == hashlib.sha256(expected).hexdigest(), artifact
                        detail = {"target_id": target["target_id"], "assertion": "Real Electron file-page DOM structure and exact retained renderer source", "renderer_sha256": artifact["sha256"]}
                return dict(detail, sandbox_mode=sandbox_mode, sandbox_failure=sandbox_failure)
        finally:
            if child:
                terminate(child)
            if mcp:
                mcp.close()
            if xvfb:
                terminate(xvfb)

    test("electron-passive", lambda: electron(False))
    test("electron-active", lambda: electron(True))
