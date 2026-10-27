#!/usr/bin/env python3
"""Native phased capacity: required failures plus separate positive controls.

Uses independent public UID effects, stage-source gates and exact quiescent
pool histories. Splitting at actual common reset does not edit any raw value.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
from unittest.mock import patch

from audit_lsq_cbo_serialization_v2 import inspect as permission
import audit_lsq_ldu_mixed_history_v1 as effects
from audit_lsq_ldu_joint_pools_v1 import PhasedPools
import audit_lsq_ldu_s3_pipeline_v1 as pipeline
from audit_lsq_normal_cbo_v3 import packages
from audit_lsq_population_v1 import events, paths_by_node, same_raw, validate_row
from audit_sq_initial import ROOT, sha, verify_common


def epochs(rows):
    result,current=[],[]
    allocated=False
    for row in rows:
        if row["input"]["reset"] and allocated:
            result.append(current)
            current=[]
            allocated=False
        current.append(row)
        allocated |= any(d["valid"] for d in row["input"]["dispatch"])
    if current:result.append(current)
    return result


def inspect(path, *, passed):
    rows=list(events(path))
    pools=PhasedPools()
    previous=None
    for index,row in enumerate(rows):
        validate_row(row,previous,False)
        assert row["checked"] or index==len(rows)-1
        if row["checked"]:pools.step(row)
        previous=row
    pool=pools.finish(passed=passed)
    stages,uid_effects=[],[]
    chunks=epochs(rows)
    for index,chunk in enumerate(chunks):
        last=index==len(chunks)-1
        with patch.object(pipeline,"events",lambda _:chunk):
            stage=pipeline.inspect(path,passed=passed and last)
        stages.append(dict(epoch=index,**stage))
        if last:
            with patch.object(effects,"events",lambda _:chunk):
                effect=effects.inspect(path,passed=passed)
            uid_effects.append(dict(epoch=index,UID_base=sum(1 for old in rows[:rows.index(chunk[0])] for d in old["input"]["dispatch"] if d["valid"]),**effect))
        else:
            # This first phase is ended by real common reset: no Store can
            # have retired/consumed or external reply have arrived here.
            assert pool["common_resets"] and all(not r["input"]["bus"]["response"] and not r["input"]["cache_response"] and not any(r["input"]["sbuffer_ready"]) for r in chunk)
            uid_effects.append(dict(epoch=index,terminal="explicit_common_system_reset_abort_not_semantic_completion",original_UIDs=248,external_jobs_aborted=16,
                                   evidence="independent initial snapshot/owners/external tokens in pool audit; full source gate above; no real replies or Store fires in this epoch"))
    cbo=permission(path)
    assert not cbo["violations"]
    cbo["normal_STA_packages"]=packages(path)
    if passed:
        assert sum(s["counts"].get("S3_source_size_lastBeat_writeback_checks",0) for s in stages)>1100
        assert cbo["normal_STA_packages"]==12 and cbo["counts"]["CBO_original_owners_identified_from_actual_STA"]==12
        for snapshot in pools.snapshots:
            if snapshot["kind"]!="LRQ_LQ_peak":continue
            owners=[s for s in pools.history if s["uid"] in snapshot["original_LRQ_UIDs"]]
            assert len(owners)==120 and {s["slot"] for s in owners}==set(range(120)),"full120 actual slot grants/feedback, not just a count"
    else:
        assert uid_effects[-1]["independent_terminal_counterexamples"]
        assert {v["obligation"] for v in uid_effects[-1]["independent_terminal_counterexamples"]}=={"original_SID_data_error_s2"}
    return dict(pool_history=pool,source_stages=stages,original_UID_effect_epochs=uid_effects,CBO_permission=cbo,
                terminal_tick=rows[-1]["post_tick"],terminal_error=rows[-1].get("error"),
                limits="All actual inputs/outputs retained. Counterexamples are ordinary failures; period8 fixed response cadence is an additional positive condition, not a SID lifetime extension, full-domain seed replacement or whole-STRESS/goal acceptance.")


def audit(name):
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert name in ("lsq-ldu-joint-phases-02","lsq-ldu-joint-phases-03")
    paths=paths_by_node(run)
    cases=[]
    totals,stages=Counter(),Counter()
    prior=paths_by_node(ROOT/"results/lsq-ldu-joint-phases-02") if name.endswith("03") else {}
    for node,path in sorted(paths.items()):
        detail=inspect(path,passed=not nodes[node])
        repeat=None
        if "[1-" in node:
            old_node=next(n for n in prior if n.split("[",1)[1]==node.split("[1-",1)[1])
            repeat=dict(prior_node=old_node,raw_records=same_raw(path,prior[old_node]))
        totals.update(detail["pool_history"]["counts"])
        for stage in detail["source_stages"]:stages.update(stage["counts"])
        cases.append(dict(nodeid=node,pytest_result="FAIL" if nodes[node] else "PASS",journal=str(path.relative_to(run)),raw_SHA256=sha(path),required_period1_exact_repeat=repeat,**detail))
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    hashes={}
    for file in(Path(__file__),ROOT/"tools/audit_lsq_ldu_joint_pools_v1.py",ROOT/"tools/audit_lsq_ldu_s3_pipeline_v1.py",ROOT/"tools/audit_lsq_ldu_mixed_history_v1.py",ROOT/"tools/audit_lsq_cbo_serialization_v2.py"):
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
        hashes[file.name]=sha(file)
    report=dict(run=name,status="REAL_SOURCE_PHASES_UID_EFFECTS_AND_REQUIRED_SID_FAILURES_RETAINED_NOT_FULL_GOAL_SIGNOFF",tests=manifest["tests"],snapshot_files=len(source),
                counts=dict(totals),S3_source_counts=dict(stages),cases=cases,auditors=hashes,
                limits="Necessary public source/pool/effect gates only, not native LoadUnit/Backend UT. Old simultaneous RAR96+LRQ120 green snapshots remain rejected. Actual first peak96/56/24/128/120/16 and later120 LRQ transfer must be proven separately. Period1 failures stay; positive cadence does not replace original eight full-kind seeds, STRESS, split-error/late local-only reset or final request audit.")
    out=run/"ldu-joint-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
