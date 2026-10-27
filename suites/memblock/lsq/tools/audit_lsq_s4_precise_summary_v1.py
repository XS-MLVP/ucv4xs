#!/usr/bin/env python3
"""Audit bounded precise-S4 terminal witnesses and frozen online checker.

No per-cycle trace is created or claimed. Native stream summaries attest how
many cycles ran; independent checks executed online on public input/output.
"""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_progress_run_v7 import failures
from audit_sq_initial import ROOT, sha, verify_common


PAGE_PATTERNS=("clean","head_af","tail_af","head_pf","tail_pf","head_af_tail_pf","head_pf_tail_af", "head_af_tail_nack",
               "head_pf_tail_nack","head_nack_tail_af","head_nack_tail_pf","head_nack_tail_miss","head_miss_tail_nack","both_pf")
WORD_PATTERNS=("clean","head_af","tail_af","head_af_tail_nack","head_nack_tail_af","head_nack_tail_miss","head_miss_tail_nack","both_pf")


def audit(name):
    assert name=="lsq-s4-precise-01"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert len(nodes)==66
    frozen=run/"verification-source/tests/lsq_wrapper"
    checker=ast.parse((frozen/"s4_precise_check.py").read_text())
    assert not any(isinstance(n,ast.Attribute) and n.attr in("model","last_change","expected_before","expected_after","dut","_instances") for n in ast.walk(checker))
    assert all(n.module in("collections","dataclasses") for n in checker.body if isinstance(n,ast.ImportFrom))
    assert not any(isinstance(n,ast.Import) for n in checker.body)
    controller=ast.parse((frozen/"ldu_s4_precise_owners.py").read_text())
    cycle=next(n for n in ast.walk(controller) if isinstance(n,ast.AsyncFunctionDef) and n.name=="cycle")
    assert len(cycle.body)==3 and isinstance(cycle.body[1],ast.Expr) and isinstance(cycle.body[1].value,ast.Await)
    assert isinstance(cycle.body[2],ast.Expr) and cycle.body[2].value.func.attr=="observe"
    shared=json.loads((ROOT/"results/lsq-progress-regression-12/source-evidence.json").read_text())["files"]
    assert all(source[k]==v for k,v in shared.items() if k.startswith("lsqverify/"))
    assert not list((run/"cases").rglob("*.jsonl")) and not list((run/"cases").rglob("*.fst"))
    expected={(lane,page,pattern) for lane in range(3) for page,patterns in((False,WORD_PATTERNS),(True,PAGE_PATTERNS)) for pattern in patterns}
    totals=Counter();semantic=Counter();actual=set();seen=set();cases=[]
    for file in sorted((run/"cases").rglob("s4-precise-summary.json")):
        result=json.loads(file.read_text());node=result["nodeid"];case=result["case"]
        assert node in nodes and node not in seen;seen.add(node)
        triple=(case["lane"],case["page"],case["pattern"])
        assert triple in expected and triple not in actual;actual.add(triple)
        assert result["passed"]==bool(not nodes[node])
        native=json.loads(file.with_name("lsq_wrapper.summary.json").read_text())
        assert native["nodeid"]==node and not native["trace_enabled"] and not native["trace_truncated"] and not native["saved_trace_bytes"]
        detail=result["independent_online_checks"];counts=detail["counts"]
        unchecked=int(native["terminal"].get("checked") is False)
        # _drive_one awaits its first FallingEdge: the monitor records one
        # initial autonomous sample, then boot's six resets + four idles.
        assert counts["cycles"]==native["records"]-11-unchecked
        totals.update(counts)
        if result["passed"]:
            states=detail["UID_terminal_states"]
            assert len(states)==detail["allocated_UIDs"]==len({s["uid"] for s in states})
            assert all(s["structure_released"]!=s["structure_cancelled"] for s in states)
            assert all(not s["fault_WB"] or s["head_trapped"] for s in states)
            normal=sum(s["structure_released"] and not s["fault_WB"] for s in states)
            faults=sum(s["head_trapped"] for s in states)
            cancel=sum(s["structure_cancelled"] and not s["head_trapped"] for s in states)
            assert normal==detail["normal_completed_UIDs"] and faults==detail["fault_WB_and_head_trap_UIDs"] and cancel==detail["pure_cancelled_UIDs"]
            assert normal+faults+cancel==len(states)
            cancelled={s["uid"] for s in states if s["structure_cancelled"]}
            assert cancelled=={w["cancelled_UID"] for w in detail["same_slot_completion_witnesses"]}
            by_uid={s["uid"]:s for s in states}
            for witness in detail["same_slot_completion_witnesses"]:
                old,new=by_uid[witness["cancelled_UID"]],by_uid[witness["new_completed_UID"]]
                assert old["uid"]<new["uid"] and new["structure_released"] and not new["fault_WB"] and old["physical_slot"]==new["physical_slot"]==witness["physical_LQ_slot"]
            assert counts["actual_original_Sbuffer_fires"]==counts["actual_original_SQ_releases"]==1
            for trap in detail["traps"]:
                assert trap["older_Store_still_unconsumed"] and by_uid[trap["fault_UID"]]["head_trapped"]
                assert by_uid[trap["fault_UID"]]["ROB_absolute"]==trap["ROB_absolute"]
                assert trap["fault_LQ_released_before_trap"]==by_uid[trap["fault_UID"]]["structure_released"]
            for field in("allocated_UIDs","normal_completed_UIDs","fault_WB_and_head_trap_UIDs","pure_cancelled_UIDs","structurally_cancelled_UIDs"):
                semantic[field]+=detail[field]
        cases.append(dict(nodeid=node,result="FAIL" if nodes[node] else "PASS",summary_SHA256=sha(file),native_records=native["records"],
                          full_runtime_stream_SHA256=native["streamed_SHA256"],case_summary_bytes=file.stat().st_size,
                          terminal_semantics=detail,first_failure=result["error"]))
    assert seen==set(nodes) and actual==expected
    if not any(nodes.values()):
        assert manifest["tests"]=={"PASS":66}
        assert semantic==Counter(allocated_UIDs=321,normal_completed_UIDs=225,fault_WB_and_head_trap_UIDs=48,pure_cancelled_UIDs=48,structurally_cancelled_UIDs=57)
        assert totals["actual_LQ_structure_releases"]==198 and totals["precise_ROB_head_traps"]==48
        assert totals["source_S4_joins"]==162 and totals["actual_replay_grants"]==totals["actual_original_slot_feedbacks"]==21
    dest=run/"evidence-auditors";dest.mkdir(exist_ok=True)
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(status="ACTUAL_PRECISE_S4_ONLINE_CHECKS_NOT_WHOLE_GOAL_SIGNOFF" if not any(nodes.values()) else "PRECISE_S4_FAILURES_RETAINED_NO_SIGNOFF",
                run=name,tests=manifest["tests"],snapshot_files=len(source),online_check_counts=dict(totals),terminal_UID_counts=dict(semantic),
                preserved_reference_files=len([k for k in shared if k.startswith("lsqverify/")]),source_checker_SHA256=source["tests/lsq_wrapper/s4_precise_check.py"],
                uncompressed_per_cycle_traces=0,waveforms=0,case_summary_bytes=sum(c["case_summary_bytes"] for c in cases),
                failures=failures(run),auditor_SHA256=sha(Path(__file__)),cases=cases,
                limits="Independent checker runs online on actual public input/output. Compact terminal witnesses and full stream hashes are NOT an offline replay of unretained new raw. Chosen stable TLB/cache stimuli are boundary assumptions, not native upstream LDU/TLB/DCache/ROB proof. External cache refill ownership/profile still requires separate review. No existing random seed/FAIL/other128/local-only or final whole-goal scope is waived.")
    out=run/"s4-precise-summary-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("name");audit(p.parse_args().name)
