#!/usr/bin/env python3
"""Phased native programs, fixed public-UID peak dedup and driver/RTL split."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import audit_lsq_ldu_joint_v1 as original
from audit_lsq_ldu_joint_pools_v3 import PhasedPools
from audit_lsq_population_v1 import RAW, events, paths_by_node, same_raw
from audit_progress_run_v7 import failures
from audit_sq_initial import ROOT, sha, verify_common


def inspect(path, *, passed):
    with patch.object(original,"PhasedPools",PhasedPools):
        return original.inspect(path,passed=passed)


def driver_cadence_timeout(path):
    pools=PhasedPools()
    rows=list(events(path))
    for row in rows:pools.step(row)
    result=pools.finish(passed=False)
    counts=result["counts"]
    assert counts["cancelled"]==248 and counts["completed"]==counts["failed_live"]==0
    assert counts["actual_responses"]==12 and counts["pending_external"]==4
    assert len(result["shared_recoveries"])==1 and result["shared_recoveries"][0]["settled"]
    responses=[r["post_tick"] for r in rows if r["input"]["bus"]["response"]]
    assert len(responses)==12 and all(b-a==16 for a,b in zip(responses,responses[1:]))
    return dict(pool_history=result,source_stages=[],original_UID_effect_epochs=[],CBO_permission={},terminal_tick=rows[-1]["post_tick"],terminal_error=None,
                classification="DRIVER_100_EDGE_BOUND_SHORTER_THAN_16_JOBS_AT_PERIOD8_NOT_RTL_FAILURE",actual_response_ticks=responses)


def audit(name):
    assert name in ("lsq-ldu-joint-phases-03","lsq-ldu-joint-phases-04")
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert len(nodes)==12 and manifest["tests"]==({"PASS":4,"FAIL":8} if name.endswith("03") else {"PASS":6,"FAIL":6})
    paths=paths_by_node(run)
    old=ROOT/"results/lsq-ldu-joint-phases-02"
    old_paths=paths_by_node(old)
    old_failures=failures(old)
    current_failures=failures(run)
    previous=ROOT/"results/lsq-ldu-joint-phases-03"
    previous_paths=paths_by_node(previous) if name.endswith("04") else {}
    totals,stages,side_effects=Counter(),Counter(),Counter()
    cases=[]
    for node,path in sorted(paths.items()):
        driver_timeout=name.endswith("03") and "[8-redirect-" in node
        detail=driver_cadence_timeout(path) if driver_timeout else inspect(path,passed=not nodes[node])
        counts=detail["pool_history"]["counts"]
        totals.update(counts)
        for stage in detail["source_stages"]:stages.update(stage["counts"])
        for epoch in detail["original_UID_effect_epochs"]:side_effects.update(epoch.get("counts",{}))
        repeat=None
        if "[1-" in node:
            old_node=next(n for n in old_paths if n.split("[",1)[1]==node.split("[1-",1)[1])
            assert nodes[node] and current_failures[node]==old_failures[old_node]
            repeat=dict(prior_node=old_node,exact_records=same_raw(path,old_paths[old_node]),primary_failure_equal=True)
        elif previous_paths:
            before=list(events(previous_paths[node]))
            after=list(events(path))
            for a,b in zip(before,after):assert all(a[k]==b[k] for k in RAW)
            assert len(after)>=len(before)
            if "-redirect-" not in node:assert len(after)==len(before)
            repeat=dict(prior_node=node,exact_prefix_records=len(before),new_records=len(after)-len(before),change="only adds actual response opportunities after old period8 redirect timeout")
        cases.append(dict(nodeid=node,pytest_result="FAIL" if nodes[node] else "PASS",journal=str(path.relative_to(run)),raw_SHA256=sha(path),actual_repetition=repeat,**detail))
    assert totals["allocated"]==totals["completed"]+totals["cancelled"]+totals["reset_aborted"]+totals["failed_live"]
    successful=[c for c in cases if c["pytest_result"]=="PASS"]
    assert sum(c["pool_history"]["counts"]["completed"] for c in successful)==1104*len(successful)
    assert all(c["pool_history"]["ROB_codes"]==640 for c in successful)
    peaks=Counter(s["kind"] for c in cases for s in c["pool_history"]["snapshots"])
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files=(Path(__file__),ROOT/"tools/audit_lsq_ldu_joint_v1.py",ROOT/"tools/audit_lsq_ldu_joint_pools_v1.py",ROOT/"tools/audit_lsq_ldu_joint_pools_v2.py",ROOT/"tools/audit_lsq_ldu_joint_pools_v3.py",
           ROOT/"tools/audit_lsq_ldu_s3_pipeline_v1.py",ROOT/"tools/audit_lsq_ldu_mixed_history_v1.py",ROOT/"tools/audit_lsq_cbo_serialization_v2.py")
    hashes={}
    for file in files:
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
        hashes[file.name]=sha(file)
    report=dict(run=name,status="REAL_PHASED_CAPACITY_AND_CBO_SOURCE_GATES_REQUIRED_SID_FAILURES_RETAINED_NOT_WHOLE_GOAL_SIGNOFF",tests=manifest["tests"],snapshot_files=len(source),
                counts=dict(totals),S3_source_counts=dict(stages),original_effect_epoch_counts=dict(side_effects),actual_quiescent_snapshot_counts=dict(peaks),
                positive_control_completed_UIDs=1104*len(successful),required_period1_failures=6,positive_control_passes=len(successful),driver_cadence_timeouts=2 if name.endswith("03") else 0,
                cases=cases,auditors=hashes,
                preserved_auditor_rejections="v1 peak key missed same-pointer redirect generations. v2 forced candidate checks again while first STA was leaving a peak. v3 only adds public UID generation to dedup and keeps entry-only assertions; all prior auditors/native failures preserved. Initial01 six service errors,03 two cadence-bound errors are driver failures, not RTL counterexamples.",
                limits="Only clean disjoint scalar positive phases. Original6 immediate-SID-reuse counterexamples are ordinary FAIL, bit-exact to02; slow external response cadence does not extend SID lifetime or replace full8 mixed kinds/errors/aliases/split. Actual source stage, original effects and quiescent records are separate gates. No normal simultaneous RAR96/LRQ120 steady-state claim, blanket half-ring relaxation, leaf numerator merge, STRESS or whole-goal signoff.")
    out=run/"ldu-joint-audit-v2.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
