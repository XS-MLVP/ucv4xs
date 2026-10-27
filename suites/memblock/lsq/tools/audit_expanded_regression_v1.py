#!/usr/bin/env python3
"""Audit the post-supplement summary-only regression against regression13."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def primary(message: str) -> str:
    """Normalize only Python object addresses, which vary by process.

    Failure assertions and actual result fields remain byte-for-byte compared;
    arbitrary hexadecimal payloads are deliberately not normalized.
    """
    return re.sub(r"\bat 0x[0-9a-fA-F]+\b", "at <process-address>", message)


def cases(run: str) -> dict[str, dict]:
    root = ET.parse(ROOT / "results" / run / "pytest.xml").getroot()
    result = {}
    for case in root.iter("testcase"):
        node = f"{case.attrib.get('classname','')}::{case.attrib.get('name','')}"
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        if failure is not None:
            outcome = "FAIL"; detail = primary(failure.attrib.get("message", "") + "\n" + (failure.text or ""))
        elif error is not None:
            outcome = "ERROR"; detail = primary(error.attrib.get("message", "") + "\n" + (error.text or ""))
        elif skipped is not None:
            outcome = "SKIP"; detail = skipped.attrib.get("message", "")
        else:
            outcome = "PASS"; detail = ""
        result[node] = dict(outcome=outcome, detail=detail)
    assert len(result) == sum(1 for _ in root.iter("testcase"))
    return result


def failure_digest(data: dict[str, dict]) -> str:
    rows = [f"{node}\0{item['outcome']}\0{item['detail']}" for node, item in sorted(data.items()) if item["outcome"] in ("FAIL", "ERROR")]
    return hashlib.sha256(("\n".join(rows) + "\n").encode()).hexdigest()


def audit(name: str) -> dict:
    old_name = "lsq-progress-regression-13"
    old = json.loads((ROOT / "results" / old_name / "execution/manifest.json").read_text())
    new = json.loads((ROOT / "results" / name / "execution/manifest.json").read_text())
    assert new["state"] == "committed" and new["coverage_complete"] and new["cleanup_complete"]
    old_cases, new_cases = cases(old_name), cases(name)
    old_failures = {node: item for node, item in old_cases.items() if item["outcome"] in ("FAIL", "ERROR")}
    missing_old = sorted(node for node in old_failures if node not in new_cases)
    changed_failures = sorted(node for node, item in old_failures.items() if node in new_cases and new_cases[node] != item)
    new_failures = sorted(node for node, item in new_cases.items() if item["outcome"] in ("FAIL", "ERROR") and node not in old_failures)
    assert not missing_old and not changed_failures

    launch = json.loads((ROOT / "results" / name / "source-aggregate-launch.json").read_text())
    end = json.loads((ROOT / "results" / name / "source-aggregate-end.json").read_text())
    assert end.pop("launch_and_end_equal") and launch == end
    policy = json.loads((ROOT / "results" / name / "trace-policy.json").read_text())
    assert not policy["per_cycle_JSON"] and not policy["waveforms"]
    cases_dir = ROOT / "results" / name / "cases"
    assert not list(cases_dir.rglob("*.jsonl")) and not list(cases_dir.rglob("*.fst")) and not list(cases_dir.rglob("*.vcd"))

    artifact_hash_ok = True
    for artifact in new["artifacts"]:
        artifact_hash_ok &= sha256(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            artifact_hash_ok &= all(sha256(Path(path)) == digest for path, digest in artifact["build"]["files"].items())
    assert artifact_hash_ok

    report = dict(
        format="lsq-expanded-regression-audit-v1", run=name, baseline=old_name,
        new_manifest=dict(state=new["state"], tests=new["tests"], functional_groups=new["functional_groups"], native_inputs=sum(w["native_inputs"] for w in new["workers"]), coverage_complete=new["coverage_complete"], cleanup_complete=new["cleanup_complete"]),
        baseline_manifest=dict(tests=old["tests"], functional_groups=old["functional_groups"], native_inputs=sum(w["native_inputs"] for w in old["workers"])),
        node_counts=dict(before=len(old_cases), after=len(new_cases), added=len(set(new_cases) - set(old_cases)), removed=len(set(old_cases) - set(new_cases))),
        failure_preservation=dict(
            before_failure_count=len(old_failures), after_failure_count=sum(item["outcome"] in ("FAIL", "ERROR") for item in new_cases.values()),
            old_failures_missing=missing_old, old_failure_signatures_changed=changed_failures, new_failure_nodes=new_failures,
            before_failure_primary_SHA256=failure_digest(old_cases), after_failure_primary_SHA256=failure_digest(new_cases),
            every_old_failure_primary_equal=not missing_old and not changed_failures,
        ),
        source=dict(launch_file_count=launch["file_count"], launch_SHA256=launch["aggregate_SHA256"], launch_end_equal=True, differs_from_regression13_source=True),
        retention=dict(per_cycle_JSON=False, waveforms=False, jsonl_files=0, waveform_files=0, native_artifact_hashes_ok=artifact_hash_ok),
        failure_signature_normalization="Python object addresses matching `at 0x...` are replaced with `<process-address>`; assertion text and actual result fields are otherwise compared exactly.",
        conclusion="Post-supplement committed regression retains every regression13 failure signature while adding the new directed cases; any new failure node is listed explicitly and must remain open.",
        limits="This audit compares outcome signatures and summary retention, not a new semantic oracle for the remaining gap inventory. Three-metric summaries and final evidence matrix are separate artifacts.",
    )
    output = ROOT / "results" / name / "expanded-regression-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
