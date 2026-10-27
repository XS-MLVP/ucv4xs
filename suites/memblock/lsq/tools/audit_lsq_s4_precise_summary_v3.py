#!/usr/bin/env python3
"""Audit precise-S4 windows, terminal UIDs and actual contiguous generations.

Native inputs/outputs were checked online, not saved for offline replay. This
auditor checks the frozen checker, compact witnesses and native stream summary;
it never substitutes predicted totals for observed native outcomes.
"""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_s4_precise_summary_v1 import PAGE_PATTERNS, WORD_PATTERNS
from audit_lsq_s4_precise_summary_v2 import terminal
from audit_progress_run_v7 import failures
from audit_sq_initial import ROOT, sha, verify_common


# Independent contract table: not imported from the controller or model.
EVENTS={"clean":"HH","head_af":"AH","tail_af":"HA","head_pf":"PH","tail_pf":"HP",
        "head_af_tail_pf":"AP","head_pf_tail_af":"PA","head_af_tail_nack":"AN","head_pf_tail_nack":"PN",
        "head_nack_tail_af":"NA","head_nack_tail_pf":"NP","head_nack_tail_miss":"NM","head_miss_tail_nack":"MN",
        "both_pf":"PP","both_miss":"MM","head_miss_tail_af":"MA","head_miss_tail_pf":"MP"}
MISS_CASES=((False,"head_miss_tail_af"),(True,"head_miss_tail_af"),(True,"head_miss_tail_pf"))
SCHEDULE=tuple((page,name) for page,patterns in((False,(*WORD_PATTERNS,"both_miss")),(True,(*PAGE_PATTERNS,"both_miss"))) for name in patterns)+MISS_CASES
FIELDS=("allocated_UIDs","normal_completed_UIDs","fault_WB_and_head_trap_UIDs","pure_cancelled_UIDs","structurally_cancelled_UIDs")


def expected_semantics(name,filler=False):
    h,t=EVENTS[name];fault=bool(set((h,t))&set("AP"));hr=h in"NM";tr=t in"NM"
    wb=h in"AP" or not hr and (t in"AP" or not tr)
    retry=bool((hr or tr) and not wb)
    retained=bool(fault and wb and (hr or tr))
    replacements=1+retained if fault else 0
    allocated=4+replacements+filler
    joins=1+retry+(replacements if fault else 1)
    counts=dict(source_S4_joins=joins,source_actual_query_pairs=2*joins,actual_original_Sbuffer_fires=1,actual_original_SQ_releases=1,
                actual_LQ_structure_releases=3+filler,precise_ROB_head_traps=int(fault),both_actual_recoveries_settled=int(fault),
                actual_replay_grants=int(retry),actual_original_slot_feedbacks=int(retry),fault_WB_attempts=int(fault),
                pending_Replay_owners_cancelled=int(retained),head_fault_beats_other_tail_fault=int(h in"AP" and t in"AP" and h!=t),
                fault_WB_despite_tail_replay=int(h in"AP" and tr),tail_fault_without_WB_waits_for_head_retry=int(hr and t in"AP"),
                declared_original_Cache_jobs=int(h=="M")+int(t=="M"),actual_original_Cache_refills=int(h=="M")+int(t=="M"),
                declared_external_prefetch_jobs=int(h=="M" and t!="M"),actual_background_Cache_refills=int(h=="M" and t!="M"),
                wrong_tail_refill_did_not_wake_head=int(h=="M"))
    return dict(zip(FIELDS,(allocated,allocated-2*int(fault),int(fault),int(fault),replacements))),counts


