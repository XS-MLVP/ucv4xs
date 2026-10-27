#!/usr/bin/env python3
"""849-test/31-DUT progress integrity audit; NOT complete LSQ acceptance.

The earlier 195/651-test gates and their frozen evidence remain unchanged.
All known defects remain ordinary failures, never waived into a PASS.
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
FAMILIES = dict(age=11, cam=24, freelist=52, rar=54, raw=32, vlq=22, uncache_entry=384,
                load_uncache=72, replay=131, enter_sbuffer=26, unalign=41)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(name):
    run = ROOT / "results" / name
    manifest_path = run / "execution/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    assert manifest["pytest_exitstatus"] == 1 and manifest["tests"] == {"PASS": 830, "FAIL": 19}
    command = json.loads((run / "command.json").read_text())["command"]
    assert {arg for arg in command if arg.startswith("tests/")} == {f"tests/{name}" for name in FAMILIES}
    assert "-k" not in command and not any(arg.startswith("--deselect") for arg in command)
    builds = set()
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            builds.add(artifact["build"]["build_id"])
            for path, digest in artifact["build"]["files"].items():
                assert sha(Path(path)) == digest
    assert len(builds) == 31
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert all(sha(run / "verification-source" / path) == digest for path, digest in source.items())
    issues = {row["id"]: row for row in json.loads((run / "verification-source/manifest/known-issues.json").read_text())["issues"]}
    known = {row["nodeid"]: ("RAR-REL-001", row) for row in issues["RAR-REL-001"]["failure_cases"]}
    known.update({node: ("LQU-SID-001", None) for node in issues["LQU-SID-001"]["failure_cases"]})
    known[issues["LQU-MMIO-IF-001"]["nodeid"]] = ("LQU-MMIO-IF-001", None)
    known.update({node: ("LRQ-STRICT-001", None) for node in issues["LRQ-STRICT-001"]["failure_cases"]})
    assert len(known) == 19 and all(issues[issue]["not_a_waiver"] for issue, _ in known.values())
    xml = ET.parse(run / "pytest.xml").getroot()
    cases = list(xml.iter("testcase"))
    assert len(cases) == sum(FAMILIES.values()) == 849 and not list(xml.iter("skipped")) and not list(xml.iter("error"))
    assert len({(case.attrib["classname"], case.attrib["name"]) for case in cases}) == 849
    families, failed = Counter(), []
    for case in cases:
        families[case.attrib["classname"].split(".")[1]] += 1
        node = case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]
        failure = case.find("failure")
        if failure is None:
            continue
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
        elif issue == "LQU-MMIO-IF-001":
            assert "'io_uncache_req_valid', 0, 1" in message
        elif issue == "LRQ-STRICT-001":
            assert "'io_replay_0_valid', 1, 0" in message
        else:
            raise AssertionError("unreviewed defect family")
        failed.append({"nodeid": node, "issue": issue, "domain": "UNIT-INTERFACE only, not normal ROB traffic" if issue == "LQU-MMIO-IF-001" else "required normal semantics"})
    assert families == Counter(FAMILIES) and {row["nodeid"] for row in failed} == set(known)
    lines_path = run / "line-audit.json"
    lines = json.loads(lines_path.read_text())
    assert lines["run"] == name and lines["tests"] == manifest["tests"]
    assert {row["build_id"] for row in lines["native"]} == builds
    for row in lines["native"]:
        if row["dut"] == "load_queue_uncache":
            assert (row["line_hit"], row["line_total"], row["closure_line_hit"], row["closure_line_total"]) == (1120, 1126, 3169, 3175)
        else:
            assert row["line_hit"] == row["line_total"] > 0 and not row["uncovered"]
        for dep in row.get("dependencies", []):
            assert dep["line_hit"] == dep["line_total"] and not dep["uncovered"]
    proof = json.loads((run / "static-gap-proof.json").read_text())
    assert proof["status"] == "six_guarded_defaults_proven" and not proof["remaining_not_proven"] and proof["line_audit_sha256"] == sha(lines_path)
    groups = {row["instance"]: row for row in json.loads((run / "execution/functional-coverage.json").read_text())["groups"]}
    assert len(groups) == 62
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
    assert set(missing) == {"lsq.load_queue_rar.checked", "lsq.load_queue_uncache.checked", "lsq.load_queue_replay.checked"}
    assert set(missing["lsq.load_queue_rar.checked"]) == set(issues["RAR-REL-001"]["unpassed_scenarios"])
    assert set(missing["lsq.load_queue_uncache.checked"]) == set(issues["LQU-SID-001"]["unpassed_scenarios"] + issues["LQU-MMIO-IF-001"]["unpassed_scenarios"])
    assert set(missing["lsq.load_queue_replay.checked"]) == set(issues["LRQ-STRICT-001"]["unpassed_scenarios"])
    auditors = {}
    for tool in (Path(__file__), ROOT / "tools/coverage_audit.py", ROOT / "tools/audit_lqu_static.py"):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool)
        else:
            shutil.copy2(tool, dest)
        auditors[str(dest.relative_to(run))] = sha(dest)
    report = {"run": name, "status": "evidence_audited_with_failures", "suite_acceptance": "NOT_PASS", "tests": manifest["tests"],
              "scope": "849 currently implemented tests on 31 independent DUTs, including real LQU/Replay parents and EnterSbufferQueue/UnalignQueue leaves; excludes ForwardModule functional UT, remaining Store modules and real LoadQueue/StoreQueue/LsqWrapper acceptance; detailed per-module history audits retained separately",
              "families": dict(families), "native_builds": len(builds), "functional_groups": len(groups), "source_snapshot_files": len(source),
              "missing_semantic_scenarios": missing, "manifest_sha256": sha(manifest_path), "line_audit_sha256": sha(lines_path),
              "auditors": auditors, "failure_issues": dict(Counter(row["issue"] for row in failed)), "failures": failed}
    out = run / "evidence-check.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "failures"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
