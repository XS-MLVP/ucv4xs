#!/usr/bin/env python3
"""1075-test/33-DUT progress gate; preserves every older gate and failure."""
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
                load_uncache=72, replay=131, enter_sbuffer=26, unalign=41, forward=184, vsq=42)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(name):
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    assert manifest["pytest_exitstatus"] == 1 and manifest["tests"] == {"PASS": 1035, "FAIL": 40}
    command = json.loads((run / "command.json").read_text())["command"]
    assert {arg for arg in command if arg.startswith("tests/")} == {f"tests/{family}" for family in FAMILIES}
    assert "-k" not in command and not any(arg.startswith("--deselect") for arg in command)
    builds = set()
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            builds.add(artifact["build"]["build_id"])
            assert all(sha(Path(path)) == digest for path, digest in artifact["build"]["files"].items())
    assert len(builds) == 33
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert all(sha(run / "verification-source" / path) == digest for path, digest in source.items())
    end = json.loads((run / "end-source-check.json").read_text())
    assert end["all_current_launch_files_match_snapshot"] and end["files"] == source
    issues = {item["id"]: item for item in json.loads((run / "verification-source/manifest/known-issues.json").read_text())["issues"]}
    issue_ids = {"RAR-REL-001", "LQU-SID-001", "LQU-MMIO-IF-001", "LRQ-STRICT-001", "FWD-ALIAS-001", "FWD-SQID-001", "FWD-RANGE-001", "VSQ-REDIR-IF-001"}
    assert set(issues) == issue_ids and all(item["not_a_waiver"] for item in issues.values())
    known = {}
    for key, issue in issues.items():
        nodes = issue.get("failure_cases", [issue.get("nodeid")])
        for node in nodes:
            signature = node if isinstance(node, dict) else None
            nodeid = node["nodeid"] if signature else node
            assert nodeid and nodeid not in known
            known[nodeid] = (key, signature)
    assert len(known) == 40
    xml = ET.parse(run / "pytest.xml").getroot()
    tests = list(xml.iter("testcase"))
    assert len(tests) == sum(FAMILIES.values()) == 1075 and not list(xml.iter("skipped")) and not list(xml.iter("error"))
    nodes = [case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"] for case in tests]
    assert len(set(nodes)) == len(nodes)
    families, failed = Counter(), []
    for nodeid, case in zip(nodes, tests, strict=True):
        families[case.attrib["classname"].split(".")[1]] += 1
        failure = case.find("failure")
        if failure is None:
            continue
        issue, signature = known[nodeid]
        message = failure.attrib["message"]
        if issue == "RAR-REL-001":
            assert "response.nuke" in message
            actual, expected = re.findall(r"Response\(valid=True, nuke=(True|False)\)", message)
            assert (actual == "True") == signature["actual_nuke"] and (expected == "True") == signature["expected_nuke"]
        elif issue == "LQU-SID-001":
            if "test_old_error_" in nodeid:
                assert "'io_exceptionInfo_bits_exceptionVec_19', 1, 0" in message
            else:
                assert re.search(r"'io_bypass_[01]_s2Resp_bits_data'", message)
                assert str(0xFEDCBA9876543210 * ((1 << 64) + 1)) in message and str(0x0123456789ABCDEF * ((1 << 64) + 1)) in message
        elif issue == "LQU-MMIO-IF-001":
            assert "'io_uncache_req_valid', 0, 1" in message
        elif issue == "LRQ-STRICT-001":
            assert "'io_replay_0_valid', 1, 0" in message
        elif issue in ("FWD-ALIAS-001", "FWD-RANGE-001"):
            assert "'forward-physical-byte-safety'" in message
            if issue == "FWD-RANGE-001":
                assert "'no physical producer'" in message
            else:
                assert "'newest physical', 1" in message
        elif issue == "FWD-SQID-001":
            assert re.search(r"'io_query_[012]_s2Resp_bits_dataInvalid_bits_first_flag', 1, 0", message)
        elif issue == "VSQ-REDIR-IF-001":
            assert "'io_toPhysicalQueue_redirectPtr_bits_value', 2, 1" in message
        else:
            raise AssertionError("unreviewed issue family")
        interface = issue in ("LQU-MMIO-IF-001", "VSQ-REDIR-IF-001") or nodeid in issues["FWD-RANGE-001"].get("unit_interface_only_cases", [])
        failed.append({"nodeid": nodeid, "issue": issue, "domain": "UNIT-INTERFACE-only" if interface else "producer-domain"})
    assert families == Counter(FAMILIES) and {row["nodeid"] for row in failed} == set(known)
    lines = json.loads((run / "line-audit.json").read_text())
    assert lines["run"] == name and lines["tests"] == manifest["tests"] and {row["build_id"] for row in lines["native"]} == builds
    for row in lines["native"]:
        if row["dut"] == "load_queue_uncache":
            assert (row["line_hit"], row["line_total"], row["closure_line_hit"], row["closure_line_total"]) == (1120, 1126, 3169, 3175)
        else:
            assert row["line_hit"] == row["line_total"] > 0 and not row["uncovered"]
        for dep in row.get("dependencies", []):
            assert dep["line_hit"] == dep["line_total"] and not dep["uncovered"]
    proof = json.loads((run / "static-gap-proof.json").read_text())
    assert proof["status"] == "six_guarded_defaults_proven" and not proof["remaining_not_proven"] and proof["line_audit_sha256"] == sha(run / "line-audit.json")
    groups = {group["instance"]: group for group in json.loads((run / "execution/functional-coverage.json").read_text())["groups"]}
    assert len(groups) == 66
    missing = {}
    for instance, group in groups.items():
        point = group["points"][0]
        assert group["collection_complete"] and not point["unknown"] and not point["unmatched"]
        if instance.endswith("checked"):
            reached = groups[instance.removesuffix("checked") + "reached"]["points"][0]["counts"]
            assert all(count <= reached[key] for key, count in point["counts"].items())
        absent = {key for key, count in point["counts"].items() if not count}
        if absent:
            missing[instance] = sorted(absent)
    expected_missing = {}
    for issue in issues.values():
        expected_missing.setdefault(f"lsq.{issue['dut']}.checked", set()).update(issue["unpassed_scenarios"])
    assert {key: set(value) for key, value in missing.items()} == expected_missing
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
              "scope": "1075 implemented tests on 33 independent DUTs, now including ForwardModule and VirtualStoreQueue; excludes Deq functional UT and real PSQ/StoreQueue/LoadQueue/LsqWrapper acceptance; no earlier gate or source snapshot overwritten",
              "families": dict(families), "native_builds": len(builds), "functional_groups": len(groups), "source_snapshot_files": len(source),
              "manifest_sha256": sha(run / "execution/manifest.json"), "line_audit_sha256": sha(run / "line-audit.json"), "end_source_check_sha256": sha(run / "end-source-check.json"),
              "missing_semantic_scenarios": missing, "failure_issues": dict(Counter(row["issue"] for row in failed)), "failure_domains": dict(Counter(row["domain"] for row in failed)),
              "auditors": auditors, "failures": failed}
    out = run / "evidence-check.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        with out.open("x") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
            output.write("\n")
    print(json.dumps({key: value for key, value in report.items() if key != "failures"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
