#!/usr/bin/env python3
"""Separate normal completion, fault WB/trap and same-slot replacement proof."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_sq_initial import ROOT,sha,verify_common


def audit(name):
    assert name.startswith("lsq-normal-mixed-source-")
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    prior=json.loads((run/"normal-mixed-summary-audit-v1.json").read_text())
    assert prior["tests"]==manifest["tests"] and len(nodes)==8
    reports=[];totals=Counter();rejected=[];completed=[];all_seeds=set()
    for path in sorted((run/"cases").rglob("normal-mixed-summary.json")):
        d=json.loads(path.read_text());seed=d["seed"];assert seed not in all_seeds;all_seeds.add(seed)
        online=d["independent_source_checks"];states=d["public_UIDs"];observed={s["uid"]:s for s in online["observed_UIDs"]}
        traps={e["uid"]:e for e in online["traps"]};assert len(traps)==len(online["traps"])
        classified=Counter();rows=[];witnesses=[];missing=[]
        for s in states:
            uid=s["uid"];actual=observed.get(uid)
            if d["passed"]:
                assert actual and s["kind"]==("load" if actual["kind"] in("cached","nc_load","mmio_load","io_load") else "store")
                assert (s["order"],s["position"],s["structure_complete"],s["local_abort"] is not None)==(actual["order"],actual["pos"],actual["released"],actual["cancelled"])
            if s["local_abort"] is not None:terminal="structurally_cancelled"
            elif s["structure_complete"]:
                if uid in traps:
                    assert actual and actual["fault_WB"] and s["fault"] and s["rob_cancelled"] and traps[uid]["ROB"]==s["order"]
                    terminal="fault_WB_and_actual_ROB_head_trap"
                elif actual and actual["fault_WB"]:
                    assert s["rob_cancelled"]
                    terminal="fault_WB_then_nontrap_ROB_cancel"
                elif s["rob_cancelled"]:terminal="normal_LSQ_completion_then_ROB_cancel"
                else:terminal="normal_LSQ_completion"
            else:
                assert not d["passed"]
                terminal="unfinished_at_original_FAIL"
            classified[terminal]+=1
            rows.append(dict(uid=uid,kind=s["kind"],ROB=s["order"],queue_position=s["position"],terminal=terminal))
            if s["local_abort"] is not None:
                size=120 if s["kind"]=="load" else 64
                candidates=[n for n in states if n["uid"]>uid and n["kind"]==s["kind"] and n["position"]%size==s["position"]%size and
                            n["structure_complete"] and not observed.get(n["uid"],{}).get("fault_WB",False) and not n["fault"]]
                if candidates:
                    n=candidates[0];witnesses.append(dict(cancelled_UID=uid,new_normally_completed_UID=n["uid"],kind=s["kind"],physical_slot=s["position"]%size))
                else:missing.append(dict(cancelled_UID=uid,kind=s["kind"],physical_slot=s["position"]%size))
        assert sum(classified.values())==len(states)
        if d["passed"]:
            assert d["random_steps_completed"]==600 and online["last_source_error"] is None and online["original_full_output_error"] is None
            assert all(not pool["pending_job_IDs"] for pool in(d["cache_sources"],d["tlb_sources"]))
            assert len(witnesses)+len(missing)==d["counts"].get("cancelled",0)
            if missing:rejected.append(seed)
            else:completed.append(seed);totals.update(classified)
        reports.append(dict(seed=seed,native_result="PASS" if d["passed"] else "FAIL",terminal_counts=dict(classified),
                            UID_terminal_states=rows,same_slot_normal_completion_witnesses=witnesses,missing_normal_completion_witnesses=missing,
                            source_summary_SHA256=sha(path),terminal_evidence_accepted=bool(d["passed"] and not missing)))
    assert all_seeds==set(range(0x7100,0x7108))
    dest=run/"evidence-auditors";dest.mkdir(exist_ok=True);target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(status="NATIVE_PASS_TERMINAL_GATE_REJECTED_FAULT_WB_IS_NOT_NORMAL_REPLACEMENT" if rejected else "ACTUAL_UID_TERMINALS_AND_NORMAL_SAME_SLOT_WITNESSES_AUDITED_RETAIN_NATIVE_FAILS_NO_GOAL_SIGNOFF",
                run=name,tests=manifest["tests"],source_files=len(source),native_pass_seeds=[r["seed"] for r in reports if r["native_result"]=="PASS"],
                accepted_completed_seed_programs=completed,rejected_native_pass_seed_programs=rejected,
                accepted_program_UID_totals=dict(totals),cases=reports,auditor_SHA256=sha(Path(__file__)),
                limits="Fault WB/trap, normal LSQ completion, later ROB cancellation and structural cancellation are disjoint. A new UID releasing its physical slot because of a fault is not a normal replacement witness. Failed prefixes remain partial. Current first vector-QB upstream route still unproven; no whole normal producer or goal signoff. Original native outcomes and v1 report are preserved, not overwritten.")
    output=run/"normal-mixed-UID-audit-v2.json"
    if output.exists():assert json.loads(output.read_text())==report
    else:output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},ensure_ascii=False,indent=2))
    return not rejected


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("name");raise SystemExit(0 if audit(p.parse_args().name) else 1)
