#!/usr/bin/env python3
"""Refine the frozen 1312-case v5 evidence gate's failure classification.

pytest's explanatory tail can include a *whole output dictionary*. Merely
finding exceptionVec in that tail is not a WB failure signature. Preserve v5
and give explicit ownership assertions priority over incidental pin names.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from audit_progress_run_v5 import FAMILIES, issue_for
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    run = ROOT / "results" / name
    manifest, source, nodes = verify_common(run)
    previous = run / "evidence-check-v5.json"
    old = json.loads(previous.read_text())
    assert old["tests"] == manifest["tests"] and len(nodes) == sum(FAMILIES.values()) == 1312
    assert old["native_builds"] == 36 and old["functional_groups"] == 72 and old["source_snapshot_files"] == len(source)
    assert old["manifest_sha256"] == sha(run / "execution/manifest.json")
    legacy = {item["nodeid"]: item["issue"] for item in json.loads((ROOT / "results/lsq-progress-regression-04/evidence-check.json").read_text())["failures"]}
    corrected, failures = [], []
    old_by_node = {item["nodeid"]: item for item in old["failures"]}
    for case in ET.parse(run / "pytest.xml").iter("testcase"):
        failure = case.find("failure")
        if failure is None:
            continue
        node = case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]
        message = failure.attrib["message"]
        item = copy.deepcopy(old_by_node[node])
        assert item["signature"] == message
        ownership = any(text in message.split("\n", 1)[0] for text in (
            "young NC/IO finish must not release an unconsumed old PSQ owner",
            "young special completion released an unconsumed older ordinary owner"))
        issue = "DEQ-FINISH-ORDER-001" if ownership else issue_for(node, message, legacy)
        if issue != item["issue"]:
            corrected.append(dict(nodeid=node, previous=item["issue"], corrected=issue,
                                  reason="primary assertion concerns premature SQ ownership release; exceptionVec appears only in pytest's explanatory output dump"))
        item["issue"] = issue
        failures.append(item)
    assert len(failures) == manifest["tests"]["FAIL"] and set(old_by_node) == {item["nodeid"] for item in failures}
    assert len(corrected) == 6 and all(item["previous"] == "DEQ-WB-001" for item in corrected)
    dest = run / "evidence-auditors" / Path(__file__).name
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = {**old, "status": "evidence_audited_with_primary_failure_assertions", "failures": failures,
              "failure_cases_by_issue": dict(Counter(item["issue"] for item in failures)), "classification_corrections": corrected,
              "previous_v5_report_sha256": sha(previous), "classification_auditor_sha256": sha(dest),
              "limits": old["limits"] + " v6 corrects six v5 issue labels only, not outcomes, coverage, domains or source hashes. The 110 cases are not 110 independent architectural defects."}
    out = run / "evidence-check-v6.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("failures", "missing_semantic_scenarios", "classification_corrections", "auditors")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
