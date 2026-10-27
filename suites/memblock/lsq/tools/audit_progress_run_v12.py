#!/usr/bin/env python3
"""Exact2036-node gate: actual10 + exclusive75 + correctedS3 26 + phased27.

This is a FUTURE-run gate until a real committed manifest passes it. Journal
families are grouped by DUT filename, not pytest folder: sq_endpoint has raw,
Replay and Wrapper logs and must not be silently omitted or double counted.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import shutil

from audit_progress_run_v11 import FAMILIES as OLD_FAMILIES
from audit_progress_run_v10 import coverage_signature
from audit_progress_run_v7 import JOURNALS, failures, histories
from audit_sq_initial import ROOT, sha, verify_common


FAMILIES={**OLD_FAMILIES,"lsq_wrapper":438,"sq_endpoint":87}
BASELINES=("lsq-progress-regression-10","lsq-raw-exclusive-06","lsq-ldu-s3-01","lsq-ldu-joint-phases-05")


def audit(name):
    assert name=="lsq-progress-regression-11"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":1821,"FAIL":215} and len(nodes)==sum(FAMILIES.values())==2036
    command=json.loads((run/"command.json").read_text())["command"]
    assert "tests" in command and not any(a=="-k" or a.startswith("--deselect") for a in command)
    directories=[ROOT/"results"/n for n in BASELINES]
    previous={d:verify_common(d) for d in directories}
    old_nodes,old_failures={},{}
    for directory,(_,_,part) in previous.items():
        assert not old_nodes.keys()&part.keys()
        old_nodes.update(part)
        old_failures.update(failures(directory))
    assert nodes==old_nodes and failures(run)==old_failures and len(old_failures)==215
    node_counts=Counter(n.split("/")[1] for n in nodes)
    assert node_counts==Counter(FAMILIES)
    journal_reports=[]
    journals=records=mapped=0
    # Existing helper scans a complete run for these DUT filenames. New tests
    # in sq_endpoint are therefore included exactly once in their real DUT.
    for family in JOURNALS:
        expected=Counter()
        expected_nodes={}
        for directory in directories:
            before,by_node=histories(directory,family)
            expected.update(before)
            assert not expected_nodes.keys()&by_node.keys()
            expected_nodes.update(by_node)
        actual,actual_nodes=histories(run,family)
        assert actual==expected and actual_nodes==expected_nodes,(family,"public raw multiset/node mapping changed")
        count=sum(actual.values())
        length=sum(n*copies for (_,n),copies in actual.items())
        journals+=count
        records+=length
        mapped+=len(actual_nodes)
        journal_reports.append(dict(DUT_journal_family=family,filenames=list(JOURNALS[family]),journals=count,records=length,exact_node_mappings=len(actual_nodes),
                                    raw_multiset=[dict(sha256=h,records=n,copies=c) for (h,n),c in sorted(actual.items())]))
    assert journals==1949==len(nodes)-87
    native={r["dut"]:r for r in json.loads((run/"line-audit.json").read_text())["native"]}
    expected={}
    for directory in directories:
        for row in json.loads((directory/"line-audit.json").read_text())["native"]:
            signature=coverage_signature(row)
            target=expected.setdefault(row["dut"],{})
            for file,(digest,lines) in signature.items():
                if file in target:assert target[file][0]==digest and target[file][1].keys()==dict(lines).keys()
                dst=target.setdefault(file,(digest,{}))[1]
                for n,hit in lines:dst[n]=dst.get(n,False) or hit
    assert native.keys()==expected.keys() and len(native)==38
    for dut,row in native.items():
        actual=coverage_signature(row)
        assert actual.keys()==expected[dut].keys()
        for file,(digest,lines) in actual.items():assert expected[dut][file]==(digest,dict(lines)),(dut,file,"own original DA universe/hits not baseline execution union")
    builds={a["build"]["build_id"] for a in manifest["artifacts"] if a["kind"]=="native"}
    assert len(builds)==38
    groups={g["instance"]:g for g in json.loads((run/"execution/functional-coverage.json").read_text())["groups"]}
    assert len(groups)==76
    expected_points={}
    for directory in directories:
        for group in json.loads((directory/"execution/functional-coverage.json").read_text())["groups"]:
            expected_points.setdefault(group["instance"],set()).update(k for k,c in group["points"][0]["counts"].items() if c)
    missing={}
    for instance,group in groups.items():
        p=group["points"][0]
        assert group["collection_complete"] and not p["unknown"] and not p["unmatched"]
        assert {k for k,c in p["counts"].items() if c}==expected_points[instance]
        if instance.endswith("checked"):
            reached=groups[instance.removesuffix("checked")+"reached"]["points"][0]["counts"]
            assert all(c<=reached[k] for k,c in p["counts"].items())
        absent=[k for k,c in p["counts"].items() if not c]
        if absent:missing[instance]=absent
    for path in(run/"verification-source/tests").rglob("*.py"):assert not re.search(r"pytest\.(?:mark\.)?(?:xfail|skip)\b",path.read_text())
    domain_files=[ROOT/"results/lsq-ldu-s3-01/ldu-s3-audit-v1.json",ROOT/"results/lsq-ldu-joint-phases-05/ldu-joint-audit-v3.json",
                  ROOT/"results/lsq-ldu-joint-phases-05/ldu-joint-coverage-audit-v2.json",ROOT/"results/lsq-joint-capacity-04/joint-producer-audit-v1.json",
                  ROOT/"results/lsq-raw-exclusive-06/exclusive-pool-audit-v1.json"]
    assert all(p.is_file() for p in domain_files)
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    hashes={}
    for file in(Path(__file__),ROOT/"tools/audit_progress_run_v11.py",ROOT/"tools/audit_progress_run_v10.py",ROOT/"tools/audit_progress_run_v7.py",ROOT/"tools/coverage_audit.py"):
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
        hashes[file.name]=sha(file)
    report=dict(run=name,status="ACTUAL2036_NODE_REPEATABILITY_NOT_PASS_215_FAILURES_RETAINED_DOMAIN_GATES_STAY",tests=manifest["tests"],snapshot_files=len(source),
                native_builds=38,functional_groups=76,actual_raw_journals_equal=journals,actual_raw_records_equal=records,exact_node_mappings=mapped,basic87_without_persisted_raw=87,
                every_primary_failure_equal=True,each_DUT_original_DA_universe_and_hits_equal_actual_baseline_union=True,pytest_family_counts=dict(node_counts),
                baselines={d.name:sha(d/"execution/manifest.json") for d in directories},domain_reports={str(p.relative_to(ROOT)):sha(p) for p in domain_files},
                missing_semantics=missing,journal_families=journal_reports,auditors=hashes,
                limits="Exact committed10+75+26+27 union. Every baseline input/observed output and ordinary failure retained; new source-valid contexts do not retroactively admit old incorrect producers. Positive period8/serial/control passes do not waive period1 SID failures or the original six mixed failures. No full-STRESS/goal signoff, split-error/other128/local-only late-reset/final request audit still required.")
    out=run/"evidence-check-v12.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="journal_families"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
