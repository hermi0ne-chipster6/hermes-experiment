"""Real packet, logic-recording and saved-core provider acceptance cases.

Fixtures are synthesized locally, with no acquisition or external network access.
GDB records a deliberately faulting, source-owned child without changing kernel
core settings. REA subsequently consumes only the saved core.
"""

import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import signal
import socket
import struct
import subprocess


class ExternalUnavailable(Exception):
    """A fixture cannot be generated under this environment's restrictions."""


def _normalized(evidence):
    assert "evidence_id" in evidence, evidence
    return evidence["normalized_result"]


def _checksum(data):
    if len(data) % 2:
        data += b"\0"
    value = sum(struct.unpack(f"!{len(data) // 2}H", data))
    while value >> 16:
        value = (value & 0xFFFF) + (value >> 16)
    return (~value) & 0xFFFF


def _write_pcap(path):
    # One valid Ethernet/IPv4/UDP DNS query; documentation IP ranges only.
    labels = b"".join(bytes([len(label)]) + label for label in (b"sdk", b"hermes", b"test"))
    dns = struct.pack("!6H", 0x5123, 0x0100, 1, 0, 0, 0) + labels + b"\0" + struct.pack("!HH", 1, 1)
    udp = struct.pack("!HHHH", 53000, 53, 8 + len(dns), 0) + dns
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(udp), 1, 0, 64, 17, 0,
                     socket.inet_aton("192.0.2.10"), socket.inet_aton("198.51.100.20"))
    ip = ip[:10] + struct.pack("!H", _checksum(ip)) + ip[12:]
    frame = bytes.fromhex("0200000000020200000000010800") + ip + udp
    data = struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    data += struct.pack("<IIII", 1700000000, 0, len(frame), len(frame)) + frame
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _write_uart(path):
    # 9600-baud 8N1 UART sampled at 1 MHz, idle high, expected bytes "SDK".
    lines = ["$timescale 1 us $end", "$scope module logic $end",
             "$var wire 1 ! RX $end", "$upscope $end", "$enddefinitions $end", "#0", "1!"]
    tick = 1000
    for byte in b"SDK":
        for bit in [0] + [(byte >> i) & 1 for i in range(8)] + [1]:
            lines.extend([f"#{tick}", f"{bit}!"])
            tick += 104
        tick += 208
    lines.extend([f"#{tick + 1000}", "1!"])
    data = ("\n".join(lines) + "\n").encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _fixture_command(args, cwd, log_path):
    process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, start_new_session=True)
    try:
        output, _ = process.communicate(timeout=45)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        output, _ = process.communicate()
        log_path.write_text(output)
        raise ExternalUnavailable(f"Core fixture command timed out: {args[0]}; diagnostics: {log_path}")
    log_path.write_text(output)
    return process.returncode, output


def _record_core(work):
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ExternalUnavailable("Core fixture requires Linux x86_64 (the SDK's target platform)")
    compiler = shutil.which("gcc")
    gdb = os.environ.get("REA_PWNDBG_GDB") or shutil.which("gdb")
    if not compiler or not gdb:
        raise ExternalUnavailable("Core fixture requires gcc and gdb")
    root = work / "recorded-crash-fixture"
    root.mkdir(exist_ok=True)
    source = root / "fixture.c"
    source.write_text('int main(void) {\n'
                      '  __asm__ volatile("movabs $0x1122334455667788, %%rdi\\n\\t"\n'
                      '                   "mov $0x123, %%rax\\n\\t"\n'
                      '                   "movb $0x2a, (%%rax)" ::: "rax", "rdi", "memory");\n'
                      '  return 0;\n}\n')
    code, output = _fixture_command([compiler, "-g", "-O0", "-fno-pie", "-no-pie", "fixture.c", "-o", "fixture-program"],
                                    root, root / "compile.log")
    assert code == 0, output
    core = root / "recording.core"
    core.unlink(missing_ok=True)
    commands = ["set auto-load off", "set debuginfod enabled off", "set startup-with-shell off",
                "set disable-randomization off", "file ./fixture-program", "run",
                "generate-core-file ./recording.core"]
    args = [gdb, "-nx", "-nh", "--batch", "--quiet"]
    for command in commands:
        args.extend(["-ex", command])
    code, output = _fixture_command(args, root, root / "gdb.log")
    if code != 0 or not core.is_file():
        diagnostics = {}
        for name in ("/proc/sys/kernel/core_pattern", "/proc/sys/kernel/yama/ptrace_scope"):
            path = pathlib.Path(name)
            diagnostics[name] = path.read_text().strip() if path.exists() else "absent"
        raise ExternalUnavailable(f"GDB could not record owned fixture (exit {code}): {output}; kernel settings: {diagnostics}")
    assert "SIGSEGV" in output, output
    assert core.read_bytes()[:4] == b"\x7fELF", "GDB did not produce an ELF core"
    return core


