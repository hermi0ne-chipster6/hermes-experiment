"""Semantic static-provider checks; fixtures are generated locally, never executed by REA."""
import hashlib
import base64
import gzip
import json
import os
from pathlib import Path
import py_compile
import struct
import subprocess
import tarfile
import zipfile
import zlib


def run_static_cases(mcp, work, test, package_root=None):
    def inspect(name, path, **options):
        evidence = mcp.call(name, {"path": str(path), **options})
        assert evidence.get("evidence_id"), f"{name} did not retain Evidence"
        return evidence.get("normalized_result", evidence.get("result", evidence))

    def command(*argv):
        subprocess.run(argv, check=True, capture_output=True, timeout=90)

    def native():
        binary = work / "static-native"
        if not binary.exists():
            source = work / "static-native.c"
            source.write_text('#include <stdio.h>\n'
                              'int hermes_static_export(int x) { return x + 37; }\n'
                              '__attribute__((constructor)) static void hermes_initializer(void) {}\n'
                              'int main(void) { puts("hermes-static-fixture"); return 0; }\n')
            command("cc", "-g", "-O0", "-fPIE", "-pie", "-rdynamic", "-Wl,--build-id=sha1",
                    "-Wl,-z,relro,-z,now", str(source), "-o", str(binary))
        return binary

    def check_digest(result, path):
        assert result["artifact"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()

    def elf_notes():
        path = native()
        result = inspect("inspect_elf_notes", path)
        check_digest(result, path)
        ids = [entry["gnu"]["build_id_hex"] for entry in result["entries"]
               if entry.get("gnu") and entry["gnu"].get("build_id_hex")]
        assert ids and all(len(value) == 40 for value in ids), "Missing SHA1 GNU build ID"
        assert result["coverage"]["status"] == "complete"
        return {"gnu_build_ids": ids}

    def native_exports():
        result = inspect("inspect_native_exports", native(), detail="complete")
        assert result["format"] == "elf"
        assert any(row.get("name") == "hermes_static_export" for row in result["exports"])
        return {"export": "hermes_static_export", "count": len(result["exports"])}

    def binary_hardening():
        result = inspect("inspect_binary_hardening", native())
        assert result["format"] == "elf"
        assert result["images"][0]["status"] == "parsed"
        rows = result["images"][0]["rows"]
        states = {row["property"]: row["state"] for row in rows}
        assert all(states.get(name) == "enabled" for name in ("pie", "nx", "relro")), states
        return {"properties": rows}

    def native_initializers():
        result = inspect("inspect_native_initializers", native())
        assert result["format"] == "elf"
        assert result["entries"], "Constructor fixture produced no initializer entries"
        assert "hermes_initializer" in json.dumps(result["entries"])
        return {"initializers": len(result["entries"])}

    def elf_unwind():
        result = inspect("inspect_elf_unwind_ranges", native())
        assert result["ranges"], "Unwind-enabled fixture produced no FDE ranges"
        assert "hermes_static_export" in json.dumps(result["ranges"])
        return {"ranges": len(result["ranges"])}

    def elf_dependencies():
        result = inspect("inspect_elf_dependencies", native(), detail="complete")
        assert "libc.so.6" in json.dumps(result["needed"])
        assert "puts" in json.dumps(result["imports"])
        return {"needed": result["needed"]}

    def dwarf():
        result = inspect("inspect_dwarf_units", native())
        assert result["debug_info"] == "present" and result["total_units"] >= 1
        assert "static-native.c" in json.dumps(result["units"])
        return {"compile_units": result["total_units"]}

    def elf_debug_link():
        original = native()
        debug = work / "static-native.debug"
        stripped = work / "static-native.stripped"
        command("objcopy", "--only-keep-debug", str(original), str(debug))
        command("objcopy", "--strip-debug", str(original), str(stripped))
        command("objcopy", "--add-gnu-debuglink=" + str(debug), str(stripped))
        result = inspect("inspect_elf_debug_link", stripped, candidate_path=str(debug))
        assert "static-native.debug" in json.dumps(result["debuglink"])
        assert result["verification"]["status"] == "matches", result["verification"]
        return {"verification": result["verification"]}

    def entropy():
        path = work / "entropy.bin"
        path.write_bytes(bytes(256) + bytes(range(256)))
        result = inspect("inspect_byte_entropy", path, block_size=256, detail="complete")
        check_digest(result, path)
        assert [row["entropy"] for row in result["blocks"]] == [0, 8]
        return {"block_entropies": [0, 8]}

    def model():
        path = work / "fixture.safetensors"
        header = json.dumps({"__metadata__": {"producer": "hermes-sdk-fixture"},
                             "weights": {"dtype": "F32", "shape": [2], "data_offsets": [0, 8]}},
                            separators=(",", ":")).encode()
        header += b" " * (-len(header) % 8)
        path.write_bytes(struct.pack("<Q", len(header)) + header + struct.pack("<ff", 1.0, 2.0))
        result = inspect("inspect_model_artifact", path, hash="full", detail="complete")
        check_digest(result, path)
        assert result["format"] == "safetensors"
        tensor = result["tensors"][0]
        assert tensor["name"] == "weights" and tensor["shape"] == ["2"]
        assert tensor["byte_length"] == 8 and result["totals"]["parameter_count"] == "2"
        return {"tensor": tensor, "payload_executed": False}

    def python_pyc():
        source = work / "static_python.py"
        path = work / "static_python.pyc"
        source.write_text('def hermes_static_python(value):\n    return value + 37\n')
        py_compile.compile(str(source), cfile=str(path), doraise=True,
                           invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
        result = inspect("inspect_python_pyc", path, detail="complete")
        check_digest(result, path)
        names = [row["name"] for row in result["code_objects"]]
        assert "<module>" in names and "hermes_static_python" in names
        assert result["coverage"]["status"] == "complete"
        return {"code_objects": names, "python_source_executed": False}

    def evm():
        path = work / "evm.hex"
        # REA's public real-provider verifier uses this zero-selector dispatcher.
        bytecode = "60003560e01c630000000014601057005b00"
        path.write_text(bytecode)
        result = inspect("inspect_evm_interface", path, encoding="hex", detail="complete")
        assert result["bytecode"]["hex"] == bytecode
        assert "0x00000000" in [row["selector"] for row in result["functions"]]
        assert result["runtime_execution"] == "not-performed"
        return {"selectors": [row["selector"] for row in result["functions"]]}

    def kernel_module():
        source = work / "static-module.c"
        path = work / "static-module.ko"
        source.write_text('__attribute__((section(".modinfo"),used)) static const char info[] = '
                          '"license=GPL\\0description=hermes-sdk-fixture\\0";\n'
                          'int init_module(void) { return 0; }\nvoid cleanup_module(void) {}\n')
        command("cc", "-c", str(source), "-o", str(path))
        result = inspect("inspect_kernel_module", path)
        check_digest(result, path)
        assert "hermes-sdk-fixture" in json.dumps(result)
        assert "GPL" in json.dumps(result)
        return {"modinfo": "license=GPL;description=hermes-sdk-fixture", "module_loaded": False}

    def devicetree():
        path = work / "fixture.dtb"
        value = b"hermes,sdk-fixture\0"
        value += b"\0" * (-len(value) % 4)
        structure = struct.pack(">I", 1) + bytes(4)
        structure += struct.pack(">III", 3, len(b"hermes,sdk-fixture\0"), 0) + value
        structure += struct.pack(">II", 2, 9)
        strings = b"compatible\0"
        off_structure = 56
        off_strings = off_structure + len(structure)
        header = struct.pack(">10I", 0xD00DFEED, off_strings + len(strings), off_structure,
                             off_strings, 40, 17, 16, 0, len(strings), len(structure))
        path.write_bytes(header + bytes(16) + structure + strings)
        result = inspect("inspect_devicetree", path, detail="complete")
        check_digest(result, path)
        assert "hermes,sdk-fixture" in json.dumps(result)
        return {"root_compatible": "hermes,sdk-fixture"}

    def nuget():
        path = work / "Hermes.Fixture.1.2.3.nupkg"
        nuspec = ('<?xml version="1.0"?><package><metadata><id>Hermes.Fixture</id>'
                  '<version>1.2.3</version><authors>SDK Test</authors><description>Synthetic fixture</description>'
                  '<dependencies><group targetFramework="net8.0"><dependency id="Example.Dependency" '
                  'version="[2.0.0,3.0.0)"/></group></dependencies></metadata></package>')
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("Hermes.Fixture.nuspec", nuspec)
            archive.writestr("lib/net8.0/readme.txt", "No managed code is needed for package inventory.")
        result = inspect("inspect_nuget_nupkg", path)
        check_digest(result, path)
        assert result["identity"]["id"] == "Hermes.Fixture" and result["identity"]["version"] == "1.2.3"
        dependency = result["dependency_groups"][0]["dependencies"][0]
        assert dependency["id"] == "Example.Dependency" and dependency["version"] == "[2.0.0,3.0.0)"
        return {"package": "Hermes.Fixture", "version": "1.2.3", "dependency": "Example.Dependency"}

    def apple_ips():
        path = work / "crash.ips"
        body = {"procName": "hermes-crash-fixture", "faultingThread": 0,
                "exception": {"type": "EXC_BAD_ACCESS", "signal": "SIGSEGV"},
                "threads": [{"triggered": True, "frames": [{"imageIndex": 0, "imageOffset": 16}]}],
                "usedImages": [{"name": "Hermes", "base": 4096, "size": 256,
                                "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "arch": "arm64"}]}
        path.write_text(json.dumps({"bug_type": "309"}) + "\n" + json.dumps(body))
        result = inspect("inspect_apple_ips", path)
        check_digest(result, path)
        assert result["faulting_thread"] == 0
        assert result["threads"][0]["frames"][0]["image_index"] == 0
        assert result["images"][0]["arch"] == "arm64"
        assert "EXC_BAD_ACCESS" in json.dumps(result)
        return {"faulting_thread": 0, "image_arch": "arm64", "report_executed": False}

    def beam():
        path = work / "hermes.beam"
        u32 = lambda value: struct.pack(">I", value)
        def chunk(name, payload):
            return name.encode() + u32(len(payload)) + payload + bytes(-len(payload) % 4)
        names = ["hermes_beam", "module_info", "start", "erlang", "get_module_info"]
        atom_bytes = u32(len(names)) + b"".join(bytes([len(n)]) + n.encode() for n in names)
        def table(name, rows):
            return chunk(name, u32(len(rows)) + b"".join(u32(x) for row in rows for x in row))
        chunks = chunk("AtU8", atom_bytes) + chunk("Code", struct.pack(">5I", 16, 0, 169, 4, 2) + b"code")
        chunks += table("ExpT", [[3, 0, 2], [2, 0, 1], [2, 1, 3]])
        chunks += table("ImpT", [[4, 5, 1]]) + table("FunT", [[3, 1, 4, 0, 0, 42]])
        form = b"BEAM" + chunks
        path.write_bytes(b"FOR1" + u32(len(form)) + form)
        result = inspect("inspect_erlang_beam", path)
        check_digest(result, path)
        assert result["module"] == "hermes_beam"
        assert len(result["exports"]) == 3 and len(result["imports"]) == 1
        assert result["code"]["functions"] == 2
        assert "get_module_info" in json.dumps(result["imports"])
        return {"module": result["module"], "exports": 3, "imports": 1, "executed": False}

    def gpu():
        path = work / "hermes.ptx"
        path.write_text(".version 8.8\n.target sm_80\n.address_size 64\n"
                        ".visible .entry hermes_kernel(.param .u64 input) { .reg .b32 %r<3>; ret; }\n")
        result = inspect("inspect_gpu_code_objects", path, analysis="kernels", detail="complete")
        check_digest(result, path)
        assert any(row["kind"] == "ptx" and row["target"] == "sm_80" for row in result["objects"])
        kernel = next(row for row in result["kernels"] if row["name"] == "hermes_kernel")
        assert kernel["parameter_count"] == 1 and kernel["parameter_bytes"] == 8
        assert kernel["registers"]["virtual"] == [{"type": ".b32", "count": 3}]
        return {"kernel": kernel["name"], "parameters": 1, "gpu_execution": False}

    def rust():
        metadata = {"format": 1, "packages": [
            {"name": "hermes-dependency", "version": "1.2.3", "source": "crates.io"},
            {"name": "hermes-root", "version": "0.1.0", "source": "local", "dependencies": [0], "root": True}]}
        section = work / "rust-dep-v0"
        path = work / "rust-auditable-elf"
        section.write_bytes(zlib.compress(json.dumps(metadata).encode()))
        command("objcopy", "--add-section", ".dep-v0=" + str(section), str(native()), str(path))
        result = inspect("inspect_rust_binary", path)
        check_digest(result, path)
        audit = result["auditable_metadata"]
        assert audit["root_package_index"] == 1
        assert audit["packages"][0]["name"] == "hermes-dependency"
        assert audit["dependency_edges"] == [{"from_index": 1, "to_index": 0}]
        return {"synthetic_cargo_auditable_section": True, "root": "hermes-root", "dependency_edges": 1}

    def v8_cache():
        path = work / "cache.jsc"
        source = "function hermes_add(a,b) { return a+b; } hermes_add(1,2);"
        command("node", "-e", "require('fs').writeFileSync(process.argv[1],new (require('vm').Script)(process.argv[2],{produceCachedData:true}).createCachedData())",
                str(path), source)
        result = inspect("inspect_v8_code_cache", path)
        check_digest(result, path)
        assert result["header"]["source_length"] == len(source)
        assert result["header"]["magic_build_stable"] == 0xC0DE
        assert result["payload"]["offset"] + result["payload"]["bytes"] == path.stat().st_size
        return {"source_length": len(source), "cached_data_bytes": path.stat().st_size, "source_executed": False}

    def windows_shortcut():
        path = work / "fixture.lnk"
        # MS-SHLLINK header plus Unicode StringData, no target invocation.
        header = bytearray(76)
        struct.pack_into("<I", header, 0, 76)
        header[4:20] = bytes.fromhex("0114020000000000c000000000000046")
        struct.pack_into("<I", header, 20, 0x80 | 0x4 | 0x8 | 0x20)
        struct.pack_into("<I", header, 60, 1)
        def string(value):
            return struct.pack("<H", len(value)) + value.encode("utf-16le")
        path.write_bytes(header + string("Hermes shortcut") + string(".\\hermes.exe") + string("--fixture") + bytes(4))
        result = inspect("inspect_windows_shortcut", path)
        check_digest(result, path)
        assert result["string_data"]["arguments"]["value"] == "--fixture"
        assert result["string_data"]["relative_path"]["value"] == ".\\hermes.exe"
        assert result["header"]["show_command"]["raw"] == 1
        return {"arguments": "--fixture", "relative_path": ".\\hermes.exe", "target_executed": False}

    def upstream_fixture(name):
        return base64.b64decode(json.loads(Path(__file__).with_name("static-fixtures.json").read_text())[name])

    def il2cpp():
        path = work / "global-metadata.dat"
        path.write_bytes(upstream_fixture("il2cpp"))
        result = inspect("inspect_il2cpp_metadata", path, detail="complete")
        check_digest(result, path)
        assert result["magic"] == 0xFAB11BAF and result["metadata_version"] == 29
        assert "Assembly-CSharp.dll" in json.dumps(result["images"])
        assert "Player" in json.dumps(result["types"])
        assert "ToString" in json.dumps(result["methods"])
        return {"version": 29, "image": "Assembly-CSharp.dll", "type": "Game.Player"}

    def flutter():
        path = work / "flutter.apk"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("lib/x86_64/libapp.so", upstream_fixture("flutter"))
            archive.writestr("assets/flutter_assets/AssetManifest.json", "{}")
        build = inspect("identify_flutter_build", path)
        assert build["flutter_detected"]
        assert build["abis"][0]["libapp"]["snapshot_hash"] == "65817c30a78bb44c3dc3771876b6010a"
        result = inspect("inspect_dart_aot", path, abi="x86_64", detail="complete")
        assert result["libapp"]["snapshot_hash_sources"] == 2
        assert "package:animations/src/fade_scale_transition.dart" in result["string_pool"]["package_uris"]
        assert "dart:_http" in result["string_pool"]["dart_uris"]
        return {"abi": "x86_64", "snapshot_hash_sources": 2, "package_uri": "package:animations/src/fade_scale_transition.dart"}

    def application_projection(path, operation):
        mcp.call("open_binary", {"path": str(path)})
        try:
            inspection = mcp.call("inspect_artifact")
            evidence = mcp.call(operation, {"inventory_evidence": [inspection]})
            assert evidence.get("evidence_id")
            return evidence["normalized_result"]
        finally:
            mcp.call("close_binary")

    def apple_graph():
        path = work / "Hermes.ipa"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("Payload/Hermes.app/Info.plist", '<?xml version="1.0"?><plist version="1.0"><dict><key>CFBundleIdentifier</key><string>test.hermes.fixture</string></dict></plist>')
            archive.writestr("Payload/Hermes.app/main.js", "export const fixture = 37;")
            archive.writestr("Payload/Hermes.app/_CodeSignature/CodeResources", "Synthetic inventory entry, no signature claim")
        result = application_projection(path, "project_apple_application_graph")
        assert result["root_format"] == "ipa"
        assert "Payload/Hermes.app" in json.dumps(result["application_roots"])
        assert "Payload/Hermes.app/Info.plist" in json.dumps(result["components"]["bundle_metadata"])
        assert "Payload/Hermes.app/main.js" in json.dumps(result["components"]["javascript"])
        return {"root_format": "ipa", "application_root": "Payload/Hermes.app", "scope": "Static path inventory, no plist/signature semantic claim"}

    def harmony_graph():
        path = work / "Hermes.hap"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("module.json", json.dumps({"module": {"name": "entry", "type": "entry"}}))
            archive.writestr("ets/modules.abc", b"PANDA\x00\x00\x00" + bytes(64))
            archive.writestr("resources/rawfile/fixture.txt", "hermes-harmony")
            archive.writestr("js/main.js", "export const fixture = 37;")
        result = application_projection(path, "project_harmony_application_graph")
        assert result["root_format"] == "hap" and result["packaging_model"] == "stage"
        assert "module.json" in json.dumps(result["components"]["manifests"])
        assert "ets/modules.abc" in json.dumps(result["components"]["bytecode"])
        return {"root_format": "hap", "packaging_model": "stage", "scope": "Static paths, no Ark bytecode execution or decompilation claim"}

    def go_binary():
        source = work / "hermes_go.go"
        path = work / "hermes-go"
        source.write_text('package main\nimport "fmt"\nfunc main() { fmt.Println("hermes-go-fixture") }\n')
        environment = {**os.environ, "GOTOOLCHAIN": "local", "GOENV": "off", "GOWORK": "off", "GOPROXY": "off", "GOSUMDB": "off", "CGO_ENABLED": "0"}
        subprocess.run(["go", "build", "-buildvcs=false", "-o", str(path), str(source)],
                       env=environment, check=True, capture_output=True, timeout=180)
        result = inspect("inspect_go_binary", path)
        check_digest(result, path)
        assert "go1." in json.dumps(result)
        assert "command-line-arguments" in json.dumps(result)
        return {"fixture": "compiler-produced ELF", "build_info": "Go version and command-line-arguments module"}

    def pe_fixture(name, operation):
        path = work / (name + ".exe")
        path.write_bytes(upstream_fixture(name))
        result = inspect(operation, path)
        check_digest(result, path)
        return result

    def pe_imports():
        result = pe_fixture("pe_imports", "inspect_pe_imports")
        library = next(row for row in result["imports"] if row["name"] == "KERNEL32.dll")
        assert {row["name"] for row in library["functions"]} == {"GetProcAddress", "ExitProcess"}
        return {"library": "KERNEL32.dll", "imports": ["GetProcAddress", "ExitProcess"]}

    def pe_certificates():
        result = pe_fixture("pe_certificates", "inspect_pe_certificates")
        assert len(result["entries"]) == 1
        entry = result["entries"][0]
        assert entry["certificate_type"] == 2 and entry["revision"] == 512
        assert "REA Fixture" in json.dumps(entry["pkcs7"]["certificates"])
        assert len(entry["pkcs7"]["signers"]) == 1
        return {"pkcs7_entries": 1, "signers": 1, "certificate_subject": "REA Fixture", "trust_verified": False}

    def pe_resources():
        result = pe_fixture("pe_resources", "inspect_pe_resources")
        assert len(result["resources"]) == 5
        hashes = {row["payload"]["sha256"] for row in result["resources"]}
        assert hashlib.sha256(b"Hello").hexdigest() in hashes
        assert hashlib.sha256(b"World").hexdigest() in hashes
        return {"resources": 5, "exact_payload_hashes": ["Hello", "World"]}

    def pe_load_config():
        result = pe_fixture("pe_load_config", "inspect_pe_load_config")
        callbacks = result["tls"]["callbacks"]
        assert len(callbacks) == 3
        assert callbacks[0]["rva"] == 0x2000 and callbacks[0]["file_offset"] == 0x1600
        assert callbacks[2]["rva"] == 0x9000 and callbacks[2]["file_offset"] is None
        assert result["load_config"]["guard_flags"]["raw"] == 0x500
        return {"tls_callbacks": 3, "guard_flags": "0x500", "callbacks_executed": False}

    def kernel_config():
        section = work / "kernel-config-section"
        path = work / "vmlinux-fixture"
        config = b'CONFIG_SECURITY_SELINUX=y\nCONFIG_MODULE_SIG=m\n# CONFIG_MODULE_SIG_FORCE is not set\nCONFIG_HZ=250\n'
        section.write_bytes(b"Linux version 6.6.0 (hermes@fixture) (gcc) #1 SMP\x00" +
                            b"IKCFG_ST" + gzip.compress(config, mtime=0) + b"IKCFG_ED")
        command("objcopy", "--add-section", ".ikconfig=" + str(section), str(native()), str(path))
        result = inspect("inspect_kernel_build_config", path)
        check_digest(result, path)
        assert result["config"]["status"] == "present"
        assert result["config"]["sha256"] == hashlib.sha256(config).hexdigest()
        values = {row["name"]: row["value"] for row in result["config"]["entries"]}
        assert values == {"CONFIG_SECURITY_SELINUX": "y", "CONFIG_MODULE_SIG": "m", "CONFIG_MODULE_SIG_FORCE": None, "CONFIG_HZ": "250"}
        return {"config_options": values, "kernel_executed": False}

    def electron_fuses():
        section = work / "electron-fuse-section"
        path = work / "electron-fuse-fixture"
        states = [0x30, 0x31, 0x30, 0x30, 0x30, 0x30, 0x30, 0x31]
        section.write_bytes(b"dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX" + bytes([1, len(states), *states]))
        command("objcopy", "--add-section", ".fuses=" + str(section), str(native()), str(path))
        result = inspect("inspect_electron_fuses", path)
        check_digest(result, path)
        sentinels = result["slices"][0]["sentinels"]
        assert len(sentinels) == 1 and sentinels[0]["complete"]
        assert [fuse["raw_byte"] for fuse in sentinels[0]["fuses"]] == states
        return {"version": 1, "observed_fuse_bytes": states, "electron_executed": False}

    def analysis_view():
        model()
        path = work / "fixture.safetensors"
        parent = mcp.call("inspect_model_artifact", {"path": str(path), "hash": "full", "detail": "complete"})
        path.unlink()
        evidence = mcp.call("inspect_analysis_view", {
            "source": {"kind": "retained-evidence", "evidence_id": parent["evidence_id"]},
            "view": {"kind": "model-artifact", "collection": "tensors", "offset": 0, "limit": 1}})
        result = evidence["normalized_result"]
        assert result["parent_evidence_id"] == parent["evidence_id"]
        assert result["items"][0]["name"] == "weights"
        return {"retained_parent": parent["evidence_id"], "tensor": "weights", "source_removed_before_query": True}

    def android_graph():
        path = work / "graph.apk"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("AndroidManifest.xml", '<manifest package="test.hermes.fixture"/>')
            archive.writestr("classes.dex", b"dex\n035\x00" + bytes(104))
            archive.writestr("assets/main.js", "export const fixture=37;")
        result = application_projection(path, "project_android_application_graph")
        assert "classes.dex" in json.dumps(result["components"])
        assert "AndroidManifest.xml" in json.dumps(result["components"])
        return {"dex": "classes.dex", "manifest": "AndroidManifest.xml", "scope": "Path inventory only, separate JADX test exercises DEX decoding"}

    def apk_signature():
        path = work / "signer-metadata.apk"
        pe = upstream_fixture("pe_certificates")
        length = struct.unpack_from("<I", pe, 0x200)[0]
        cms = pe[0x208:0x200 + length]
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("AndroidManifest.xml", '<manifest package="test.hermes.fixture"/>')
            archive.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\r\n\r\n")
            archive.writestr("META-INF/CERT.SF", "Signature-Version: 1.0\r\n\r\n")
            archive.writestr("META-INF/CERT.RSA", cms)
        result = inspect("inspect_apk_signature", path, detail="complete")
        assert result["artifact"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert len(result["schemes"]["v1"]["signers"]) == 1
        assert "REA Fixture" in json.dumps(result["schemes"]["v1"]["signers"])
        return {"v1_signers": 1, "certificate_subject": "REA Fixture", "signature_authenticity_verified": False}

    def release_exposure():
        path = work / "release-fixture"
        path.mkdir(exist_ok=True)
        (path / "package.json").write_text(json.dumps({"name": "hermes-release-fixture", "version": "1.0.0", "main": "main.js"}))
        (path / "main.js").write_text("console.log(37);\n//# sourceMappingURL=main.js.map\n")
        (path / "main.js.map").write_text(json.dumps({"version": 3, "file": "main.js", "sources": ["original.ts"], "sourcesContent": ["console.log(37);"], "names": [], "mappings": "AAAA"}))
        (path / "secondary.js.map").write_text(json.dumps({"version": 3, "file": "secondary.js", "sources": ["secondary.ts"], "names": [], "mappings": "AAAA"}))
        result = inspect("audit_release_exposure", path)
        checks = {row["id"]: row for row in result["checks"]}
        assert checks["javascript.source_map_sources"]["status"] == "exposed"
        assert checks["javascript.source_maps"]["status"] == "exposed"
        return {"exposed_checks": ["javascript.source_map_sources", "javascript.source_maps"]}

    def settings():
        setting = "asar.max_header_bytes"
        before = mcp.call("inspect_analysis_settings", {"settings": [setting]})
        descriptor = before["settings"][0]
        selected = descriptor["minimum"]
        changed = mcp.call("update_analysis_settings", {"changes": [{"setting": setting, "action": "set", "value": selected}], "expected_revision": before["revision"]})
        try:
            observed = mcp.call("inspect_analysis_settings", {"settings": [setting]})
            assert observed["settings"][0]["value"] == selected
            assert observed["revision"] >= before["revision"]
        finally:
            restore = {"setting": setting, "action": "reset"} if descriptor["source"] != "runtime" else {"setting": setting, "action": "set", "value": descriptor["value"]}
            mcp.call("update_analysis_settings", {"changes": [restore]})
        return {"setting": setting, "selected_value": selected, "changed": changed["changed"], "restored": True}

    def unknown_lifecycle():
        request = {"question": "Does the Hermes fixture require an unavailable service?", "severity": "medium", "domain": "protocol",
                   "required_authority": "controlled-replay", "required_confidence": "observed", "required_environment": None,
                   "recommended_probes": [], "relationships": []}
        created = mcp.call("record_unknown", request)["result"]
        identity = created["unknown_id"]
        update = {"unknown_id": identity, "expected_revision": created["revision"], "status": "investigating", "severity": "medium",
                  "supporting_evidence_ids": [], "contradicting_evidence_ids": [], "required_authority": "controlled-replay",
                  "required_confidence": "observed", "required_environment": None, "recommended_probes": [], "relationships": [], "resolution": None}
        advanced = mcp.call("update_unknown", update)["result"]
        assert advanced["revision"] == created["revision"] + 1 and advanced["status"] == "investigating"
        listing = mcp.call("list_unknowns", {"offset": 0, "limit": 50})["result"]
        assert identity in json.dumps(listing)
        assert len(advanced["mutation_evidence_ids"]) == 2
        return {"unknown_id": identity, "revision": advanced["revision"], "mutation_evidence": 2}

    def managed_workflow():
        path = work / "managed-workflow.dll"
        path.write_bytes(upstream_fixture("managed"))
        members = mcp.call("inspect_managed_members", {"path": str(path)})
        evidence = mcp.call("project_managed_application_graph", {"managed_members": {"kind": "retained-evidence", "evidence_id": members["evidence_id"]}})
        result = evidence["normalized_result"]
        assert result["source_evidence"]["managed_members_evidence_id"] == members["evidence_id"]
        assert "HermesWorkflow" in json.dumps(result["graph"])
        assert "Greet" in json.dumps(result["graph"])
        return {"type": "Hermes.HermesWorkflow", "method": "Greet", "source_evidence": members["evidence_id"]}

    def desktop_application():
        path = work / "desktop-dotnet"
        path.mkdir(exist_ok=True)
        (path / "Hermes.dll").write_bytes(upstream_fixture("managed"))
        (path / "Hermes.runtimeconfig.json").write_text(json.dumps({"runtimeOptions": {"tfm": "net8.0", "framework": {"name": "Microsoft.NETCore.App", "version": "8.0.0"}}}))
        result = inspect("inspect_desktop_application", path, detail="complete")
        assert any(row["family"] == "dotnet" for row in result["candidates"])
        assert "Hermes.dll" in json.dumps(result["files"])
        return {"runtime_candidate": "dotnet", "assembly": "Hermes.dll", "application_executed": False}

    def application_comparison():
        path = work / "comparison-app"
        path.mkdir(exist_ok=True)
        (path / "package.json").write_text(json.dumps({"name": "hermes-comparison", "version": "1.0.0", "main": "index.js"}))
        (path / "index.js").write_text("exports.hermes_first = () => 37;\n")
        first = mcp.call("analyze_javascript_application", {"input_path": str(path)})
        (path / "index.js").write_text("exports.hermes_first = () => 38;\nexports.hermes_second = () => 39;\n")
        second = mcp.call("analyze_javascript_application", {"input_path": str(path)})
        evidence = mcp.call("compare_application_versions", {
            "left": {"kind": "retained-evidence", "evidence_id": first["evidence_id"]},
            "right": {"kind": "retained-evidence", "evidence_id": second["evidence_id"]}})
        result = evidence["normalized_result"]
        assert result["left"]["evidence_id"] == first["evidence_id"]
        assert result["right"]["evidence_id"] == second["evidence_id"]
        assert result["summary"]["changed"] + result["summary"]["added"] > 0
        assert "hermes_second" in json.dumps(result)
        return {"summary": result["summary"], "new_export": "hermes_second"}

    def api_contracts():
        path = work / "openapi.json"
        path.write_text(json.dumps({"openapi": "3.1.0", "info": {"title": "Hermes", "version": "1.0"},
                                   "paths": {"/hermes": {"get": {"operationId": "getHermes", "responses": {"200": {"description": "fixture"}}}}}}))
        result = inspect("inspect_api_contract", path, detail="complete")
        check_digest(result, path)
        assert [(row["method"], row["path"], row["declared_id"]) for row in result["operations"]] == [("GET", "/hermes", "getHermes")]
        schema = work / "schema.graphql"
        operations = work / "queries.graphql"
        schema.write_text("type Query { hermes: String! }\n")
        operations.write_text("query Hermes { hermes }\n")
        graphql = inspect("inspect_api_contract", schema, format="graphql-sdl", operations_path=str(operations), detail="complete")
        assert graphql["fields"][0]["field_key"] == "Query.hermes"
        assert graphql["definitions"][0]["name"] == "Hermes"
        assert graphql["references"][0]["state"] == "resolved"
        assert graphql["references"][0]["schema_field_id"] == graphql["fields"][0]["field_id"]
        assert graphql["summary"]["fields"] == 1
        return {"openapi": "GET /hermes", "graphql": "Query.hermes", "network_requests": False}

    def playwright_trace():
        path = work / "trace.zip"
        trace = [{"type": "context-options", "version": 10}, {"type": "screencast-frame", "file": "resources/frame", "timestamp": 1}]
        network = {"type": "resource-snapshot", "snapshot": {"request": {"method": "GET", "url": "http://captured.invalid/hermes"},
                   "response": {"status": 200, "content": {"_file": "resources/body"}}}}
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("trace.trace", "".join(json.dumps(row) + "\n" for row in trace))
            archive.writestr("trace.network", json.dumps(network) + "\n")
            archive.writestr("resources/frame", "Opaque fixture resource, not an image-validity claim")
            archive.writestr("resources/body", "hermes-recorded-response")
        result = inspect("inspect_playwright_trace", path, detail="complete")
        assert len(result["events"]) == 2
        assert "http://captured.invalid/hermes" in json.dumps(result["events"])
        assert result["summary"]["unavailable_references"] == 0
        return {"events": 2, "unavailable_references": 0, "recorded_url_contacted": False}

    def environment_export():
        path = work / "environment.har"
        body = json.dumps({"items": [{"id": "hermes-fixture", "value": 37}]})
        entry = {"startedDateTime": "2026-01-01T00:00:00.000Z", "time": 1,
                 "request": {"method": "GET", "url": "https://fixture.example.invalid/api/items", "httpVersion": "HTTP/1.1", "headers": [], "queryString": [], "cookies": [], "headersSize": -1, "bodySize": 0},
                 "response": {"status": 200, "statusText": "OK", "httpVersion": "HTTP/1.1", "headers": [{"name": "content-type", "value": "application/json"}], "cookies": [], "content": {"size": len(body), "mimeType": "application/json", "text": body}, "redirectURL": "", "headersSize": -1, "bodySize": len(body)},
                 "cache": {}, "timings": {"send": 0, "wait": 1, "receive": 0}}
        path.write_text(json.dumps({"log": {"version": "1.2", "creator": {"name": "hermes-fixture", "version": "1"}, "entries": [entry]}}))
        captured = mcp.call("inspect_web_network_capture", {"capture_path": str(path), "format": "har"})
        index = 0
        destination = work / "exported-environment"
        while destination.exists():
            index += 1
            destination = work / f"exported-environment-{index}"
        result = mcp.call("export_environment_bundle", {"source": {"kind": "retained-evidence", "evidence_id": captured["evidence_id"]},
                                                        "output_directory": str(destination), "name": "hermes-fixture"})
        assert result["status"] == "built" and result["capture"]["records"] == 1
        assert result["capture"]["evidence_id"] == captured["evidence_id"]
        assert result["tool_count"] >= 1
        assert (destination / "README.md").is_file()
        assert any(p.is_file() and "hermes-fixture" in p.read_text(errors="replace") for p in destination.rglob("*.json"))
        assert package_root is not None, "Installed package root is required for local environment HTTP proof"
        from environment_http import verify_environment_http
        served = verify_environment_http(destination, package_root, json.loads(body))
        return {"capture_records": 1, "tools": result["tool_count"], "bundle_directory": str(destination),
                "local_http_environment": served, "external_service_or_model_used": False}

    def ntfs_journal():
        mft_path, journal_path = work / "fixture-MFT", work / "fixture-USN"
        mft = bytearray(1024)
        mft[0:4] = b"FILE"
        for offset, value in [(4, 48), (6, 3), (16, 5), (18, 1), (20, 56), (22, 1),
                              (48, 5), (50, 0xA5A5), (52, 0xA5A5), (510, 5), (1022, 5)]:
            struct.pack_into("<H", mft, offset, value)
        for offset, value in [(24, 64), (28, 1024), (44, 0), (56, 0xFFFFFFFF)]:
            struct.pack_into("<I", mft, offset, value)
        mft_path.write_bytes(mft)
        name = "hermes.txt".encode("utf-16le")
        journal = bytearray(80)
        struct.pack_into("<IHHQQqQII", journal, 0, 80, 2, 0, 5 << 48, (1 << 48) | 5, 37, 133000000000000000, 0x80000100, 0)
        struct.pack_into("<HH", journal, 56, len(name), 60)
        journal[60:60 + len(name)] = name
        journal_path.write_bytes(journal)
        evidence = mcp.call("inspect_ntfs_journal", {"mft_path": str(mft_path), "journal_path": str(journal_path), "mft_record_limit": 1})
        result = evidence["normalized_result"]
        assert result["mft"]["sha256"] == hashlib.sha256(mft).hexdigest()
        assert result["journal"]["sha256"] == hashlib.sha256(journal).hexdigest()
        assert result["mftMetadata"]["record_count"] == 1 and result["mftMetadata"]["fixup_mismatch_count"] == 0
        event = next(row["event"] for row in result["rows"] if row["kind"] == "event")
        assert event["name"] == "hermes.txt" and event["usn"] == "37"
        assert event["mft"]["file"]["kind"] == "matched"
        return {"mft_records": 1, "usn": "37", "name": "hermes.txt", "sequence_checked_reference": True}

    def artifact_resources():
        assert package_root is not None, "Installed package root is required"
        archive = work / "resource-lifecycle.zip"
        marker = b"hermes-owned-artifact-resource\n"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
            output.writestr("owned/resource.txt", marker)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        destination = work / "resource-published-output"
        opened = False
        try:
            target = mcp.call("open_binary", {"path": str(archive)})["result"]
            opened = True
            assert target["sha256"] == digest and target["kind"] == "archive"
            first = mcp.call("inspect_artifact")["normalized_result"]
            assert first["subject"]["root_sha256"] == digest
            extracted = mcp.call("extract_artifact", {"output_root": str(destination)})
            assert extracted["evidence_id"]
            published = destination / "owned/resource.txt"
            assert published.read_bytes() == marker
            mcp.call("close_binary")
            opened = False
            status = mcp.call("binary_session")["result"]
            assert status["open"] is False and status["cleanup_pending"] is False
            denied = mcp.request("tools/call", {"name": "inspect_artifact", "arguments": {}})
            (work / "closed-artifact-read.json").write_text(json.dumps(denied, indent=2))
            assert denied.get("isError") is True
            error = denied.get("structuredContent")
            if error is None:
                error = json.loads("\n".join(item["text"] for item in denied["content"] if item["type"] == "text"))
            assert "No app is open" in json.dumps(error), error
            # Successful extraction is published caller output, not scratch space.
            assert published.read_bytes() == marker
            reopened = mcp.call("open_binary", {"path": str(archive)})["result"]
            opened = True
            again = mcp.call("inspect_artifact")["normalized_result"]
            assert reopened["sha256"] == digest and again["subject"] == first["subject"]
            assert hashlib.sha256(archive.read_bytes()).hexdigest() == digest
        finally:
            if opened:
                mcp.call("close_binary")
        # Exercise the exact installed ownership primitives with real kernel
        # handles/private directories. There are no public opaque archive handles.
        script = work / "owned-resource-proof.mjs"
        script.write_text('''import assert from "node:assert/strict";
import {open, access, writeFile, stat} from "node:fs/promises";
import {pathToFileURL} from "node:url";
import {join} from "node:path";
import {createHash} from "node:crypto";
const [root, source, parent] = process.argv.slice(2);
const load = relative => import(pathToFileURL(join(root, relative)).href);
const {ArtifactResourceScope} = await load("dist/resources/ArtifactResourceScope.js");
const {OwnedFileHandle} = await load("dist/filesystem/OwnedFileHandle.js");
const {PrivateRuntimeRoot} = await load("dist/process/PrivateRuntimeRoot.js");
const scope = new ArtifactResourceScope();
const handle = await open(source, "r");
const owned = new OwnedFileHandle(handle);
scope.retain({kind:"file-handle",resource:source,handle:owned});
let scratch;
try {
  const before = await handle.readFile();
  assert.equal(before.subarray(0,2).toString(), "PK");
  scratch = await PrivateRuntimeRoot.create({parent,prefix:"artifact-owned-"});
  scope.retain({kind:"private-runtime-root",resource:scratch.path,root:scratch});
  assert.equal((await stat(scratch.path)).mode & 0o777, 0o700);
  await writeFile(join(scratch.path,"partial.txt"), "owned unpublished bytes");
  assert.equal(scope.hasPending,true);
  await scope.close();
  assert.equal(scope.hasPending,false);
  assert.equal(handle.fd,-1);
  await assert.rejects(() => handle.readFile(), {code:"EBADF"});
  await assert.rejects(() => access(scratch.path), {code:"ENOENT"});
  await assert.rejects(() => scope.run(async () => "must not execute"), /scope is closed/);
  const fresh = await open(source,"r");
  let after;
  try {assert.notEqual(fresh,handle); after=await fresh.readFile();} finally {await fresh.close();}
  assert.deepEqual(after,before);
  console.log(JSON.stringify({closed_handle_read:"EBADF",scratch_removed:true,
    scratch_path:scratch.path,fresh_handle_bytes_equal:true,
    source_sha256:createHash("sha256").update(after).digest("hex")}));
} finally {await scope.close();}
''')
        proof = subprocess.run(["node", str(script), str(Path(package_root).resolve()), str(archive), str(work)],
                               text=True, capture_output=True, timeout=60)
        assert proof.returncode == 0, proof.stderr[-2400:]
        resources = json.loads(proof.stdout)
        assert resources["source_sha256"] == digest
        (work / "owned-resource-proof.json").write_text(json.dumps(resources, indent=2))
        return {"public_archive_close_denies_inspection": True, "reopen_inventory_intact": True,
                "published_output_retained": True, "ownership_primitives": resources,
                "scope": "Normal real file/private-root lifecycle; cancellation/fault retries and exhaustive leak testing excluded"}

    def desktop_runtime_pack():
        assert package_root is not None, "Installed package root is required"
        root = Path(package_root).resolve()
        script = root / "scripts/pack-build-computer-runtime.mjs"
        assert script.is_file(), "Upstream desktop runtime packaging script is missing"
        archive = work / "desktop-build-runtime.tar.xz"
        env = dict(os.environ, npm_config_audit="false",
                   npm_config_fund="false", npm_config_progress="false")
        # Do not inherit a caller's alternate npm entry or registry credentials.
        env.pop("npm_execpath", None)
        env.pop("NPM_TOKEN", None)
        env.pop("NODE_AUTH_TOKEN", None)
        env["npm_config_userconfig"] = os.devnull
        log = work / "desktop-runtime-pack.log"
        with log.open("w") as output:
            result = subprocess.run(["node", str(script), str(archive)], cwd=work,
                                    env=env, stdout=output, stderr=subprocess.STDOUT, timeout=600)
        assert result.returncode == 0, f"Runtime packing failed: {log.read_text()[-2400:]}"
        assert archive.stat().st_size > 100000
        required = ["scripts/rea.mjs", "dist/main.js", "dist/mcp-catalog.json",
                    "package.json", "package-lock.json", "node_modules/playwright-core/package.json"]
        with tarfile.open(archive, "r:xz") as payload:
            names = {member.name.removeprefix("./"):member for member in payload.getmembers()}
            for name in required:
                assert "rea-prod/"+name in names, f"Packed runtime lacks {name}"
            package = json.load(payload.extractfile(names["rea-prod/package.json"]))
            lock = json.load(payload.extractfile(names["rea-prod/package-lock.json"]))
            assert package["name"] == "rea-agents" and package["version"] == "6.9.0"
            assert lock["packages"][""]["version"] == package["version"]
            assert lock["packages"][""]["dependencies"] == package["dependencies"]
            assert all(name == "rea-prod" or name.startswith("rea-prod/") for name in names)
        return {"archive": str(archive), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "bytes": archive.stat().st_size, "required_entries": required,
                "scope": "Unchanged upstream runtime archive producer; no remote desktop execution"}

    for name, callback in [
        ("elf-notes", elf_notes), ("native-exports", native_exports),
        ("binary-hardening", binary_hardening), ("native-initializers", native_initializers),
        ("elf-unwind", elf_unwind), ("elf-dependencies", elf_dependencies),
        ("dwarf", dwarf), ("elf-debug-link", elf_debug_link), ("entropy", entropy),
        ("model", model), ("python-pyc", python_pyc), ("evm", evm),
        ("kernel-module", kernel_module), ("devicetree", devicetree), ("nuget", nuget),
        ("apple-ips", apple_ips), ("beam", beam), ("gpu", gpu), ("rust", rust),
        ("v8-cache", v8_cache), ("windows-shortcut", windows_shortcut),
        ("il2cpp", il2cpp), ("flutter", flutter), ("apple-graph", apple_graph),
        ("harmony-graph", harmony_graph), ("go-binary", go_binary),
        ("pe-imports", pe_imports), ("pe-certificates", pe_certificates),
        ("pe-resources", pe_resources), ("pe-load-config", pe_load_config),
        ("kernel-config", kernel_config), ("electron-fuses", electron_fuses),
        ("analysis-view", analysis_view), ("android-graph", android_graph),
        ("apk-signature", apk_signature), ("release-exposure", release_exposure),
        ("settings", settings), ("unknown-lifecycle", unknown_lifecycle),
        ("managed-workflow", managed_workflow), ("desktop-application", desktop_application),
        ("application-comparison", application_comparison),
        ("api-contracts", api_contracts), ("playwright-trace", playwright_trace),
        ("environment-export", environment_export),
        ("ntfs-journal", ntfs_journal),
        ("desktop-runtime-pack", desktop_runtime_pack),
        ("artifact-resources", artifact_resources),
    ]:
        test(name, callback)
