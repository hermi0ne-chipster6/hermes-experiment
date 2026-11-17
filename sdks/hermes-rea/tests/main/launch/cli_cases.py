#!/usr/bin/env python3
"""Owned, model-free CLI skill installation and Evidence publication regressions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import stat
import subprocess
import tempfile


MANAGED_SKILL_FILES = (
    "SKILL.md", "references/connection-and-recovery.md",
    "references/native-and-artifacts.md", "references/javascript-applications.md",
    "references/android-applications.md", "references/runtime-observation.md",
    "references/evidence-workflows.md", "references/environments.md",
    "references/desktop-build.md",
)
SKILL_NAME = "reverse-engineer-anything"


def package_root(command):
    """Resolve the installed SDK wrapper or upstream Node script, without executing it."""
    for token in command:
        candidate = Path(shutil.which(token) or token).resolve()
        if candidate.name == "rea.mjs" and candidate.parent.name == "scripts":
            root = candidate.parent.parent
        elif candidate.name == "rea" and candidate.parent.name == "wrappers":
            root = candidate.parent.parent / "rea/node_modules/rea-agents"
        else:
            continue
        if (root / "package.json").is_file():
            return root
    raise AssertionError("CLI command must identify the installed SDK rea wrapper or scripts/rea.mjs")


def owned_file(path):
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid(), str(path)
    assert not stat.S_IMODE(info.st_mode) & 0o022, str(path)
    return path.read_bytes()


def isolated_case(work, name):
    assert os.geteuid() != 0 and pwd.getpwuid(os.geteuid()).pw_name == "rea", "Run as the installed rea account"
    work.mkdir(parents=True, exist_ok=True)
    case = Path(tempfile.mkdtemp(prefix=name + "-", dir=work)).resolve()
    home = case / "home"
    home.mkdir(mode=0o700)
    assert stat.S_IMODE(home.stat().st_mode) == 0o700 and home.stat().st_uid == os.geteuid()
    # Deliberately do not inherit client configuration roots, credentials,
    # NODE_OPTIONS, or user-supplied REA settings. The SDK wrapper supplies its
    # provider defaults. Built-in static JS analysis needs no provider overrides.
    environment = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                   "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "HOME": str(home),
                   "USER": "rea", "LOGNAME": "rea", "CI": "1", "NO_UPDATE_NOTIFIER": "1"}
    for variable, relative in {
        "XDG_CONFIG_HOME": ".config", "XDG_CACHE_HOME": ".cache",
        "XDG_DATA_HOME": ".local/share", "XDG_STATE_HOME": ".local/state",
        "XDG_RUNTIME_DIR": ".runtime", "XDG_CONFIG_DIRS": ".system-config",
        "XDG_DATA_DIRS": ".system-data", "TMPDIR": ".tmp",
    }.items():
        directory = home / relative
        directory.mkdir(parents=True, mode=0o700)
        environment[variable] = str(directory)
    # Explicit system override where upstream supports one. Other client roots
    # fall back to this HOME/XDG tree; no --client or --all-detected is selected.
    environment["GEMINI_CLI_SYSTEM_SETTINGS_PATH"] = str(home / ".system-config/gemini.json")
    return case, home, environment


def runner(command, case, environment):
    sequence = 0

    def run(label, arguments, *, success=True):
        nonlocal sequence
        sequence += 1
        result = subprocess.run([*command, *arguments], cwd=case, env=environment,
                                capture_output=True, text=True, timeout=180,
                                stdin=subprocess.DEVNULL)
        prefix = case / f"{sequence:02d}-{label}"
        prefix.with_suffix(".stdout").write_text(result.stdout)
        prefix.with_suffix(".stderr").write_text(result.stderr)
        prefix.with_suffix(".exit").write_text(str(result.returncode) + "\n")
        if success:
            assert result.returncode == 0, f"{label}: exit {result.returncode}; see {prefix}.stderr"
        value = json.loads(result.stdout)
        assert isinstance(value, dict), value
        return value, result.returncode
    return run


def run_cli_cases(command, output, work, test):
    """Register two cases through functional.py's test(case_id, callable) callback."""
    output, work = Path(output).resolve(), Path(work).resolve()
    output.mkdir(parents=True, exist_ok=True)

    def setup():
        root = package_root(command)
        case, home, environment = isolated_case(work, "cli-setup")
        run = runner(command, case, environment)
        args = ["setup", "--skill-client", "shared", "--yes", "--json"]
        first, _ = run("setup", args)
        assert first["status"] == "ready", first
        assert first["appliedActions"] == ["installed_skill"], first
        assert first["clients"] == {}, first
        destination = home / ".agents/skills" / SKILL_NAME
        source = root / "skills" / SKILL_NAME
        actual_files = {str(path.relative_to(destination)) for path in destination.rglob("*") if path.is_file()}
        assert actual_files == set(MANAGED_SKILL_FILES), actual_files
        before = {}
        for relative in MANAGED_SKILL_FILES:
            path = destination / relative
            content = owned_file(path)
            assert content == (source / relative).read_bytes(), relative
            before[relative] = (hashlib.sha256(content).hexdigest(), path.stat().st_mtime_ns)
        doctor, _ = run("doctor-skill", ["doctor", "--skill", "--json"])
        assert doctor["healthy"] is True, doctor
        assert doctor["identity"]["skill"]["state"] == "aligned", doctor
        assert doctor["identity"]["skill"]["installed_version"] == doctor["identity"]["expected_skill_version"], doctor
        second, _ = run("setup-repeat", args)
        assert second["status"] == "ready" and second["appliedActions"] == [] and second["clients"] == {}, second
        for relative, expected in before.items():
            path = destination / relative
            assert (hashlib.sha256(owned_file(path)).hexdigest(), path.stat().st_mtime_ns) == expected, relative
        assert {str(path.relative_to(destination)) for path in destination.rglob("*") if path.is_file()} == actual_files
        result = {"assertion": "Nine bundled skill files installed exactly, scoped doctor aligned, repeat unchanged",
                  "case_directory": str(case), "isolated_home": str(home), "files": {name: value[0] for name, value in before.items()},
                  "skill_version": doctor["identity"]["skill"]["installed_version"],
                  "scope": "Shared skill only; no client registrations, optional installation, model, or real HOME modification"}
        (output / "cli-setup-result.json").write_text(json.dumps(result, indent=2) + "\n")
        return result

    def evidence():
        case, home, environment = isolated_case(work, "cli-evidence")
        run = runner(command, case, environment)
        app = case / "application"
        app.mkdir()
        (app / "package.json").write_text(json.dumps({"name": "hermes-cli-evidence-fixture", "version": "1.0.0", "main": "main.js"}))
        (app / "main.js").write_text("const {ipcMain}=require('electron');\nconst helper=require('./helper');\nipcMain.handle('hermes-cli-evidence-marker',()=>helper.greet('fixture'));\n")
        (app / "helper.js").write_text("exports.greet = name => 'hello ' + name;\n")
        bundle_path, copy_path = case / "evidence.json", case / "copy.json"
        delivered, _ = run("analyze", ["analyze-javascript-application", str(app), "--detail", "summary",
                                      "--evidence_output", str(bundle_path), "--json"])
        bundle_bytes = owned_file(bundle_path)
        bundle = json.loads(bundle_bytes)
        records = bundle["records"]
        assert records, bundle
        ids = {record["evidence_id"] for record in records}
        assert len(ids) == len(records) and all(re.fullmatch(r"ev_[a-f0-9]{64}", value) for value in ids)
        summary = delivered["summary"]
        assert summary["operation"] == "inspect_analysis_view", summary
        assert summary["normalized_result"]["kind"] == "summary", summary
        root_id = summary["parameters"]["parent_evidence_id"]
        assert summary["evidence_links"] == [root_id], summary
        assert summary["parameters"]["view"] == {"kind": "summary"}, summary
        assert root_id in ids, delivered
        root_record = next(record for record in records if record["evidence_id"] == root_id)
        assert root_record["operation"] == "analyze_javascript_application", root_record
        semantic = json.dumps(root_record["normalized_result"])
        for marker in ("hermes-cli-evidence-marker", "helper.js", "main.js"):
            assert marker in semantic, f"Missing observed JS semantic {marker}"
        for record in records:
            assert set(record["evidence_links"]) <= ids, record
        # Check that every retained record is reachable from the delivered root.
        by_id = {record["evidence_id"]: record for record in records}
        reached, pending = set(), [root_id]
        while pending:
            current = pending.pop()
            if current not in reached:
                reached.add(current)
                pending.extend(by_id[current]["evidence_links"])
        assert reached == ids, {"unreachable": sorted(ids - reached)}
        expected_counts = {"records": len(records), "unknowns": len(bundle["unknowns"])}
        receipt = delivered["evidence_bundle"]
        assert receipt["bytes"] == len(bundle_bytes) and Path(receipt["path"]) == bundle_path, receipt
        imported, _ = run("import", ["evidence-import", str(bundle_path), "--json"])
        assert imported == {"imported": len(records), "unknowns_added": len(bundle["unknowns"]), "total": len(records)}, imported
        exported, _ = run("export", ["evidence-export", str(bundle_path), str(copy_path), "--json"])
        copied = owned_file(copy_path)
        assert json.loads(copied) == bundle, "Canonical roundtrip changed Evidence content/identities"
        assert {key: exported[key] for key in expected_counts} == expected_counts, exported
        assert exported["bytes"] == len(copied) and Path(exported["path"]) == copy_path, exported
        refused, refusal_exit = run("no-overwrite", ["evidence-export", str(bundle_path), str(copy_path), "--json"], success=False)
        assert refusal_exit == 1, refusal_exit
        assert refused["code"] == "invalid_request" and refused["category"] == "invalid_input", refused
        assert refused["details"]["reason"] == "exists" and refused["details"]["operation"] == "write", refused
        assert Path(refused["details"]["path"]) == copy_path, refused
        assert owned_file(copy_path) == copied and owned_file(bundle_path) == bundle_bytes
        result = {"assertion": "Real JS graph summarized with complete retained closure, validated CLI import/export, typed no-overwrite refusal",
                  "case_directory": str(case), "isolated_home": str(home), "evidence_ids": sorted(ids),
                  "record_count": len(records), "unknown_count": len(bundle["unknowns"]),
                  "bundle_sha256": hashlib.sha256(bundle_bytes).hexdigest(), "copy_sha256": hashlib.sha256(copied).hexdigest(),
                  "no_overwrite_exit_code": refusal_exit,
                  "scope": "Local static analysis and Evidence filesystem workflow; no Electron runtime or model"}
        (output / "cli-evidence-result.json").write_text(json.dumps(result, indent=2) + "\n")
        return result

    test("cli-setup", setup)
    test("cli-evidence", evidence)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rea", default="rea")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--case", choices=("cli-setup", "cli-evidence"), action="append")
    args = parser.parse_args()
    results = {}

    def test(name, execute):
        if not args.case or name in args.case:
            results[name] = execute()
    run_cli_cases(shlex.split(args.rea), args.output, args.work, test)
    print(json.dumps({"status": "passed", "results": results}, indent=2))


if __name__ == "__main__":
    main()
