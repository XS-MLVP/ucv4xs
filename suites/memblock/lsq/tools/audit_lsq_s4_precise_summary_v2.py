#!/usr/bin/env python3
"""Source-correct invalid payload and closed external Cache jobs, actual72.

No per-cycle trace generation or fictitious offline replay. Runtime checker
source and every terminal UID witness remain independently inspectable.
"""
import ast
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_s4_precise_summary_v1 import PAGE_PATTERNS, WORD_PATTERNS
from audit_progress_run_v7 import failures
from audit_sq_initial import ROOT, sha, verify_common


def terminal(detail):
    states=detail["UID_terminal_states"];by={s["uid"]:s for s in states}
    assert len(by)==len(states)==detail["allocated_UIDs"]
    assert all(s["structure_released"]!=s["structure_cancelled"] for s in states)
    assert all(not s["fault_WB"] or s["head_trapped"] for s in states)
    normal=sum(s["structure_released"] and not s["fault_WB"] for s in states)
    fault=sum(s["head_trapped"] for s in states)
    cancelled=sum(s["structure_cancelled"] and not s["head_trapped"] for s in states)
    assert normal==detail["normal_completed_UIDs"] and fault==detail["fault_WB_and_head_trap_UIDs"] and cancelled==detail["pure_cancelled_UIDs"]
    assert normal+fault+cancelled==len(states)
    witnesses=detail["same_slot_completion_witnesses"]
    assert {w["cancelled_UID"] for w in witnesses}=={s["uid"] for s in states if s["structure_cancelled"]}
    for w in witnesses:
        a,b=by[w["cancelled_UID"]],by[w["new_completed_UID"]]
        assert a["uid"]<b["uid"] and b["structure_released"] and not b["fault_WB"] and a["physical_slot"]==b["physical_slot"]==w["physical_LQ_slot"]
    for trap in detail["traps"]:
        s=by[trap["fault_UID"]]
        assert s["head_trapped"] and s["ROB_absolute"]==trap["ROB_absolute"] and trap["older_Store_still_unconsumed"]
        assert s["structure_released"]==trap["fault_LQ_released_before_trap"]
    counts=detail["counts"]
    assert counts.get("declared_original_Cache_jobs",0)==counts.get("actual_original_Cache_refills",0)
    assert counts.get("declared_external_prefetch_jobs",0)==counts.get("actual_background_Cache_refills",0)
    assert detail["declared_cache_jobs_remaining"]==0
    assert counts.get("actual_replay_grants",0)==counts.get("actual_original_slot_feedbacks",0)