def check_program(detail,pattern,*,sq=0,lq=0,order=8,uid=0,filler=False,initial=False):
    terminal(detail)
    expected,counts=expected_semantics(pattern,filler)
    assert {f:detail[f] for f in FIELDS}==expected,(pattern,{f:detail[f] for f in FIELDS},expected)
    assert all(detail["counts"].get(k,0)==v for k,v in counts.items()),(pattern,detail["counts"],counts)
    states=detail["UID_terminal_states"];by={s["uid"]:s for s in states}
    assert set(by)==set(range(uid+1,uid+expected["allocated_UIDs"]+1))
    assert [(s["kind"],s["queue_absolute_position"],s["ROB_absolute"]) for s in states[:4]]==[
        ("store",sq,order),("load",lq,order+2),("load",lq+1,order+3),("load",lq+2,order+4)]
    replacements=expected["structurally_cancelled_UIDs"]
    for n,s in enumerate(states[4:4+replacements]):
        assert s["kind"]=="load" and s["queue_absolute_position"]==lq+3-replacements+n and s["ROB_absolute"]==order+5+n
    if filler:
        assert (states[-1]["kind"],states[-1]["queue_absolute_position"],states[-1]["ROB_absolute"])==("load",lq+3,order+10)
    assert detail["queue_tails"]==dict(SQ=sq+1,LQ=lq+3+filler)
    assert all(s["physical_slot"]==s["queue_absolute_position"]%(64 if s["kind"]=="store" else 120) for s in states)
    for w in detail["same_slot_completion_witnesses"]:
        assert by[w["cancelled_UID"]]["queue_absolute_position"]==by[w["new_completed_UID"]]["queue_absolute_position"]
    window=detail["request_window"];cycles=detail["counts"]["cycles"]
    assert window["all_requests_plus2"] and window["last_tick"]-window["first_tick"]==2*(cycles-1)
    prefix=detail["native_prefix_records"];end=detail["native_records_at_end"]
    assert end-prefix==cycles+int(initial)
    assert window["first_tick"]-detail["native_prefix_last_tick"]==2*(1+int(initial))
    assert window["last_tick"]-detail["native_prefix_last_tick"]==2*(end-prefix)
    assert prefix>=10 and (not initial or prefix==10)
    return Counter(detail["counts"]),Counter(expected)


def frozen_checker(run,source):
    frozen=run/"verification-source/tests/lsq_wrapper"
    tree=ast.parse((frozen/"s4_precise_check.py").read_text())
    assert not any(isinstance(n,ast.Import) for n in tree.body)
    assert all(n.module in("collections","dataclasses") for n in tree.body if isinstance(n,ast.ImportFrom))
    assert not any(isinstance(n,ast.Attribute) and n.attr in("model","last_change","expected_before","expected_after","dut","_instances") for n in ast.walk(tree))
    assert any(isinstance(n,ast.Assert) and "unobserved cycle" in ast.unparse(n) for n in ast.walk(tree))
    controller=ast.parse((frozen/"ldu_s4_precise_owners.py").read_text())
    cycle=next(n for n in ast.walk(controller) if isinstance(n,ast.AsyncFunctionDef) and n.name=="cycle")
    assert len(cycle.body)==3 and isinstance(cycle.body[1].value,ast.Await) and cycle.body[2].value.func.attr=="observe"
    shared=json.loads((ROOT/"results/lsq-progress-regression-12/source-evidence.json").read_text())["files"]
    assert all(source[k]==v for k,v in shared.items() if k.startswith("lsqverify/"))
    return len([k for k in shared if k.startswith("lsqverify/")])


