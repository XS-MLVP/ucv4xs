#!/usr/bin/env python3
"""Integrity gate for the currently implemented suite; known failures stay red."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(name):
    run = ROOT / "results" / name
    manifest_path = run / "execution/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    assert manifest["pytest_exitstatus"] == 1 and manifest["tests"] == {"PASS": 188, "FAIL": 7}
    native_ids = set()
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            native_ids.add(artifact["build"]["build_id"])
            for path, digest in artifact["build"]["files"].items():
                assert sha(Path(path)) == digest, path
    assert len(native_ids) == 11
    source = json.loads((run / "source-evidence.json").read_text())
    for path, digest in source["files"].items():
        assert sha(run / "verification-source" / path) == digest, path
    issues = json.loads((run / "verification-source/manifest/known-issues.json").read_text())["issues"]
    issue = next(item for item in issues if item["id"] == "RAR-REL-001")
    known = {case["nodeid"]: case for case in issue["failure_cases"]}
    xml = ET.parse(run / "pytest.xml").getroot()
    cases = list(xml.iter("testcase"))
    assert len(cases) == 195 and not list(xml.iter("error")) and not list(xml.iter("skipped"))
    families, failed = Counter(), []
    for case in cases:
        classname = case.attrib["classname"]
        families[classname.split(".")[1]] += 1
        nodeid = classname.replace(".", "/") + ".py::" + case.attrib["name"]
        failure = case.find("failure")
        if failure is not None:
            assert nodeid in known
            signature = known[nodeid]
            message = failure.attrib["message"]
            assert "response.nuke" in message
            actual, expected = re.findall(r"Response\(valid=True, nuke=(True|False)\)", message)
            assert (actual == "True") == signature["actual_nuke"] and (expected == "True") == signature["expected_nuke"]
            failed.append({"nodeid": nodeid, "issue": issue["id"], **signature})
    assert {case["nodeid"] for case in failed} == set(known)
    assert families == Counter(age=11, cam=24, freelist=52, rar=54, raw=32, vlq=22)
    audit_path = run / "line-audit.json"
    lines = json.loads(audit_path.read_text())
    assert lines["run"] == name and lines["tests"] == manifest["tests"]
    assert {row["build_id"] for row in lines["native"]} == native_ids
    for row in lines["native"]:
        assert row["line_hit"] == row["line_total"] > 0 and not row["uncovered"]
        for dep in row.get("dependencies", []):
            assert dep["line_hit"] == dep["line_total"] and not dep["uncovered"]
    functional = json.loads((run / "execution/functional-coverage.json").read_text())
    groups = {group["instance"]: group for group in functional["groups"]}
    assert len(groups) == 22
    missing = {}
    for instance, group in groups.items():
        point = group["points"][0]
        assert group["collection_complete"] and not point["unknown"] and not point["unmatched"]
        if instance.endswith("checked"):
            reached = groups[instance.removesuffix("checked") + "reached"]["points"][0]["counts"]
            assert all(0 <= count <= reached[key] for key, count in point["counts"].items())
        absent = [key for key, count in point["counts"].items() if not count]
        if absent:
            missing[instance] = absent
    assert set(missing) == {"lsq.load_queue_rar.checked"}
    assert set(missing["lsq.load_queue_rar.checked"]) == set(issue["unpassed_scenarios"])
    auditors = {}
    for tool in (Path(__file__), ROOT / "tools/coverage_audit.py"):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool), "do not overwrite historical auditor"
        else:
            shutil.copy2(tool, dest)
        auditors[str(dest.relative_to(run))] = sha(dest)
    report = {"run": name, "status": "evidence_audited_with_failures", "suite_acceptance": "NOT_PASS",
              "scope": "all currently implemented 195 tests on 11 independent DUTs, not complete LSQ scope or parent integration",
              "tests": manifest["tests"], "families": dict(families), "native_builds": len(native_ids),
              "functional_groups": len(groups), "missing_semantic_scenarios": missing,
              "source_snapshot_files": len(source["files"]), "manifest_sha256": sha(manifest_path),
              "line_audit_sha256": sha(audit_path), "auditors": auditors, "failures": failed}
    output = run / "evidence-check.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "failures"}, indent=2, ensure_ascii=False))
    print("failure details:", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