def run_external_cases(mcp, work, test, unavailable=RuntimeError):
    """Register independent cases; the callback decides which cases to execute."""
    pcap = work / "sdk-network.pcap"
    uart = work / "sdk-uart.vcd"
    core_cache = {}

    def packet_capture():
        digest = _write_pcap(pcap)
        evidence = mcp.call("inspect_packet_capture", {
            "path": str(pcap), "fields": ["ip.src", "ip.dst", "udp.srcport", "udp.dstport", "dns.qry.name"],
            "display_filter": "dns", "match_limit": None,
        })
        report = _normalized(evidence)
        assert report["artifact"]["sha256"] == digest, report
        assert report["packets"] == [{"frame.number": ["1"], "ip.src": ["192.0.2.10"],
                                       "ip.dst": ["198.51.100.20"], "udp.srcport": ["53000"],
                                       "udp.dstport": ["53"], "dns.qry.name": ["sdk.hermes.test"]}], report
        assert report["output_window"]["matching_packets"] == 1, report
        return {"evidence_id": evidence["evidence_id"], "packets": report["packets"],
                "tshark": report["tool"]["version_banner"], "sha256": digest}

    def pcap_summary():
        digest = _write_pcap(pcap)
        evidence = mcp.call("inspect_pcap_capture", {"path": str(pcap)})
        report = _normalized(evidence)
        assert report["target"]["sha256"] == digest, report
        assert report["packet_count"] == 1, report
        endpoints = {(item["address"], item["port"], item["packet_count"]) for item in report["endpoints"]}
        # The upstream summary aggregates IP endpoints without transport ports.
        assert ("192.0.2.10", None, 1) in endpoints, report
        assert ("198.51.100.20", None, 1) in endpoints, report
        assert any(query["query"] == "sdk.hermes.test" for query in report["dns_queries"]), report
        assert any("dns" in item["protocol"].split(":") for item in report["protocol_distribution"]), report
        return {"evidence_id": evidence["evidence_id"], "packet_count": report["packet_count"],
                "endpoints": report["endpoints"], "dns_queries": report["dns_queries"], "client": report["client"]}

    def signal_recording():
        digest = _write_uart(uart)
        evidence = mcp.call("decode_signal_recording", {"path": str(uart), "input_format": "vcd",
                            "decoders": "uart:rx=RX:baudrate=9600", "annotations": "uart=rx-data", "line_limit": None})
        report = _normalized(evidence)
        assert report["artifact"]["sha256"] == digest, report
        decoded = re.findall(r"\d+-\d+ uart-1: ([0-9a-f]{2})\s*(?:\n|$)", report["annotations_text"], re.IGNORECASE)
        assert [int(value, 16) for value in decoded] == list(b"SDK"), report
        return {"evidence_id": evidence["evidence_id"], "decoded_ascii": "SDK",
                "annotations": report["annotations_text"], "sigrok": report["tool"]["version_banner"]}

    def recorded_crash(debugger=False):
        if "path" not in core_cache:
            try:
                core_cache["path"] = _record_core(work)
            except ExternalUnavailable as error:
                raise unavailable(str(error)) from error
        path = core_cache["path"]
        evidence = mcp.call("inspect_recorded_crash", {"path": str(path), "include_debugger_context": debugger})
        report = _normalized(evidence)
        assert report["artifact"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest(), report
        assert report["architecture"] == "x86_64-little-endian", report
        assert report["target_execution"] == "not-performed", report
        assert any(register["name"] == "rdi" and int(register["value"], 16) == 0x1122334455667788
                   for thread in report["threads"] for register in thread["registers"]), report
        assert any(item["number"] == 11 and item["fault_address"] == "0x123" for item in report["signals"]), report
        detail = {"evidence_id": evidence["evidence_id"], "threads": len(report["threads"]),
                  "signals": report["signals"], "known_register": "rdi=0x1122334455667788"}
        if debugger:
            context = report["debugger"]
            assert context["status"] == "available", context
            assert context["connection"] == "core", context
            assert context["pwndbg_version"].startswith("2026.09.15"), context
            assert context["executable"] is None, context
            assert len(context["maps"]) > 0, context
            detail.update({"pwndbg_version": context["pwndbg_version"], "gdb_version": context["gdb_version"],
                           "core_maps": len(context["maps"])})
        else:
            assert report["debugger"]["status"] == "not-requested", report
        return detail

    def ilspy_reconstruction():
        compiler = shutil.which("mcs")
        executable = os.environ.get("REA_ILSPY_CMD_PATH") or shutil.which("ilspycmd")
        if not compiler or not executable:
            raise unavailable("ILSpy reconstruction fixture requires mcs and configured ilspycmd")
        source = work / "IlspyFixture.cs"
        assembly = work / "IlspyFixture.dll"
        source.write_text('namespace HermesSdk { public class IlspyMarker { '
                          'public static string Greet() { return "hermes-ilspy-reconstruction"; } } }\n')
        subprocess.run([compiler, "-target:library", f"-out:{assembly}", str(source)],
                       check=True, capture_output=True, text=True, timeout=60)
        outputs = {}
        for name, arguments in [
            ("version", ["--version"]),
            ("classes", ["--disable-updatecheck", "-l", "c", str(assembly)]),
            ("csharp", ["--disable-updatecheck", "--type", "HermesSdk.IlspyMarker", str(assembly)]),
        ]:
            process = subprocess.run([executable] + arguments, capture_output=True, text=True, timeout=90)
            (work / f"ilspy-{name}.log").write_text(process.stdout + process.stderr)
            assert process.returncode == 0, {"command": arguments, "stdout": process.stdout, "stderr": process.stderr}
            outputs[name] = process.stdout
        assert "11.2.0.10050" in outputs["version"], outputs["version"]
        assert "Class HermesSdk.IlspyMarker" in outputs["classes"], outputs["classes"]
        assert 'return "hermes-ilspy-reconstruction";' in outputs["csharp"], outputs["csharp"]
        assert "Greet()" in outputs["csharp"] and "Error" not in outputs["csharp"], outputs["csharp"]
        members = mcp.call("inspect_managed_members", {"path": str(assembly)})
        method = next(item for item in _normalized(members)["methods"] if item["name"] == "Greet")
        evidence = mcp.call("import_managed_reconstruction", {
            "static_members": {"kind": "retained-evidence", "evidence_id": members["evidence_id"]},
            "decompiler": {"name": "ilspycmd", "version": "11.2.0.10050", "family": "ilspy",
                           "executable_sha256": hashlib.sha256(pathlib.Path(executable).read_bytes()).hexdigest(),
                           "options": ["--disable-updatecheck", "--type", "HermesSdk.IlspyMarker"]},
            "methods": [{"token": method["token"], "signature_sha256": method["signature"]["raw_sha256"],
                         "normalized_il_sha256": method["body"]["normalized_il_sha256"],
                         "reconstruction": {"kind": "decompiled-csharp", "language": "csharp", "text": outputs["csharp"]}}],
            "notes": ["Real source-owned ILSpy oracle; C# is reconstruction inference, not canonical observation."],
        })
        report = _normalized(evidence)
        validation = report["methods"][0]["validation"]
        assert validation["canonical_observation"] is False, report
        assert validation["confidence_floor"] == "inference", report
        assert "hermes-ilspy-reconstruction" in json.dumps(report), report
        return {"evidence_id": evidence["evidence_id"], "source_evidence_id": members["evidence_id"],
                "version": outputs["version"].strip(), "method": method["token"],
                "decompiled_csharp_sha256": hashlib.sha256(outputs["csharp"].encode()).hexdigest(),
                "canonical_observation": False, "confidence_floor": "inference"}

    def desktop_clients():
        docker = os.environ.get("REA_DOCKER_COMMAND") or shutil.which("docker")
        agent = os.environ.get("REA_AGENT_ENV_COMMAND") or shutil.which("agent-env")
        if not docker or not agent:
            raise unavailable("Desktop client initialization requires Docker CLI and agent-env")
        versions = {}
        for label, arguments, expected in [
            ("docker", [docker, "--version"], "29.1.3"),
            ("buildx", [docker, "buildx", "version"], "0.30.1"),
            ("compose", [docker, "compose", "version"], "2.40.3"),
            ("agentenv", [agent, "--version"], "0.9.1485"),
        ]:
            result = subprocess.run(arguments, capture_output=True, text=True, timeout=60)
            assert result.returncode == 0, {"component": label, "stdout": result.stdout, "stderr": result.stderr}
            assert expected in result.stdout, (label, result.stdout)
            versions[label] = result.stdout.strip()
        # REA's agentEnvInterpreter falls back to python3 beside the resolved runner.
        interpreter = pathlib.Path(agent).resolve().parent / "python3"
        result = subprocess.run([str(interpreter), "-I", "-c",
            'import json; from importlib.metadata import version; '
            'from agent_env.bundle import run_bundle; import agentenv_protocol; '
            'print(json.dumps({"framework":version("agentenv-framework"), '
            '"protocol":version("agentenv-framework-protocol"), "bundle_runner":callable(run_bundle)}))'],
            capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        imported = json.loads(result.stdout)
        assert imported == {"framework": "0.9.1485", "protocol": "0.1.500", "bundle_runner": True}, imported
        return {"versions": versions, "python_imports": imported,
                "scope": "Client initialization only; no Docker daemon, container build, remote endpoint, or model run tested"}

    test("packet-capture", packet_capture)
    test("pcap-summary", pcap_summary)
    test("signal-recording", signal_recording)
    test("recorded-crash", recorded_crash)
    test("pwndbg-core", lambda: recorded_crash(debugger=True))
    test("ilspy-reconstruction", ilspy_reconstruction)
    test("desktop-clients", desktop_clients)
