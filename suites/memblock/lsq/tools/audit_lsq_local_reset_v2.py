#!/usr/bin/env python3
"""All16 retained old responses: actual SID ledger, same-slot completion, impact.

The first12 actual streams must remain identical to the audited first batch.
Only terminal/event witnesses, not unretained full-cycle raw, are replayed here.
"""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    assert name=="lsq-local-reset-retained-02"
    run=ROOT/"results"/name;prior=ROOT/"results/lsq-local-reset-retained-01"
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":15} and len(nodes)==15 and not any(nodes.values())
    old_audit=json.loads((prior/"local-reset-audit-v1.json").read_text())
    assert old_audit["tests"]=={"PASS":12}
    old={json.loads(p.read_text())["nodeid"]:(p,json.loads(p.read_text())) for p in(prior/"cases").rglob("local-reset-summary.json")}
    expected_shared=json.loads((ROOT/"results/lsq-progress-regression-12/source-evidence.json").read_text())["files"]
    assert all(source[k]==h for k,h in expected_shared.items() if k.startswith('lsqverify/'))
    frozen=run/"verification-source/tests/local_reset"
    tree=ast.parse((frozen/"check.py").read_text())
    assert all(n.module=="collections" for n in tree.body if isinstance(n,ast.ImportFrom))
    assert not any(isinstance(n,ast.Attribute) and n.attr in("model","last_change","dut","expected_before","expected_after","_instances") for n in ast.walk(tree))
    reference=ast.parse((frozen/"reference.py").read_text());cls=next(n for n in reference.body if isinstance(n,ast.ClassDef))
    assert [n.name for n in cls.body if isinstance(n,ast.FunctionDef)]==["advance"] and ast.unparse(cls.bases[0])=="WrapperModel"
    # Both operands belong to frozen historical snapshots, not current files.
    assert source["tests/local_reset/reference.py"]==json.loads((prior/"source-evidence.json").read_text())["files"]["tests/local_reset/reference.py"]
    seen=set();rotations=set();impact=set();total=Counter();native_records=summary_bytes=0;reports=[]
    for file in sorted((run/"cases").rglob("local-reset-summary.json")):
        result=json.loads(file.read_text());node=result["nodeid"]
        assert node in nodes and node not in seen and result["passed"];seen.add(node)
        native_path=file.with_name("lsq_wrapper.summary.json");native=json.loads(native_path.read_text())
        assert native["nodeid"]==node and not native["trace_enabled"] and not native["trace_truncated"] and native["saved_trace_bytes"]==0 and native["terminal"]["checked"]
        detail=result["online_check"];c=detail["counts"];native_records+=native["records"];summary_bytes+=file.stat().st_size
        assert native["records"]==c["checked_program_requests"]+result["native_boot_records"]+1
        window=detail["request_window"];assert window["continuous"] and window["last_tick"]==native["terminal"]["post_tick"]
        assert window["last_tick"]-window["first_tick"]==2*(c["checked_program_requests"]-1)
        if node in old:
            old_path,previous=old[node];prior_native=json.loads(old_path.with_name("lsq_wrapper.summary.json").read_text())
            assert native["streamed_SHA256"]==prior_native["streamed_SHA256"] and native["serialized_bytes"]==prior_native["serialized_bytes"]
            assert result==previous,"first12 semantic/event witnesses changed"
            impact.add(node)
        else:
            lane=result["lane"];assert lane in range(3) and lane not in rotations and result["phase"]=="full16";rotations.add(lane)
            states=detail["UIDs"];by={s["uid"]:s for s in states};assert set(by)==set(range(1,33))
            for uid,s in by.items():
                assert s["LQ"]==(uid-1)%16 and s["generation"]==int(uid>16)
                assert s["terminal"]==("normal-completed" if uid>16 else "local-reset-aborted")
            assert detail["same_slot_completion_witnesses"]==[dict(old_UID=i,new_completed_UID=i+16,physical_LQ_slot=i-1) for i in range(1,17)]
            counts=dict(actual_source_pipeline_S3s=48,actual_external_requests=32,actual_external_acks=32,local_reset_events=1,local_reset_edges=6,
                        actual_old_discarded_responses=16,actual_new_responses=16,actual_original_grants=16,actual_original_bypass_data=16,
                        original_slot_S3_feedbacks=16,actual_new_LQ_dequeues=16)
            assert all(c[k]==n for k,n in counts.items())
            jobs=detail["external_jobs"];assert len(jobs)==32 and {j["owner_UID"] for j in jobs}==set(by)
            assert {j["sid"] for j in jobs[:16]}=={j["sid"] for j in jobs[16:]}==set(range(16))
            assert {j["mid"] for j in jobs[:16]}=={j["mid"] for j in jobs[16:]}==set(range(16))
            events=detail["events"];assert len(events)<512
            outstanding={};live_sid={};replayed={};reset_tick=None;old_returns=set();new_completed=set();last_tick=-1;max_live=0
            for e in events:
                assert e["tick"]>=last_tick;last_tick=e["tick"]
                kind=e["event"]
                if kind=="external_request":
                    assert e["job"] not in replayed
                    j=dict(uid=e["uid"],mid=e["mid"],accepted=e["tick"],sid=None,returned=None)
                    replayed[e["job"]]=j;outstanding[e["job"]]=j
                elif kind=="external_ack":
                    j=outstanding[e["job"]]
                    assert e["sid"] not in live_sid and j["sid"] is None
                    if j["uid"]>16:assert e["sid"] in old_returns,"new SID must first have its actual old response, not an abort"
                    j["sid"]=e["sid"];live_sid[e["sid"]]=e["job"];max_live=max(max_live,len(live_sid))
                elif kind=="local_reset_external_jobs_retained":
                    assert reset_tick is None and len(live_sid)==16 and set(e["UIDs"])==set(range(1,17)) and len(e["external_live_jobs"])==16
                    reset_tick=e["tick"]  # Do not clear external jobs or SIDs.
                elif kind=="actual_response":
                    assert live_sid.pop(e["sid"])==e["job"]
                    j=outstanding.pop(e["job"]);assert j["uid"]==e["uid"] and j["returned"] is None;j["returned"]=e["tick"]
                    if e["uid"]<=16:
                        assert e["discarded"] and reset_tick<e["tick"] and e["error"]!=e["nderr"]
                        old_returns.add(e["sid"])
                    else:
                        assert not e["discarded"] and not(e["error"] or e["nderr"])
                        assert e["data"]==0x1020304050607000+by[e["uid"]]["LQ"]
                elif kind in("grant","bypass_metadata","bypass_data","normal_completed"):
                    assert e["uid"]>16 and e["uid"] not in new_completed
                    job=next(j for j in jobs if j["owner_UID"]==e["uid"])
                    assert job["returned"]<e["tick"]
                    if kind=="bypass_data":assert e["data"]==job["data"]*((1<<64)+1) and not(e["error"] or e["nderr"])
                    if kind=="normal_completed":new_completed.add(e["uid"])
            assert not outstanding and not live_sid and old_returns==set(range(16)) and new_completed==set(range(17,33)) and max_live==16
            for j in jobs:
                r=replayed[j["job"]]
                assert (r["uid"],r["mid"],r["sid"],r["accepted"],r["returned"])==(j["owner_UID"],j["mid"],j["sid"],j["accepted"],j["returned"])
                assert j["discarded"]==(j["owner_UID"]<=16) and j["consumed"]!=(j["discarded"])
        total.update(c)
        reports.append(dict(nodeid=node,summary=str(file.relative_to(run)),SHA256=sha(file),stream_SHA256=native["streamed_SHA256"],phase=result["phase"],lane=result["lane"]))
    assert seen==set(nodes) and impact==set(old) and rotations==set(range(3))
    assert not list((run/"cases").rglob("*.jsonl")) and not list((run/"cases").rglob("*.fst")) and not list((run/"cases").rglob("*.vcd"))
    report=dict(status="ACTUAL15_LOCAL_RESET_EXTERNAL_FULL16_AUDITED_NOT_SOC_OR_WHOLE_GOAL_SIGNOFF",run=name,tests=manifest["tests"],snapshot_files=len(source),
                preserved_shared_reference_files=sum(k.startswith('lsqverify/') for k in expected_shared),first12_native_streams_and_semantic_witnesses_equal=True,
                counts=dict(total),native_records=native_records,allocated_UIDs=132,normal_completed_UIDs=72,local_reset_aborted_UIDs=60,
                external_jobs_aborted=0,same_slot_new_UID_completion_witnesses=60,case_summary_bytes=summary_bytes,per_cycle_JSON=0,waveforms=0,cases=reports,
                auditor_SHA256=sha(Path(__file__)),limits="Three full16 programs replay compact actual events/SID ownership, first12 exact actual streams unchanged. Full-output comparisons and source checks execute online, not offline unretained raw replay. Retained external NC profile, not native SoC reset/late-old-ack/serial Store proof. Full random/other128/old-generation/final whole-request audit remain.")
    assert total["actual_external_requests"]==total["actual_external_acks"]==total["actual_old_discarded_responses"]+total["actual_new_responses"]==132
    assert total["actual_old_discarded_responses"]==60 and total["actual_new_LQ_dequeues"]==total["actual_original_grants"]==72
    dest=run/"evidence-auditors";dest.mkdir(exist_ok=True);target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    out=run/"local-reset-audit-v2.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("name");audit(p.parse_args().name)
