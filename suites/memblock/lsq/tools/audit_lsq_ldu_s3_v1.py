import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Actual26 S3-source reruns, original UID effects, necessary producer gates.

No DUT/reference/actor-state oracle. Old outcomes/normal-domain rejections stay.
"""
import argparse
import ast
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import shutil

from audit_lsq_cbo_serialization_v2 import inspect as serialization
from audit_lsq_ldu_mixed_history_v1 import inspect as effects
from audit_lsq_ldu_s3_pipeline_v1 import inspect as pipeline
from audit_lsq_normal_cbo_v3 import packages
from audit_lsq_population_v1 import events, paths_by_node
from audit_progress_run_v7 import failures
from audit_sq_initial import ROOT, sha, verify_common


def compare_source_fields(before,after):
    a,b=list(events(before)),list(events(after))
    assert len(a)==len(b)
    changes,outputs=Counter(),Counter()
    examples={}
    for x,y in zip(a,b):
        assert (x["pre_tick"],x["post_tick"])==(y["pre_tick"],y["post_tick"])
        old=deepcopy(x["input"])
        for lane,load in enumerate(old["loads"]):
            if not load["execution"]["valid"]:continue
            for key in("aligned_type","last_beat"):
                value=y["input"]["loads"][lane]["execution"][key]
                changes[key]+=load["execution"][key]!=value
                load["execution"][key]=value
            value=y["input"]["loads"][lane]["update_address"]
            changes["update_address"]+=load["update_address"]!=value
            load["update_address"]=value
        assert old==y["input"],"program/traffic changed beyond source S3 metadata"
        assert x["pins"].keys()==y["pins"].keys()
        for key in x["pins"]:
            if x["pins"][key]!=y["pins"][key]:
                assert key.startswith("io_ldu_ldin_") and key.endswith(("_bits_alignedType","_bits_rep_info_last_beat","_bits_updateAddrValid")),key
        for phase in("before","after"):
            assert x[phase].keys()==y[phase].keys()
            for key in x[phase]:
                if x[phase][key]!=y[phase][key]:
                    outputs[key]+=1
                    examples.setdefault(key,dict(tick=x["post_tick"],phase=phase,old=x[phase][key],new=y[phase][key]))
    return dict(records=len(a),only_three_source_S3_input_fields_changed=dict(changes),actual_public_output_changes=dict(outputs),first_output_difference_examples=examples)


def full_RAR_program(path):
    rows=list(events(path))
    accepted=set()
    original={}
    head=0
    peak=0
    for row in rows:
        i,pre,post=row["input"],row["before"],row["after"]
        for d in i["dispatch"]:
            if d["valid"]:
                assert d["need_alloc"]==1 and d["flows"]==1
                pos=120*int(d["load_start"]["flag"])+d["load_start"]["value"]
                assert pos not in original
                original[pos]=d["rob"]
        assert not i["redirect"]["valid"] and not any((*i["rar_revoke_last"],*i["rar_revoke_older"]))
        for lane,q in enumerate(i["rar_queries"]):
            if q["valid"]:
                pos=120*int(q["lq"]["flag"])+q["lq"]["value"]
                assert q["rob"]==original[pos] and pre[f"io_ldu_rarNukeQuery_{lane}_req_ready"]
                if pos>head:
                    assert pos not in accepted
                    accepted.add(pos)
        peak=max(peak,len(accepted))
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            head+=post["io_toLsqEnqCtrl_lqDeq_bits"]
            accepted={n for n in accepted if n>head}
    assert len(original)==head==97 and peak==96 and not accepted
    return dict(original_Load_UIDs_completed=97,peak_public_RAR_ownership=96,internal_slot_reads=False)


def audit(name):
    assert name=="lsq-ldu-s3-01"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":17,"FAIL":9} and len(nodes)==26
    mixed_old=ROOT/"results/lsq-ldu-mixed-02"
    rar_old=ROOT/"results/lsq-ldu-rar-routing-03"
    old_m,old_s,old_n=verify_common(mixed_old)
    old_r,rar_s,rar_n=verify_common(rar_old)
    assert old_m["tests"]=={"PASS":2,"FAIL":6} and old_r["tests"]=={"PASS":15,"FAIL":3}
    for old in(old_s,rar_s):
        assert all(source[k]==v for k,v in old.items() if k.startswith("lsqverify/")),"shared reference changed"
    frozen=run/"verification-source/tests/lsq_wrapper"
    old_functions={n.name:ast.dump(n,include_attributes=False) for file in("test_ldu_rar_routing.py","test_ldu_rar_capacity.py")
                   for n in ast.parse((frozen/file).read_text()).body if isinstance(n,ast.AsyncFunctionDef)}
    new_functions={n.name:ast.dump(n,include_attributes=False) for n in ast.parse((frozen/"test_ldu_s3_rar.py").read_text()).body if isinstance(n,ast.AsyncFunctionDef)}
    assert len(new_functions)==4 and old_functions==new_functions
    actor=ast.parse((frozen/"ldu_s3_owners.py").read_text())
    assert not any(isinstance(n,ast.Attribute) and n.attr in("rng","model","last_change","pre_observed","observed") for n in ast.walk(actor))
    assert "range(0x7100,0x7108)" in (frozen/"test_ldu_s3_mixed.py").read_text()
    paths=paths_by_node(run)
    old_paths=paths_by_node(mixed_old)
    old_rpaths=paths_by_node(rar_old)
    failures_now,failures_m,failures_r=failures(run),failures(mixed_old),failures(rar_old)
    totals,stage_totals,field_changes=Counter(),Counter(),Counter()
    mixed_totals,rar_totals,permissions=Counter(),Counter(),Counter()
    cases=[]
    complete_seeds=[]
    for node,path in sorted(paths.items()):
        is_mixed="test_ldu_s3_mixed.py" in node
        if is_mixed:
            seed=int(node.rsplit("[",1)[1][:-1])
            old_node=next(n for n in old_paths if n.endswith(f"[{seed}]"))
            old_path=old_paths[old_node]
            old_failed=old_n[old_node]
            prior_failure=failures_m.get(old_node)
        else:
            tail=node.split("::",1)[1]
            old_node=next(n for n in old_rpaths if n.split("::",1)[1]==tail)
            old_path=old_rpaths[old_node]
            old_failed=rar_n[old_node]
            prior_failure=failures_r.get(old_node)
        assert nodes[node]==old_failed and failures_now.get(node)==prior_failure
        observed=compare_source_fields(old_path,path)
        field_changes.update(observed["only_three_source_S3_input_fields_changed"])
        assert not observed["actual_public_output_changes"],observed["first_output_difference_examples"]
        detail=effects(path,passed=not nodes[node])
        stage=pipeline(path,passed=not nodes[node])
        assert detail["counts"]["raw_records"]==stage["counts"]["raw_records"]==observed["records"]
        totals.update(detail["counts"])
        stage_totals.update(stage["counts"])
        if is_mixed:
            mixed_totals.update(detail["counts"])
            permission=serialization(path)
            assert not permission["violations"]
            permissions.update(permission["counts"])
            permissions["CBO_STA_packages"]+=packages(path)
            if not nodes[node]:complete_seeds.append(seed)
        else:
            rar_totals.update(detail["counts"])
            permission=None
        full=full_RAR_program(path) if "full_96_RAR" in node else None
        cases.append(dict(nodeid=node,pytest_result="FAIL" if nodes[node] else "PASS",journal=str(path.relative_to(run)),sha256=sha(path),
                          prior_run=mixed_old.name if is_mixed else rar_old.name,prior_node=old_node,actual_failure_primary_equal=prior_failure,
                          exact_input_field_and_actual_output_comparison=observed,original_effects=detail,retained_S3_pipeline=stage,CBO_permission=permission,full_RAR=full))
    assert sorted(complete_seeds)==[28929,28933]
    assert (totals["raw_records"],totals["allocated"],totals["completed"],totals["cancelled"],totals["failed_live"])==(5233,1070,674,377,19)
    assert (mixed_totals["allocated"],mixed_totals["completed"],mixed_totals["cancelled"],mixed_totals["failed_live"])==(746,359,374,13)
    assert (rar_totals["allocated"],rar_totals["completed"],rar_totals["cancelled"],rar_totals["failed_live"])==(324,315,3,6)
    assert rar_totals["actual_flushAfter"]==rar_totals["cancelled_same_slot_new_UID_completed"]==3
    assert stage_totals["S3_source_size_lastBeat_writeback_checks"]==762 and stage_totals["split_tail_S4_native_revoke_checks"]==18
    assert (field_changes["aligned_type"],field_changes["last_beat"],field_changes["update_address"])==(324,177,210)
    full_pass=[c for c in cases if "s3_mixed.py" in c["nodeid"] and c["pytest_result"]=="PASS"]
    assert sum(c["original_effects"]["counts"]["cancelled_same_slot_new_UID_completed"] for c in full_pass)==148
    source_file=ucv_paths.source_path_for(ROOT) / 'src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala'
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    hashes={}
    for file in(Path(__file__),ROOT/"tools/audit_lsq_ldu_s3_pipeline_v1.py",ROOT/"tools/audit_lsq_ldu_mixed_history_v1.py"):
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
        hashes[file.name]=sha(file)
    report=dict(run=name,status="REAL26_S3_SOURCE_RELATION_RERUNS_17PASS9FAIL_RETAINED_NOT_FULL_RANDOM_OR_GOAL_SIGNOFF",tests=manifest["tests"],snapshot_files=len(source),counts=dict(totals),
                mixed_counts=dict(mixed_totals),RAR_counts=dict(rar_totals),S3_pipeline_counts=dict(stage_totals),exact_source_input_field_changes=dict(field_changes),
                all26_actual_public_pre_post_output_histories_bitwise_equal=True,all9_primary_failure_signatures_equal=True,
                complete_original_mixed_seeds=sorted(complete_seeds),complete_seed_cancelled_same_slot_new_UID_witnesses=148,
                full_RAR_original_Load_UIDs_completed=291,CBO_permission_counts=dict(permissions),open_LDU_source_SHA256=sha(source_file),auditors=hashes,cases=cases,
                limits="Actual26 required-node reruns only. Old results/source-admission rejections preserved; only3 S3 fields changed and ALL observed outputs/old9 failures equal. Necessary retained full-kind gates now include first-uncache vs noQuery replay, exception/matchInvalid and18 cached S4 joins, not native LoadUnit/DCache/Backend proof or ungenerated split-error coverage. Six original mixed seeds still strict FAIL; two real600/fair/148 same-slot passes do not complete full8/STRESS. Joint all-pool/CBO phases, other recovery/exact128 and final complete request audit remain.")
    out=run/"ldu-s3-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
