#!/usr/bin/env python3
"""Real phased-capacity/effect gates plus serial uncovered-line supplements."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_cbo_serialization_v2 import inspect as permission
from audit_lsq_ldu_joint_v2 import inspect
from audit_lsq_ldu_joint_pools_v3 import PhasedPools
from audit_lsq_ldu_mixed_history_v1 import inspect as effects
from audit_lsq_ldu_s3_pipeline_v1 import inspect as pipeline
from audit_lsq_population_v1 import RAW, events, paths_by_node, same_raw
from audit_progress_run_v7 import failures
from audit_sq_initial import ROOT, sha, verify_common


def driver_timeout(path):
    pools=PhasedPools()
    rows=list(events(path))
    for row in rows:pools.step(row)
    result=pools.finish(passed=False)
    counts=result["counts"]
    assert counts["cancelled"]==248 and counts["completed"]==counts["failed_live"]==0
    assert counts["actual_responses"]==13 and counts["pending_external"]==3
    responses=[r["post_tick"] for r in rows if r["input"]["bus"]["response"]]
    assert len(responses)==13 and all(b-a==16 for a,b in zip(responses,responses[1:]))
    assert len(result["shared_recoveries"])==1 and result["shared_recoveries"][0]["settled"]
    return dict(pool_history=result,source_stages=[],original_UID_effect_epochs=[],CBO_permission={},terminal_tick=rows[-1]["post_tick"],terminal_error=None,
                classification="DRIVER_100_EDGE_BOUND_HAS13_PERIOD8_RESPONSES_3_OWED_NOT_RTL_FAILURE",actual_response_ticks=responses)


def serial(path):
    effect=effects(path,passed=True)
    stage=pipeline(path,passed=True)
    cbo=permission(path)
    assert effect["counts"]["allocated"]==effect["counts"]["completed"]==2 and not cbo["violations"]
    assert effect["counts"]["direction_acks"]==effect["counts"]["sid_responses"]==1
    assert all(not r["input"]["bus"]["outstanding"] for r in events(path) if not r["input"]["reset"])
    return dict(original_UID_effects=effect,source_stage=stage,CBO_permission=cbo)


def audit(name):
    assert name in ("lsq-ldu-joint-phases-03","lsq-ldu-joint-phases-04","lsq-ldu-joint-phases-05")
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    expected={"03":{"PASS":4,"FAIL":8},"04":{"PASS":6,"FAIL":6},"05":{"PASS":21,"FAIL":6}}[name[-2:]]
    assert manifest["tests"]==expected and len(nodes)==sum(expected.values())
    paths=paths_by_node(run)
    old=ROOT/"results/lsq-ldu-joint-phases-02"
    old_paths,old_failures=paths_by_node(old),failures(old)
    current_failures=failures(run)
    previous=ROOT/"results"/("lsq-ldu-joint-phases-04" if name.endswith("05") else "lsq-ldu-joint-phases-03")
    previous_paths=paths_by_node(previous) if not name.endswith("03") else {}
    totals,stages,effect_counts=Counter(),Counter(),Counter()
    serial_totals=Counter()
    cases,serial_cases=[],[]
    for node,path in sorted(paths.items()):
        if "test_ldu_joint_serial.py" in node:
            detail=serial(path)
            serial_totals.update(detail["original_UID_effects"]["counts"])
            serial_cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),raw_SHA256=sha(path),**detail))
            continue
        timeout=name.endswith("03") and "[8-redirect-" in node
        detail=driver_timeout(path) if timeout else inspect(path,passed=not nodes[node])
        totals.update(detail["pool_history"]["counts"])
        for stage in detail["source_stages"]:stages.update(stage["counts"])
        for epoch in detail["original_UID_effect_epochs"]:effect_counts.update(epoch.get("counts",{}))
        repeat=None
        if "[1-" in node:
            old_node=next(n for n in old_paths if n.split("[",1)[1]==node.split("[1-",1)[1])
            assert nodes[node] and current_failures[node]==old_failures[old_node]
            repeat=dict(prior_node=old_node,exact_records=same_raw(path,old_paths[old_node]),primary_failure_equal=True)
        if previous_paths:
            if name.endswith("05"):
                repeat={**(repeat or {}),"prior12_exact_records":same_raw(path,previous_paths[node])}
            elif "[8-" in node:
                before,after=list(events(previous_paths[node])),list(events(path))
                for a,b in zip(before,after):assert all(a[k]==b[k] for k in RAW)
                assert len(after)>=len(before)
                if "-redirect-" not in node:assert len(after)==len(before)
                repeat=dict(prior_node=node,exact_prefix_records=len(before),additional_records=len(after)-len(before))
        cases.append(dict(nodeid=node,pytest_result="FAIL" if nodes[node] else "PASS",journal=str(path.relative_to(run)),raw_SHA256=sha(path),repetition=repeat,**detail))
    assert len(cases)==12 and len(serial_cases)==(15 if name.endswith("05") else 0)
    assert totals["allocated"]==totals["completed"]+totals["cancelled"]+totals["reset_aborted"]+totals["failed_live"]
    successful=[c for c in cases if c["pytest_result"]=="PASS"]
    assert sum(c["pool_history"]["counts"]["completed"] for c in successful)==1104*len(successful)
    peaks=Counter(s["kind"] for c in cases for s in c["pool_history"]["snapshots"])
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files=(Path(__file__),*(ROOT/"tools"/f"audit_lsq_ldu_joint_{suffix}.py" for suffix in ("v1","v2","pools_v1","pools_v2","pools_v3")),
           ROOT/"tools/audit_lsq_ldu_s3_pipeline_v1.py",ROOT/"tools/audit_lsq_ldu_mixed_history_v1.py",ROOT/"tools/audit_lsq_cbo_serialization_v2.py")
    hashes={}
    for file in files:
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
        hashes[file.name]=sha(file)
    report=dict(run=name,status="REAL_PHASED_CAPACITY_CBO_SERIAL_SOURCE_GATES_REQUIRED6_SID_FAIL_RETAINED_NOT_GOAL_SIGNOFF",tests=manifest["tests"],snapshot_files=len(source),
                counts=dict(totals),S3_source_counts=dict(stages),original_effect_epoch_counts=dict(effect_counts),serial_counts=dict(serial_totals),
                actual_quiescent_snapshot_counts=dict(peaks),positive_control_completed_UIDs=1104*len(successful),required_period1_failures=6,
                positive_control_passes=len(successful),driver_cadence_timeouts=2 if name.endswith("03") else 0,cases=cases,serial_cases=serial_cases,auditors=hashes,
                preserved_auditor_rejections="Pool v1 missed same-pointer new UID generation, v2 revalidated a peak on exit; pool v3 only fixes snapshot discriminator. Outer v2 guessed12 replies in100 period8 cycles, actual phase has13; outer v3 checks actual13/3 and retains failure, not changing source/input/output or native outcomes.",
                limits="Positive clean scalar phase/cadence and optional serial cases only. Period1 remains bit-exact ordinary SID FAIL to02, SID lifetime is not extended, original8 full-kind mixed/error/alias/split obligations not replaced. No normal simultaneous RAR96/LRQ120 steady claim, blanket half-ring relaxation, leaf numerator merge, STRESS or whole-goal acceptance. Common reset aborts external jobs explicitly, not local-only late-response proof.")
    out=run/"ldu-joint-audit-v3.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in ("cases","serial_cases")},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
