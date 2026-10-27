#!/usr/bin/env python3
"""Audit retained external jobs independently from compact actual-event witnesses.

Does not recreate discarded per-cycle raw or treat this isolated reset profile
as proof of native MemBlock/Uncache/TileLink reset-domain integration.
"""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_progress_run_v7 import failures
from audit_sq_initial import ROOT, sha, verify_common


PHASES=("empty_after_reset","new_mid_wait_response","new_response_wait_bypass","new_bypass_s1")


def audit(name):
    assert name in("lsq-local-reset-retained-01","lsq-local-reset-retained-02")
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert len(nodes)==12
    base=json.loads((ROOT/"results/lsq-progress-regression-12/source-evidence.json").read_text())["files"]
    shared=[k for k in base if k.startswith("lsqverify/")]
    assert all(source[k]==base[k] for k in shared)
    frozen=run/"verification-source/tests/local_reset"
    reference=ast.parse((frozen/"reference.py").read_text())
    cls=next(n for n in reference.body if isinstance(n,ast.ClassDef))
    assert [n.name for n in cls.body if isinstance(n,ast.FunctionDef)]==["advance"]
    assert ast.unparse(cls.bases[0])=="WrapperModel"
    assert not any(isinstance(n,ast.Attribute) and n.attr in("expected","connected","safety","compare","masks","known") for n in ast.walk(cls))
    checker=ast.parse((frozen/"check.py").read_text())
    assert not any(isinstance(n,ast.Attribute) and n.attr in("model","last_change","expected_before","expected_after","dut","_instances") for n in ast.walk(checker))
    assert all(n.module=="collections" for n in checker.body if isinstance(n,ast.ImportFrom))
    fixture=(frozen/"conftest.py").read_text()
    assert "WrapperEnv(" in fixture and "PublicProbeEnv" not in fixture and "RetainedExternalLoadJobs()" in fixture
    totals=Counter();seen=set();cases=set();reports=[];native_records=summary_bytes=0
    for file in sorted((run/"cases").rglob("local-reset-summary.json")):
        result=json.loads(file.read_text());node=result["nodeid"];lane=result["lane"];phase=result["phase"]
        assert node in nodes and node not in seen;seen.add(node)
        assert (lane,phase) not in cases and lane in range(3) and phase in PHASES;cases.add((lane,phase))
        assert result["passed"]==bool(not nodes[node])
        native=json.loads(file.with_name("lsq_wrapper.summary.json").read_text())
        assert native["nodeid"]==node and not native["trace_enabled"] and not native["trace_truncated"] and native["saved_trace_bytes"]==0
        detail=result["online_check"];c=detail["counts"]
        native_records+=native["records"];summary_bytes+=file.stat().st_size
        if result["passed"]:
            window=detail["request_window"]
            assert window["continuous"] and (window["last_tick"]-window["first_tick"])//2+1==c["checked_program_requests"]
            assert native["records"]==c["checked_program_requests"]+result["native_boot_records"]+1
            assert native["terminal"]["post_tick"]==window["last_tick"] and native["terminal"]["checked"]
            for key,n in dict(actual_source_pipeline_S3s=5,actual_external_requests=3,actual_external_acks=3,local_reset_events=1,local_reset_edges=6,
                              actual_new_responses=2,actual_old_discarded_responses=1,actual_original_grants=2,actual_original_bypass_data=2,
                              original_slot_S3_feedbacks=2,actual_new_LQ_dequeues=2).items():assert c[key]==n,(key,c[key])
            assert detail["UIDs"]==[dict(uid=1,generation=0,LQ=0,ROB=10,terminal="local-reset-aborted"),
                                    dict(uid=2,generation=1,LQ=0,ROB=20,terminal="normal-completed"),
                                    dict(uid=3,generation=1,LQ=1,ROB=22,terminal="normal-completed")]
            assert detail["same_slot_completion_witnesses"]==[dict(old_UID=1,new_completed_UID=2,physical_LQ_slot=0)]
            jobs=detail["external_jobs"];assert [j["owner_UID"] for j in jobs]==[1,2,3]
            assert jobs[0]["mid"]==jobs[1]["mid"]==0 and jobs[0]["sid"]==jobs[2]["sid"]!=jobs[1]["sid"]
            assert all(j["returned"] and j["consumed"]!=j["discarded"] for j in jobs)
            assert jobs[0]["discarded"] and not jobs[0]["consumed"] and not any(j["discarded"] for j in jobs[1:])
            events=detail["events"];assert all(events[i]["tick"]<=events[i+1]["tick"] for i in range(len(events)-1))
            ledger={};live_sid={};terminated=set();by_kind={}
            for e in events:
                by_kind.setdefault(e["event"],[]).append(e)
                if e["event"]=="external_request":
                    assert e["job"] not in ledger
                    ledger[e["job"]]=dict(uid=e["uid"],mid=e["mid"],accepted=e["tick"],sid=None,returned=None)
                elif e["event"]=="external_ack":
                    j=ledger[e["job"]];assert j["sid"] is None and e["sid"] not in live_sid
                    j["sid"]=e["sid"];live_sid[e["sid"]]=e["job"]
                elif e["event"]=="local_reset_external_jobs_retained":
                    assert e["UIDs"]==[1] and e["external_live_jobs"]==[1] and live_sid
                    terminated.add(1)  # Only the local Load, not ledger/SID.
                elif e["event"]=="actual_response":
                    assert live_sid.pop(e["sid"])==e["job"]
                    j=ledger[e["job"]];assert j["uid"]==e["uid"] and j["returned"] is None
                    j["returned"]=e["tick"]
                    assert e["discarded"]==(e["uid"] in terminated) and not(e["error"] and e["nderr"])
                elif e["event"] in("grant","bypass_metadata","bypass_data","normal_completed"):
                    assert e["uid"] in(2,3) and e["uid"] not in terminated
                    job=next(j for j in jobs if j["owner_UID"]==e["uid"])
                    assert job["returned"]<e["tick"]
                    if e["event"]=="bypass_data":assert e["data"]==job["data"]*((1<<64)+1) and e["error"]==e["nderr"]==0
            assert not live_sid and len(ledger)==3
            for job in jobs:
                history=ledger[job["job"]]
                assert (history["uid"],history["mid"],history["sid"],history["accepted"],history["returned"])==(job["owner_UID"],job["mid"],job["sid"],job["accepted"],job["returned"])
            old=jobs[0]["returned"];fresh=jobs[1]["returned"]
            meta=next(e["tick"] for e in by_kind["bypass_metadata"] if e["uid"]==2)
            dispatch=next(e["tick"] for e in by_kind["dispatch"] if e["uid"]==2)
            ack=next(e["tick"] for e in by_kind["external_ack"] if e["job"]==2)
            if phase=="empty_after_reset":assert old<dispatch
            elif phase=="new_mid_wait_response":assert ack<old<fresh
            elif phase=="new_response_wait_bypass":assert fresh<old<meta
            else:assert old==meta+2==next(e["tick"] for e in by_kind["bypass_data"] if e["uid"]==2)
            totals.update(c)
        reports.append(dict(nodeid=node,result="FAIL" if nodes[node] else "PASS",summary=str(file.relative_to(run)),SHA256=sha(file),runtime_stream_SHA256=native["streamed_SHA256"],error=result["error"]))
    assert seen==set(nodes) and cases=={(lane,phase) for lane in range(3) for phase in PHASES}
    assert not list((run/"cases").rglob("*.jsonl")) and not list((run/"cases").rglob("*.fst")) and not list((run/"cases").rglob("*.vcd"))
    dest=run/"evidence-auditors";dest.mkdir(exist_ok=True);target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(status="LOCAL_RESET_RETAINED_EXTERNAL_PROFILE_AUDITED_NOT_SOC_RESET_SIGNOFF",run=name,tests=manifest["tests"],snapshot_files=len(source),
                preserved_shared_reference_files=len(shared),actual_online_counts=dict(totals),native_records=native_records,summary_bytes=summary_bytes,
                allocated_UIDs=3*sum(not failed for failed in nodes.values()),normal_completed_UIDs=2*sum(not failed for failed in nodes.values()),
                local_reset_aborted_UIDs=sum(not failed for failed in nodes.values()),external_jobs_aborted=0,same_slot_new_UID_witnesses=sum(not failed for failed in nodes.values()),
                cases=reports,failures=failures(run),per_cycle_JSON=0,waveforms=0,auditor_SHA256=sha(Path(__file__)),
                limits="Full-output native WrapperEnv inherited; only external already-acked NC job ledger survives reset in this opt-in fixture. Compact actual events audited, not offline replay of unretained raw or native MemBlock/Uncache/TL reset-domain proof. Late old ack, serial Store reset and full random/128/whole request audit remain.")
    out=run/"local-reset-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("name");audit(p.parse_args().name)
