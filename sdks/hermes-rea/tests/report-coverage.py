#!/usr/bin/env python3
"""Merge actual installed-SDK test records without converting probes into passes.

Example: python3 tests/report-coverage.py --environment workshop:fresh-one \
  --artifact-sha256 SHA256 --results /logs/first/results.json /logs/retest/results.json \
  --output /logs/coverage

Files are chronological: the last result for an ID is effective. All earlier
attempts remain in the JSON. A later successful retry therefore does not hide
the original failure. Never feed host-only fixture debugging into an installed
Workshop report. The required environment and artifact identity are provenance,
not independently verified by this merger.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re


def classify(row, attempts):
    tests = row["test_ids"]
    effective = {name: attempts[name][-1] for name in tests if name in attempts}
    passed = [name for name, result in effective.items() if result["status"] == "pass"]
    failed = [name for name, result in effective.items() if result["status"] == "fail"]
    unavailable = [name for name, result in effective.items() if result["status"] == "unavailable"]
    pending = [name for name in tests if name not in effective]
    platform = row.get("limitation_cause") == "incompatible-platform"
    if platform:
        if passed:
            raise ValueError("A platform-disabled row has passing tests: manually reconcile its source classification")
        status = "Unsupported on target platform"
    elif passed and not failed and not unavailable and not pending:
        status = "Fully functional"
    elif passed:
        status = "Partially functional"
    elif failed or unavailable:
        status = "Missing"
    else:
        status = "Not yet tested"
    # Indirect normal cleanup alone cannot establish lifetime/fault behavior.
    if row.get("maximum_status") == "Partially functional" and status == "Fully functional":
        status = "Partially functional"
    issues = []
    for name in failed + unavailable:
        result = effective[name]
        reason = result.get("reason", "No diagnostic recorded")
        # Failure strings are never proof of an upstream defect. These labels
        # only identify obvious missing executables; all other causes need triage.
        cause = row.get("limitation_cause") or (
            "missing-dependency" if re.search(r"(?:executable|command|program).*(?:not found|missing)|No such file or directory|Missing executable", reason, re.I)
            else "unresolved-validation-failure")
        issues.append({"test": name, "cause": cause, "reason": reason,
                       "requires_triage": cause == "unresolved-validation-failure", "source": result["source"]})
    return {**row, "status": status, "execution_evidence": list(effective.values()),
            "passing_tests": passed, "failing_tests": failed,
            "unavailable_tests": unavailable, "pending_tests": pending,
            "issues": issues}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, default=Path(__file__).resolve().parents[1] / "docs/capability-coverage.json")
    parser.add_argument("--environment", required=True, help="Actual fresh Workshop identity; not a host-debug run")
    parser.add_argument("--artifact-sha256", required=True, help="Digest of the installed SDK archive")
    parser.add_argument("--results", nargs="+", required=True, type=Path, help="Chronological functional result JSON arrays")
    parser.add_argument("--output", required=True, type=Path, help="Output prefix for .json and .md")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{64}", args.artifact_sha256):
        parser.error("--artifact-sha256 must be a lower-case SHA256 digest")
    mapping = json.loads(args.mapping.read_text())
    if len(mapping["capabilities"]) != 78:
        parser.error("Expected the pinned baseline's 78 capability keys")
    attempts, inputs = {}, []
    for path in args.results:
        raw = path.read_bytes()
        records = json.loads(raw)
        if not isinstance(records, list):
            parser.error(f"{path} must contain a result array")
        source = str(path.resolve())
        inputs.append({"path": source, "sha256": hashlib.sha256(raw).hexdigest()})
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("test"), str) or record.get("status") not in {"pass", "fail", "unavailable"}:
                parser.error(f"Invalid functional result in {path}")
            attempts.setdefault(record["test"], []).append({**record, "source": source})
    report = {"schema_version": 1, "upstream_commit": mapping["upstream_commit"],
              "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "environment": args.environment, "installed_sdk_sha256": args.artifact_sha256,
              "status_policy": mapping["status_policy"], "input_files": inputs,
              "test_attempts": attempts,
              "capabilities": {key: classify(row, attempts) for key, row in mapping["capabilities"].items()},
              "shared_workflows": {key: classify(row, attempts) for key, row in mapping["shared_workflows"].items()}}
    mapped = {name for section in (mapping["capabilities"], mapping["shared_workflows"])
              for row in section.values() for name in row["test_ids"]}
    report["unmapped_test_ids"] = sorted(set(attempts) - mapped)
    counts = {}
    for row in report["capabilities"].values():
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    report["capability_status_counts"] = counts
    args.output.parent.mkdir(parents=True, exist_ok=True)
    Path(str(args.output) + ".json").write_text(json.dumps(report, indent=2) + "\n")
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["# Installed Hermes REA validation coverage", "",
             f"Environment: `{args.environment}`. SDK SHA256: `{args.artifact_sha256}`.", "",
             "A pass proves only the recorded representative scope. Missing means a tested operation was not operational; unresolved failure causes still require triage. Registration and diagnostics are not functional evidence. Earlier attempts remain in the JSON report.", ""]
    for title, section in [("Capabilities", report["capabilities"]), ("Shared workflows", report["shared_workflows"])]:
        lines += [f"## {title}", "", "| Capability | Status | Representative tests | Scope / remaining limits |", "| --- | --- | --- | --- |"]
        for key, row in section.items():
            outcomes = ", ".join(f"{name}: {attempts[name][-1]['status'] if name in attempts else 'not run'}" for name in row["test_ids"]) or "No representative test"
            notes = row.get("limitation", row.get("scope", ""))
            if row["issues"]:
                notes += " " + "; ".join(f"{issue['cause']}: {issue['reason']}" for issue in row["issues"])
            lines.append("| " + " | ".join(map(cell, [key, row["status"], outcomes, notes])) + " |")
        lines.append("")
    Path(str(args.output) + ".md").write_text("\n".join(lines))
    print(json.dumps({"environment": args.environment, "counts": counts, "unmapped_test_ids": report["unmapped_test_ids"]}))


if __name__ == "__main__":
    main()
