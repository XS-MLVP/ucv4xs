#!/usr/bin/env python3
"""1312-case/36-native-DUT progress gate, NOT complete LSQ acceptance.

Adds Deq/PSQ/real StoreQueue to the immutable 1075-case v4 scope. Checks
actual failures and signatures; the issue document is never a test oracle.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

from audit_sq_initial import ROOT, sha, verify_common
from prepare_rtl import pinned_index

FAMILIES = dict(age=11, cam=24, freelist=52, rar=54, raw=32, vlq=22, uncache_entry=384,
                load_uncache=72, replay=131, enter_sbuffer=26, unalign=41, forward=184, vsq=42,
                deq=92, psq=66, store_queue=79)


def issue_for(node, message, old):
    if node in old:
        issue = old[node]
        signature = {"RAR-REL-001": "response.nuke", "LQU-SID-001": "io_", "LQU-MMIO-IF-001": "io_uncache_req_valid",
                     "LRQ-STRICT-001": "io_replay_0_valid", "FWD-ALIAS-001": "newest physical", "FWD-RANGE-001": "no physical producer",
                     "FWD-SQID-001": "dataInvalid_bits_first_flag", "VSQ-REDIR-IF-001": "io_toPhysicalQueue_redirectPtr_bits_value"}[issue]
        assert signature in message, (node, message)
        return issue
    assert node.split("/")[1] in ("deq", "psq", "store_queue"), (node, message)
    if "forward-physical-byte-safety" in message:
        return "FWD-RANGE-001" if "no physical producer" in message else "FWD-ALIAS-001"
    if "dataInvalid_bits_first_flag" in message:
        return "FWD-SQID-001"
    if "bits_wline" in message:
        assert "[1, 0]" in message or ", 1, 0" in message
        return "DEQ-SPLIT-WLINE-001"
    if "exceptionVec_7" in message or "exceptionVec_19" in message:
        return "DEQ-WB-001"
    if "req_flush" in message or "without its own" in message or "own zero write" in message:
        return "DEQ-ZERO-001"
    if "io_sqDeqCnt" in message or "io_sqDeqPtr_" in message or "unconsumed old" in message or "unconsumed older" in message:
        return "DEQ-FINISH-ORDER-001"
    raise AssertionError(("unreviewed_failure_not_whitelisted", node, message))


def audit(name):
    run = ROOT / "results" / name
    manifest, source, nodes = verify_common(run)
    assert manifest["pytest_exitstatus"] == 1 and sum(manifest["tests"].values()) == sum(FAMILIES.values()) == len(nodes) == 1312
    command = json.loads((run / "command.json").read_text())["command"]
    assert {arg for arg in command if arg.startswith("tests/")} == {f"tests/{family}" for family in FAMILIES}
    assert "-k" not in command and not any(arg.startswith("--deselect") for arg in command)
    old_report = ROOT / "results/lsq-progress-regression-04/evidence-check.json"
    old = {item["nodeid"]: item["issue"] for item in json.loads(old_report.read_text())["failures"]}
    assert len(old) == 40 and set(old) <= set(nodes)
    cases = list(ET.parse(run / "pytest.xml").iter("testcase"))
    families, failures = Counter(), []
    for case in cases:
        node = case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]
        families[node.split("/")[1]] += 1
        failure = case.find("failure")
        if failure is not None:
            message = failure.attrib["message"]
            issue = issue_for(node, message, old)
            interface = issue in ("LQU-MMIO-IF-001", "VSQ-REDIR-IF-001") or "test_seeded_in_window_nonalias_concurrent_byte_queries" in node
            failures.append({"nodeid": node, "issue": issue, "domain": "UNIT-INTERFACE-only" if interface else "module-producer-boundary_not_architecture_proof", "signature": message})
    assert families == Counter(FAMILIES) and set(old) <= {item["nodeid"] for item in failures}
    assert len(failures) == manifest["tests"]["FAIL"] and manifest["tests"]["PASS"] == len(nodes) - len(failures)
    lines = json.loads((run / "line-audit.json").read_text())
    native = {row["dut"]: row for row in lines["native"]}
    builds = {artifact["build"]["build_id"] for artifact in manifest["artifacts"] if artifact["kind"] == "native"}
    assert len(native) == len(builds) == 36 and builds == {row["build_id"] for row in native.values()}
    for row in native.values():
        if row["dut"] == "load_queue_uncache":
            assert (row["line_hit"], row["line_total"], row["closure_line_hit"], row["closure_line_total"]) == (1120, 1126, 3169, 3175)
        else:
            assert row["line_hit"] == row["line_total"] > 0 and not row["uncovered"]
        assert all(dep["line_hit"] == dep["line_total"] and not dep["uncovered"] for dep in row.get("dependencies", []))
    proof = json.loads((run / "static-gap-proof.json").read_text())
    assert proof["status"] == "six_guarded_defaults_proven" and not proof["remaining_not_proven"] and proof["line_audit_sha256"] == sha(run / "line-audit.json")
    groups = {group["instance"]: group for group in json.loads((run / "execution/functional-coverage.json").read_text())["groups"]}
    assert len(groups) == 72
    missing = {}
    for instance, group in groups.items():
        point = group["points"][0]
        assert group["collection_complete"] and not point["unknown"] and not point["unmatched"]
        if instance.endswith("checked"):
            reached = groups[instance.removesuffix("checked") + "reached"]["points"][0]["counts"]
            assert all(count <= reached[key] for key, count in point["counts"].items())
        absent = [key for key, count in point["counts"].items() if not count]
        if absent:
            missing[instance] = absent
    assert not any(instance.endswith("reached") for instance in missing), missing
    for path in (run / "verification-source/tests").rglob("*.py"):
        assert not re.search(r"pytest\.(?:mark\.)?(?:xfail|skip)\b", path.read_text()), path
    _, hashes, _, _ = pinned_index()
    assert len(hashes) == 53
    auditors = {}
    for tool in (Path(__file__), ROOT / "tools/audit_sq_initial.py", ROOT / "tools/audit_psq_initial.py", ROOT / "tools/coverage_audit.py", ROOT / "tools/audit_lqu_static.py", ROOT / "tools/prepare_rtl.py"):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool)
        else:
            shutil.copy2(tool, dest)
        auditors[tool.name] = sha(dest)
    result = {"run": name, "status": "evidence_audited_with_real_failures", "suite_acceptance": "NOT_PASS", "tests": manifest["tests"], "families": dict(families),
              "native_builds": len(builds), "functional_groups": len(groups), "source_snapshot_files": len(source), "original_rtl_hashes_checked": len(hashes),
              "manifest_sha256": sha(run / "execution/manifest.json"), "previous_1075_case_evidence_sha256": sha(old_report),
              "failure_cases_by_issue": dict(Counter(item["issue"] for item in failures)), "failure_domains": dict(Counter(item["domain"] for item in failures)),
              "missing_semantic_scenarios": missing, "auditors": auditors, "failures": failures,
              "limits": "1312 implemented cases on 36 independent native DUTs, including real StoreQueue but NOT LoadQueue/LsqWrapper or complete LSQ acceptance. Frozen original 1075/849/651/195-case gates are unchanged. Deq producer domain was widened to actual PSQ permissions; failure counts may legitimately grow. This is evidence/signature/hash coverage audit, not a replacement for detailed per-DUT UID/byte audits or architecture proofs."}
    output = run / "evidence-check-v5.json"
    if output.exists():
        assert json.loads(output.read_text()) == result
    else:
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "failures"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
