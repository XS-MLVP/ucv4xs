#!/usr/bin/env python3
"""651-test progress integrity gate; independent DUTs, NOT full LSQ acceptance.

Versioned separately so the earlier 195-test auditor and its frozen results
remain untouched. Known issue inventories identify failures, never waive them.
"""
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
    assert manifest["pytest_exitstatus"] == 1 and manifest["tests"] == {"PASS": 636, "FAIL": 15}
    builds = set()
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            builds.add(artifact["build"]["build_id"])
            for path, digest in artifact["build"]["files"].items():
                assert sha(Path(path)) == digest
    assert len(builds) == 28
    source = json.loads((run / "source-evidence.json").read_text())
    for path, digest in source["files"].items():
        assert sha(run / "verification-source" / path) == digest
    issues = {row["id"]: row for row in json.loads((run / "verification-source/manifest/known-issues.json").read_text())["issues"]}
    known = {row["nodeid"]: ("RAR-REL-001", row) for row in issues["RAR-REL-001"]["failure_cases"]}
    known.update({node: ("LQU-SID-001", None) for node in issues["LQU-SID-001"]["failure_cases"]})
    known[issues["LQU-MMIO-IF-001"]["nodeid"]] = ("LQU-MMIO-IF-001", None)
    assert len(known) == 15 and all(issues[key]["not_a_waiver"] for key in issues)
    xml = ET.parse(run / "pytest.xml").getroot()
    cases = list(xml.iter("testcase"))
    assert len(cases) == 651 and not list(xml.iter("error")) and not list(xml.iter("skipped"))
    families, failed = Counter(), []
    for case in cases:
        families[case.attrib["classname"].split(".")[1]] += 1
        node = case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]
        failure = case.find("failure")
        if failure is not None:
            assert node in known
            issue, signature = known[node]
            message = failure.attrib["message"]
            if issue == "RAR-REL-001":
                assert "response.nuke" in message
                actual, expected = re.findall(r"Response\(valid=True, nuke=(True|False)\)", message)
                assert (actual == "True") == signature["actual_nuke"] and (expected == "True") == signature["expected_nuke"]
            elif issue == "LQU-SID-001":
                if "test_old_error_" in node:
                    assert "'io_exceptionInfo_bits_exceptionVec_19', 1, 0" in message
                else:
                    assert re.search(r"'io_bypass_[01]_s2Resp_bits_data'", message)
                    assert str(0xFEDCBA9876543210 * ((1 << 64) + 1)) in message
                    assert str(0x0123456789ABCDEF * ((1 << 64) + 1)) in message
            else:
                assert "'io_uncache_req_valid', 0, 1" in message
            failed.append({"nodeid": node, "issue": issue, "domain": "UNIT-INTERFACE only, not normal ROB traffic" if issue == "LQU-MMIO-IF-001" else "required normal semantics"})
    assert {row["nodeid"] for row in failed} == set(known)
    assert families == Counter(age=11, cam=24, freelist=52, rar=54, raw=32, vlq=22, uncache_entry=384, load_uncache=72)
    lines_path = run / "line-audit.json"
    lines = json.loads(lines_path.read_text())
    assert lines["run"] == name and lines["tests"] == manifest["tests"]
    assert {row["build_id"] for row in lines["native"]} == builds
    for row in lines["native"]:
        if row["dut"] == "load_queue_uncache":
            assert row["line_hit"] == 1120 and row["line_total"] == 1126
            assert row["closure_line_hit"] == 3169 and row["closure_line_total"] == 3175
        else:
            assert row["line_hit"] == row["line_total"] > 0 and not row["uncovered"]
        for dep in row.get("dependencies", []):
            assert dep["line_hit"] == dep["line_total"] and not dep["uncovered"]
    proof = json.loads((run / "static-gap-proof.json").read_text())
    assert proof["status"] == "six_guarded_defaults_proven" and not proof["remaining_not_proven"] and proof["line_audit_sha256"] == sha(lines_path)
    functional = json.loads((run / "execution/functional-coverage.json").read_text())
    groups = {g["instance"]: g for g in functional["groups"]}
    assert len(groups) == 56
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
    assert set(missing) == {"lsq.load_queue_rar.checked", "lsq.load_queue_uncache.checked"}
    assert set(missing["lsq.load_queue_rar.checked"]) == set(issues["RAR-REL-001"]["unpassed_scenarios"])
    assert set(missing["lsq.load_queue_uncache.checked"]) == set(issues["LQU-SID-001"]["unpassed_scenarios"] + issues["LQU-MMIO-IF-001"]["unpassed_scenarios"])
    auditors = {}
    for tool in (Path(__file__), ROOT / "tools/coverage_audit.py", ROOT / "tools/audit_lqu_static.py"):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool), "do not overwrite historical auditor"
        else:
            shutil.copy2(tool, dest)
        auditors[str(dest.relative_to(run))] = sha(dest)
    report = {"run": name, "status": "evidence_audited_with_failures", "suite_acceptance": "NOT_PASS",
              "scope": "651 currently implemented tests on 28 independent DUTs including real LQU parent; integrity/coverage regression, not Replay, Store branch, real LoadQueue or LsqWrapper acceptance; detailed per-module history audits retained separately",
              "tests": manifest["tests"], "families": dict(families), "native_builds": len(builds), "functional_groups": len(groups),
              "missing_semantic_scenarios": missing, "source_snapshot_files": len(source["files"]),
              "manifest_sha256": sha(manifest_path), "line_audit_sha256": sha(lines_path), "auditors": auditors,
              "failure_issues": dict(Counter(row["issue"] for row in failed)), "failures": failed}
    output = run / "evidence-check.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "failures"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