def audit(name):
    assert name in("lsq-s4-precise-03","lsq-s4-precise-04")
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert len(nodes)==84
    references=frozen_checker(run,source)
    assert not list((run/"cases").rglob("*.jsonl")) and not list((run/"cases").rglob("*.fst")) and not list((run/"cases").rglob("*.vcd"))
    expected={(lane,page,pattern) for lane in range(3) for page,pattern in SCHEDULE}
    totals=Counter();semantic=Counter();seen=set();actual=set();rotations=set();case_reports=[];native_records=0;program_count=0
    for file in sorted((run/"cases").rglob("s4-precise*summary.json")):
        result=json.loads(file.read_text());node=result["nodeid"]
        assert node in nodes and node not in seen;seen.add(node)
        assert result["passed"]==bool(not nodes[node])
        native=json.loads(file.with_name("lsq_wrapper.summary.json").read_text())
        assert native["nodeid"]==node and not native["trace_enabled"] and not native["trace_truncated"] and not native["saved_trace_bytes"]
        native_records+=native["records"]
        if "case" in result:
            case=result["case"];key=(case["lane"],case["page"],case["pattern"])
            assert key in expected and key not in actual;actual.add(key)
            if result["passed"]:
                detail=result["independent_online_checks"]
                c,u=check_program(detail,case["pattern"],initial=True)
                totals.update(c);semantic.update(u);program_count+=1
                assert native["records"]==detail["native_records_at_end"] and native["terminal"]["post_tick"]==detail["request_window"]["last_tick"] and native["terminal"]["checked"]
        else:
            rotation=result["rotation"];assert rotation in range(3) and rotation not in rotations;rotations.add(rotation)
            programs=result["programs"] if result["passed"] else result["completed_programs"]
            assert len(programs)<=360
            sq=lq=uid=0;order=8;last_end=last_tick=None;targets=set();stores=set()
            for index,program in enumerate(programs):
                page,pattern=SCHEDULE[index%27]
                assert (program["index"],program["page"],program["pattern"],program["lane"])==(index,page,pattern,(index+rotation)%3)
                detail=program["summary"];filler=index in(119,239)
                c,u=check_program(detail,pattern,sq=sq,lq=lq,order=order,uid=uid,filler=filler,initial=index==0)
                totals.update(c);semantic.update(u);program_count+=1
                if last_end is not None:
                    assert detail["native_prefix_records"]==last_end and detail["native_prefix_last_tick"]==last_tick
                last_end=detail["native_records_at_end"];last_tick=detail["request_window"]["last_tick"]
                targets.add((lq+1)%240);stores.add(sq%256)
                sq,lq,order,uid=sq+1,lq+3+filler,order+10+filler,uid+detail["allocated_UIDs"]
            if result["passed"]:
                assert len(programs)==360 and targets==set(range(240)) and stores==set(range(256))
                assert (sq,lq,order,uid)==(result["SQ_tail"],result["LQ_tail"],result["ROB_absolute"],result["allocated_UIDs"])
                assert (sq,lq,order)==(360,1082,3610) and native["records"]==last_end and native["terminal"]["post_tick"]==last_tick and native["terminal"]["checked"]
        case_reports.append(dict(nodeid=node,result="FAIL" if nodes[node] else "PASS",summary=str(file.relative_to(run)),summary_SHA256=sha(file),
                                 summary_bytes=file.stat().st_size,native_records=native["records"],runtime_stream_SHA256=native["streamed_SHA256"],error=result.get("error")))
    assert seen==set(nodes) and actual==expected and rotations==set(range(3))
    if not any(nodes.values()):
        assert manifest["tests"]=={"PASS":84} and program_count==1161
        assert native_records==totals["cycles"]+11*84
    dest=run/"evidence-auditors";dest.mkdir(exist_ok=True)
    for file in(Path(__file__),ROOT/"tools/audit_lsq_s4_precise_summary_v1.py",ROOT/"tools/audit_lsq_s4_precise_summary_v2.py"):
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
    report=dict(status="ACTUAL_PRECISE_S4_WINDOW_UID_CACHE_CHECKS_NOT_WHOLE_GOAL_SIGNOFF" if not any(nodes.values()) else "PRECISE_S4_FAILURES_RETAINED_NO_SIGNOFF",
                run=name,tests=manifest["tests"],snapshot_files=len(source),preserved_reference_files=references,validated_completed_programs=program_count,
                native_records=native_records,program_request_counts=dict(totals),UID_terminal_counts=dict(semantic),failures=failures(run),
                per_cycle_JSON=0,waveforms=0,case_summary_bytes=sum(c["summary_bytes"] for c in case_reports),cases=case_reports,auditor_SHA256=sha(Path(__file__)),
                limits="Actual native/public I/O checks executed online. Compact terminal witnesses/windows and stream SHA do not permit offline replay of unretained per-cycle raw. External Cache/TLB/ROB/LDU choices are producer assumptions, not upstream native UT. Only completed programs enter terminal totals; stopped FAIL prefixes remain partial. Old FAILs/random/other128/local-only/full request audit are not waived.")
    output=run/"s4-precise-summary-audit-v3.json"
    if output.exists():assert json.loads(output.read_text())==report
    else:output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("name");audit(p.parse_args().name)