def audit(name):
    assert name=="lsq-s4-precise-02"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run);assert len(nodes)==72
    frozen=run/"verification-source/tests/lsq_wrapper"
    tree=ast.parse((frozen/"s4_precise_check.py").read_text())
    assert all(n.module in("collections","dataclasses") for n in tree.body if isinstance(n,ast.ImportFrom))
    assert not any(isinstance(n,ast.Attribute) and n.attr in("model","last_change","expected_before","expected_after","dut","_instances") for n in ast.walk(tree))
    controller=ast.parse((frozen/"ldu_s4_precise_owners.py").read_text())
    cycle=next(n for n in ast.walk(controller) if isinstance(n,ast.AsyncFunctionDef) and n.name=="cycle")
    assert len(cycle.body)==3 and isinstance(cycle.body[1].value,ast.Await) and cycle.body[2].value.func.attr=="observe"
    shared=json.loads((ROOT/"results/lsq-progress-regression-12/source-evidence.json").read_text())["files"]
    assert all(source[k]==v for k,v in shared.items() if k.startswith('lsqverify/'))
    assert not list((run/"cases").rglob("*.jsonl")) and not list((run/"cases").rglob("*.fst"))
    expected={(lane,page,name) for lane in range(3) for page,patterns in((False,(*WORD_PATTERNS,"both_miss")),(True,(*PAGE_PATTERNS,"both_miss"))) for name in patterns}
    totals=Counter();semantic=Counter();seen=set();actual=set();cases=[];native_records=0
    for file in sorted((run/"cases").rglob("s4-precise-summary.json")):
        result=json.loads(file.read_text());node=result["nodeid"];case=result["case"]
        assert node in nodes and node not in seen;seen.add(node)
        key=(case["lane"],case["page"],case["pattern"])
        assert key in expected and key not in actual;actual.add(key)
        assert result["passed"]==bool(not nodes[node])
        native=json.loads(file.with_name("lsq_wrapper.summary.json").read_text())
        assert native["nodeid"]==node and not native["trace_enabled"] and not native["saved_trace_bytes"]
        detail=result["independent_online_checks"];counts=detail["counts"]
        # Fixture reports ten boot samples. Yielding the fixture to the test
        # adds one autonomous idle sample before its first dispatch. The core
        # fixture still checks that sample; this observer handles requests.
        assert counts["cycles"]==native["records"]-result["native_boot_records"]-1-int(native["terminal"].get("checked") is False)
        assert result["native_boot_records"]==10
        totals.update(counts);native_records+=native["records"]
        if result["passed"]:
            terminal(detail)
            assert counts["actual_original_Sbuffer_fires"]==counts["actual_original_SQ_releases"]==1
            semantic.update({f:detail[f] for f in("allocated_UIDs","normal_completed_UIDs","fault_WB_and_head_trap_UIDs","pure_cancelled_UIDs","structurally_cancelled_UIDs")})
        cases.append(dict(nodeid=node,result="FAIL" if nodes[node] else "PASS",case=case,summary_SHA256=sha(file),
                          native_records=native["records"],stream_SHA256=native["streamed_SHA256"],online_terminal=detail,error=result["error"]))
    assert seen==set(nodes) and actual==expected
    if not any(nodes.values()):
        assert manifest["tests"]=={"PASS":72}
        assert semantic==Counter(allocated_UIDs=345,normal_completed_UIDs=249,fault_WB_and_head_trap_UIDs=48,pure_cancelled_UIDs=48,structurally_cancelled_UIDs=57)
        for key,n in dict(source_S4_joins=180,source_actual_query_pairs=360,actual_LQ_structure_releases=216,precise_ROB_head_traps=48,
                          actual_replay_grants=27,actual_original_slot_feedbacks=27,declared_original_Cache_jobs=24,actual_original_Cache_refills=24,
                          declared_external_prefetch_jobs=6,actual_background_Cache_refills=6,wrong_tail_refill_did_not_wake_head=12).items():assert totals[key]==n,(key,totals[key],n)
    report=dict(status="ACTUAL72_PRECISE_S4_AND_CACHE_JOB_CHECKS_NOT_WHOLE_GOAL_SIGNOFF" if not any(nodes.values()) else "PRECISE_S4_FAILURES_RETAINED_NO_SIGNOFF",
                run=name,tests=manifest["tests"],snapshot_files=len(source),native_records=native_records,online_counts=dict(totals),UID_terminal_counts=dict(semantic),
                source_checker_runs_after_every_program_request=True,initial_autonomous_idle_samples_checked_by_core_fixture=72,
                per_cycle_JSON=0,waveforms=0,source_checker_SHA256=source["tests/lsq_wrapper/s4_precise_check.py"],
                failures=failures(run),cases=cases,auditor_SHA256=sha(Path(__file__)),
                limits="Online independent public-history checks plus terminal witnesses, not unretained raw offline replay. Each external Cache job is a declared producer assumption with actual LSQ refill input; not native Cache/TLB/ROB/LoadUnit proof. Old01 five invalid-payload checker FAILs remain unchanged; normal random, other128/local-only/full request audit stay.")
    dest=run/"evidence-auditors";dest.mkdir(exist_ok=True)
    for file in(Path(__file__),ROOT/"tools/audit_lsq_s4_precise_summary_v1.py"):
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
    output=run/"s4-precise-summary-audit-v2.json"
    if output.exists():assert json.loads(output.read_text())==report
    else:output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2))


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("name");audit(p.parse_args().name)
