#!/usr/bin/env python3
"""Default-OFF full regression gate; compare streamed hashes, not new raw dumps.

Selected historical native baselines were audited before retention cleanup.
Summary equality proves diagnostic/rerun equivalence only; it is not independent
offline semantic replay of an unretained new trace or producer-domain signoff.
"""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from audit_progress_run_v7 import JOURNALS, failures
from audit_progress_run_v10 import coverage_signature
from audit_sq_initial import ROOT, sha, verify_common


BASELINES=("lsq-progress-regression-11","lsq-ldu-s4-03","lsq-ldu-s4-plain-01")


def indices(run):
    return {e["path"]:e for name in("storage-index-v1.json","reports-storage-index-v1.json")
            if (run/name).exists() for e in json.loads((run/name).read_text())["files"]}


def payload(run,relative):
    path=run/relative
    if path.is_file():return path.read_bytes()
    e=indices(run)[relative]
    obj=ROOT/e["object"]
    assert sha(obj)==e["object_SHA256"]
    data=subprocess.check_output(["zstd","-q","-d","-c",str(obj)])
    assert len(data)==e["bytes"] and sha256(data).hexdigest()==e["SHA256"]
    return data


def nodes(run):
    cases=list(ET.parse(run/"pytest.xml").iter("testcase"))
    assert all(c.find("error") is None and c.find("skipped") is None for c in cases)
    return {c.attrib["classname"].replace(".","/")+".py::"+c.attrib["name"]:c.find("failure") is not None for c in cases}


def baseline_metadata(run):
    m=json.loads((run/"execution/manifest.json").read_text())
    assert m["state"]=="committed" and m["coverage_complete"] and m["cleanup_complete"]
    for artifact in m["artifacts"]:
        path=Path(artifact["path"])
        assert sha256(payload(run,str(path.relative_to(run)))).hexdigest()==artifact["sha256"]
    source=json.loads((run/"source-evidence.json").read_text())["files"]
    assert all(sha(run/"verification-source"/p)==h for p,h in source.items())
    end=json.loads((run/"end-source-check.json").read_text())
    assert end["files"]==source and end["all_current_launch_files_match_snapshot"]
    return m,source,nodes(run)


def audit():
    run=ROOT/"results/lsq-progress-regression-12"
    m,source,current=verify_common(run)
    assert len(current)==2203 and m["tests"]=={"PASS":1982,"FAIL":221}
    command=json.loads((run/"command.json").read_text())["command"]
    assert "tests" in command and not any(a in("-k","--lsq-trace","--lsq-waves") or a.startswith("--deselect") for a in command)
    assert not list((run/"cases").rglob("*.jsonl")) and not list((run/"cases").rglob("*.fst"))
    policy=json.loads((run/"trace-policy.json").read_text())
    assert not policy["per_cycle_JSON"] and not policy["waveforms"]
    expected_nodes={};expected_failures={};expected_histories={f:Counter() for f in JOURNALS};prior_lines={};old_coverage={}
    for name in BASELINES:
        prior=ROOT/"results"/name
        _,_,ns=baseline_metadata(prior)
        assert not expected_nodes.keys()&ns.keys()
        expected_nodes.update(ns);expected_failures.update(failures(prior))
        for e in indices(prior).values():
            for family,names in JOURNALS.items():
                if Path(e["path"]).name in names:expected_histories[family][(e["SHA256"],e["bytes"])]+=1
        for row in json.loads(payload(prior,"line-audit.json"))["native"]:
            for file,(h,lines) in coverage_signature(row).items():
                per=prior_lines.setdefault(row["dut"],{})
                if file in per:assert per[file][0]==h and per[file][1].keys()==dict(lines).keys()
                dst=per.setdefault(file,(h,{}))[1]
                for n,hit in lines:dst[n]=dst.get(n,False) or hit
        for group in json.loads((prior/"execution/functional-coverage.json").read_text())["groups"]:
            old_coverage.setdefault(group["instance"],set()).update(k for k,c in group["points"][0]["counts"].items() if c)
    assert current==expected_nodes and failures(run)==expected_failures and len(expected_failures)==221
    total=records=avoided=summary_bytes=0;history=[]
    for family,names in JOURNALS.items():
        actual=Counter();count=0
        for filename in names:
            for path in (run/"cases").rglob(Path(filename).with_suffix(".summary.json").name):
                s=json.loads(path.read_text())
                assert not s["trace_enabled"] and not s["trace_truncated"] and s["saved_trace_bytes"]==0
                actual[(s["streamed_SHA256"],s["serialized_bytes"])]+=1
                count+=1;records+=s["records"];avoided+=s["serialized_bytes"];summary_bytes+=path.stat().st_size
        assert actual==expected_histories[family],(family,"full serialized stream changed: investigate; do not waive differences")
        total+=count;history.append(dict(DUT_journal_family=family,matching_streams=count))
    assert total==2203-87==2116
    actual_lines={r["dut"]:coverage_signature(r) for r in json.loads((run/"line-audit.json").read_text())["native"]}
    assert actual_lines.keys()==prior_lines.keys() and len(actual_lines)==38
    for dut,files in actual_lines.items():
        assert files.keys()==prior_lines[dut].keys()
        for file,(h,lines) in files.items():assert (h,dict(lines))==prior_lines[dut][file]
    groups=json.loads((run/"execution/functional-coverage.json").read_text())["groups"]
    assert len(groups)==76
    for group in groups:
        p=group["points"][0]
        assert group["collection_complete"] and not p["unknown"] and not p["unmatched"]
        assert {k for k,c in p["counts"].items() if c}==old_coverage[group["instance"]]
    report=dict(status="ACTUAL2203_DEFAULT_OFF_REPEATABILITY_NOT_PASS_221_FAILURES_RETAINED",tests=m["tests"],snapshot_files=len(source),
                native_builds=38,functional_groups=76,actual_equal_stream_digests=total,actual_stream_records=records,
                per_cycle_JSON_files=0,waveform_files=0,avoided_raw_bytes=avoided,summary_bytes=summary_bytes,
                each_DUT_original_DA_universe_and_hit_union_equal=True,every_failure_primary_equal=True,
                baselines=list(BASELINES),families=history,auditor_SHA256=sha(Path(__file__)),
                limits="Full serialized stream digest equality is a diagnostic/rerun gate, NOT independently replayed new raw history. Prior source admission rejections stay: invalid hyper/poison/early trap streams are interface evidence, not whole normal S4 admission. All functional FAILs, full random, other128, local-only late response and final whole-goal audit remain.")
    out=run/"evidence-check-summary-v13.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":audit()
