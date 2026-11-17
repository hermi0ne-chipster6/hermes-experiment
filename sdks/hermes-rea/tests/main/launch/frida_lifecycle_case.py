"""Installed Frida/Node child-reaping regression with an owned finite fixture."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile


CHILD_STAGES = (
    "before-frida-import", "frida-import", "frida-device-manager",
    "frida-enumerate-devices", "frida-enumerate-processes",
    "frida-spawn-owned-fixture", "frida-attach-owned-fixture",
    "frida-load-script", "frida-unload-script", "frida-resume-owned-fixture",
    "frida-detach-owned-fixture", "after-owned-fixture-exit",
)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_probe(case, node, fixture):
    rows = json.loads((case / "probe/results.json").read_text())
    final = json.loads((case / "probe/final.json").read_text())
    assert final["completed"] is True and final["failed_checks"] == 0, final
    assert rows and all(row["status"] == "pass" for row in rows), "Frida process probe contains failures"
    identities = [row for row in rows if row["stage"] == "identity"]
    assert len(identities) == 1 and identities[0]["mode"] == "injection", identities
    assert Path(identities[0]["exec_path"]).resolve() == node.resolve(), "Probe used a different Node runtime"
    assert identities[0]["fixture_sha256"] == _sha256(fixture), "Probe used a different fixture"
    children = [row for row in rows if "kind" in row]
    expected = {(stage, kind) for stage in CHILD_STAGES for kind in ("ps", "node-child")}
    assert len(children) == len(expected) and {(row["stage"], row["kind"]) for row in children} == expected, "Missing or duplicate before/after child-process checks"
    for row in children:
        assert row["exit_code"] == 0 and row["signal"] is None, row
        assert "spawn" in row["events"] and {"exit": 0, "signal": None} in row["events"], row
        assert "timeout_ms" not in row, row
    for stage in CHILD_STAGES[1:-1]:
        assert len([row for row in rows if row["stage"] == stage and "kind" not in row]) == 1, f"Missing Frida operation: {stage}"
    starts = [index for index, row in enumerate(rows) if row["stage"] == "owned-node-sentinel-start"]
    cleanups = [index for index, row in enumerate(rows) if row["stage"] == "owned-node-sentinel-cleanup"]
    assert len(starts) == len(cleanups) == 1 and rows[starts[0]]["child_pid"] > 0, "Missing owned sentinel lifecycle"
    exits = [index for index, row in enumerate(rows) if row["stage"] == "owned-frida-target-exit"]
    assert len(exits) == 1, "Missing observed owned Frida target exit"
    target_exit = rows[exits[0]]
    assert target_exit["pid"] > 0 and str(target_exit["starttime"]).isdigit(), target_exit
    spawn = next(row for row in rows if row["stage"] == "frida-spawn-owned-fixture" and "kind" not in row)
    assert spawn["target_identity"]["pid"] == target_exit["pid"], "Exit observation used a different target PID"
    assert spawn["target_identity"]["starttime"] == target_exit["starttime"], "Exit observation used a different target process identity"
    assert target_exit["observation"] in ("proc-entry-gone", "exited-process-state"), target_exit
    if target_exit["observation"] == "exited-process-state":
        assert target_exit["state"] in ("Z", "X"), target_exit
    watched = []
    for index, row in enumerate(rows):
        if row["stage"] in ("before-frida-import", "after-owned-fixture-exit"):
            assert starts[0] < index < cleanups[0], "Signal check ran outside sentinel lifetime"
            if row["stage"] == "after-owned-fixture-exit":
                assert exits[0] < index, "Post-exit child check preceded observed target exit"
            assert int(row["node_signal_state"]["SigCgt"], 16) & (1 << 16), "SIGCHLD handler disappeared across Frida lifecycle"
            watched.append(row)
    assert len(watched) == 4, "Require both child checks before import and after fixture exit"
    return {"records": len(rows), "child_process_checks": len(children),
            "sigchld_caught_before_and_after": True, "owned_sentinel_cleanup": True,
            "owned_target_exit_observed": target_exit["observation"],
            "duration_ms": final["duration_ms"], "node_version": identities[0]["versions"]["node"]}


def run_frida_lifecycle(package_root, output, work):
    """Return semantic acceptance detail, raising on any missing/failed check.

    GCC is a test-fixture prerequisite, not a production REA dependency. The
    parent runner owns result aggregation and must copy the companion .mjs.
    """
    assert os.getuid() != 0, "Run as the unprivileged REA account"
    package_root, output, work = (Path(path).resolve() for path in (package_root, output, work))
    node = package_root.parents[2] / "node/bin/node"
    probe = Path(__file__).with_name("frida_process_probe.mjs")
    assert node.is_file() and os.access(node, os.X_OK), f"Installed Node missing: {node}"
    assert probe.is_file(), f"Copy companion probe into test directory: {probe}"
    case = output / "frida-process-lifecycle"
    case.mkdir(mode=0o700, parents=True, exist_ok=False)
    fixture_dir = Path(tempfile.mkdtemp(prefix="frida-process-lifecycle-", dir=work))
    source, fixture = fixture_dir / "fixture.c", fixture_dir / "fixture"
    source.write_text("#include <unistd.h>\nint main(void){sleep(2);return 0;}\n")
    with (case / "compile.log").open("wb") as log:
        compiled = subprocess.run(["gcc", "-g", "-O0", "-o", str(fixture), str(source)],
                                  stdout=log, stderr=subprocess.STDOUT, timeout=60)
    assert compiled.returncode == 0, f"Owned fixture compilation failed; see {case / 'compile.log'}"
    command = [str(node), str(probe), "--output", str(case / "probe"), "--fixture", str(fixture),
               "--package-root", str(package_root), "--mode", "injection"]
    with (case / "probe-stdout.log").open("wb") as stdout, (case / "probe-stderr.log").open("wb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code = child.wait(timeout=180)
        except subprocess.TimeoutExpired:
            # This process group was created solely for this probe and its children.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait(timeout=10)
            (case / "exit.json").write_text(json.dumps({"timeout_seconds": 180, "exit_code": child.returncode}) + "\n")
            raise AssertionError(f"Frida lifecycle exceeded 180 seconds; see {case}")
    (case / "exit.json").write_text(json.dumps({"exit_code": code}) + "\n")
    assert code == 0, f"Frida lifecycle process exited {code}; see {case / 'probe/results.json'}"
    detail = _validate_probe(case, node, fixture)
    frida = package_root.parent / "frida"
    detail.update({"assertion": "Real Frida injection preserves Node SIGCHLD handling and child completion before/after owned target exit",
                   "case_directory": str(case), "fixture": str(fixture),
                   "fixture_sha256": _sha256(fixture),
                   "installed_node": str(node), "frida_version": json.loads((frida / "package.json").read_text())["version"],
                   "native_binding_sha256": _sha256(frida / "build/frida_binding.node")})
    return detail
