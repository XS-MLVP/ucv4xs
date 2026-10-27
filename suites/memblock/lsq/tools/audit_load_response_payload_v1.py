#!/usr/bin/env python3
"""Load response data closure with source-correct S3 and all prior FAILs kept."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re

from audit_checkpoint_pool_v1 import validate_run
from audit_coverage_points_v1 import records,sha256_file,summarize
from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases,failure_digest
from audit_gap_closure_v1 import audit as audit_delta,digest_keys,native,point_sets
from audit_native_case_probe_v1 import journal_streams,stable_run,xml_node
from audit_native_contributor_scope_v1 import contributors,same_summary
from audit_sq_head_permit_domain_v1 import source,evidence
from audit_store_strict_lifetimes_v1 import source_lines
from audit_uq_page_pairs_v1 import functional_counts,node_summaries
from audit_vsq_cancel_capacity_v1 import failure_witness
from audit_vsq_recovery_boundaries_v1 import ROOT
from audit_vsq_release_windows_v1 import FULL_PATHS as STORE_PATHS,line_delta
from audit_sq_scalar_reservation_pool_v1 import FULL as STORE_FULL

BASELINE="load-response-contributor-baseline-01"
FULL="load-response-contributor-regression-02"
INTERRUPTED="load-response-contributor-regression-01"
FULL_PATHS=STORE_PATHS+["tests/load_uncache","tests/load_queue"]
NEW_FILES=["tests/load_uncache/test_response_payload_pool.py","tests/load_queue/test_response_payload_pool.py","tests/lsq_wrapper/test_response_payload_pool.py"]
PAIRS=(
    ("load_queue_uncache","lqu-response-payload-baseline-01","lqu-response-payload-after-01","LQU-BYPASS.payload_pool"),
    ("load_queue","lq-response-payload-baseline-01","lq-response-payload-after-01","LQ-UNCACHE.payload_pool"),
    ("lsq_wrapper","lsq-response-payload-baseline-01","lsq-response-payload-after-01","LSQ-EXCEPTION.load_fault"),
)
PROFILES=((0,False,False),((1<<64)-1,True,False),(0,False,True),((1<<64)-1,True,True))
SIGNALS=("uncacheData","io_ncOut_bits_data","io_mmioRawData_lqData")


def load(path):return json.loads(path.read_text())


def producer_source():
    ranges=[]
    for path,start,end,checks in (
        ("mem/pipeline/NewLoadUnit.scala",927,951,["val isUncache = isNC || isMMIO","exceptionVec(hardwareError) := hwe"]),
        ("mem/pipeline/NewLoadUnit.scala",1059,1061,["val alwaysWriteback = exception || isMMIOReplay"]),
        ("mem/pipeline/NewLoadUnit.scala",1094,1097,["isNCReplay","nukeQueryReq.nc := isNCReplay"]),
        ("mem/pipeline/NewLoadUnit.scala",1111,1115,["isNCReplay && (sqDataInvalid || rarNack || rawNack || nuke || forwardInvalid)"]),
        ("mem/pipeline/NewLoadUnit.scala",1145,1146,["val shouldWakeup = !shouldReplay && !isUncache && !exception","val shouldWriteback = shouldWakeup || exception || matchInvalid"]),
        ("mem/pipeline/NewLoadUnit.scala",1571,1582,["lqWrite.uop.exceptionVec extendFrom exceptionVec","lqWrite.nc := in.nc.get || in.isNCReplay()"]),
        ("mem/pipeline/NewLoadUnit.scala",1596,1615,["lqWrite.alignedType := in.size","lqWrite.updateAddrValid := ldoutValid || vldoutValid","lqWrite.rep_info.last_beat := paddr(log2Up(refillBytes))"]),
        ("mem/lsqueue/LoadQueueUncache.scala",194,196,["uncacheData := io.uncache.resp.bits.data","nderr := io.uncache.resp.bits.nderr","derr := io.uncache.resp.bits.error"]),
        ("mem/lsqueue/LoadQueueUncache.scala",211,239,["exceptionVec(loadAccessFault) := nderr","exceptionVec(hardwareError) := derr","io.mmioRawData.lqData := uncacheData"]),
        ("mem/lsqueue/LoadQueueUncache.scala",352,357,["!s2_has_exception(w)","(s2_req(w).mmio || s2_req(w).nc)"]),
        ("mem/lsqueue/LoadQueueUncache.scala",534,542,["io.bypass(w).s2Resp.bits.nderr := RegEnable(s1RespNderr, s1RespValid)","io.bypass(w).s2Resp.bits.derr := RegEnable(s1RespDerr, s1RespValid)"]),
    ):
        ranges.append(evidence(*source(path),start,end,checks))
    return dict(source_ranges=ranges,first_uncache_update_address=False,NC_replay_queries_RAR_RAW=True,
        MMIO_replay_no_RAR_RAW=True,response_error_exception_bit=19,response_nderr_exception_bit=5,
        fault_local_writeback_not_architectural_commit=True,external_head_exception_redirect=True,
        limits="Exact fixed-source ranges for the aligned single-owner response contract. Not a full NewLoadUnit DUT/S4, backend trap, or whole-CPU reachability proof.")


def target_summary(dat,dut):
    points=[p for p in records(dat) if p["t"]=="toggle" and re.fullmatch(r"UncacheEntry(?:_\d+)?\.sv",Path(p["f"]).name)
            and p["o"].split("[")[0] in SIGNALS]
    assert len(points)==6144
    result=[]
    for i in range(16):
        filename="UncacheEntry"+(f"_{i}" if i else "")+".sv"
        for signal in SIGNALS:
            selected=[p for p in points if Path(p["f"]).name==filename and p["o"].startswith(signal+"[")]
            assert len(selected)==128
            assert {p["o"] for p in selected}=={f"{signal}[{b}]:{d}" for b in range(64) for d in ("0->1","1->0")}
            result.append(dict(entry_id=i,source=str(Path(selected[0]["f"]).relative_to(ROOT)),signal=signal,
                source_lines=sorted({int(p["l"]) for p in selected}),hierarchies=sorted({p["h"] for p in selected}),
                hit=sum(p["hit"]>0 for p in selected),total=128,
                missing_SHA256=digest_keys({tuple(p.get(k,"") for k in ("f","l","n","t","o","S","h")) for p in selected if not p["hit"]})))
    return dict(total=6144,hit=sum(p["hit"]>0 for p in points),by_entry_signal=result)


def witness(run,dut):
    paths=[p for p in (ROOT/"results"/run/"cases").rglob("load-response-payload-witness.json") if load(p)["dut"]==dut]
    assert len(paths)==1
    path,item=paths[0],load(paths[0])
    assert item["format"]=="lsq-load-response-payload-witness-v1" and len(item["rows"])==128
    assert item["local_UID_completions"]==item["requests"]==item["acks"]==item["responses"]==128
    assert item["clean_UID_completions"]==32 and item["fault_local_completions"]==item["external_fault_redirects"]==96
    assert item["resets_between_profiles"]==0 and not item["Backend_trap_implementation_claimed"]
    assert len(item["checked_public_stream_SHA256"])==64
    seen=Counter()
    for index,row in enumerate(item["rows"]):
        data,error,nderr=PROFILES[row["generation"]]
        assert row["uid"]==index+1 and row["position"]==index and row["nc"]==(index<64)
        assert row["generation"]==index//16%4 and row["data"]==data and row["error"]==error and row["nderr"]==nderr
        assert row["lane"]==index%3 and row["sid"]==index%16 and row["mid"] in range(16)
        seen[(row["nc"],row["generation"],row["mid"])]+=1
        assert all(row[k] for k in ("actual_s1_PA_checked","actual_s2_data_checked","actual_exception_metadata_checked","local_completion"))
        assert row["external_fault_redirect"]==bool(error or nderr) and row["architectural_retirement_claimed"]==(not bool(error or nderr))
        if dut!="load_queue_uncache":
            assert row["replay_slot"] in range(120) and row["actual_LQ_head"]==index+1
            assert not row["S3_update_first"] and row["S3_update_final"] and row["S3_exceptions"]==(int(error)<<19|int(nderr)<<5)
            first,final=row["actual_driven_first_S3"],row["actual_driven_final_S3"]
            assert not first["update_address"] and first["need_replay"] and first["causes"]==1 and not first["replay_feedback"]
            assert first["uop_exceptions"]==first["load_exceptions"]==0
            assert final["update_address"] and not final["need_replay"] and final["causes"]==0 and final["replay_feedback"]
            assert final["uop_exceptions"]==final["load_exceptions"]==row["S3_exceptions"] and final["slot"]==row["replay_slot"]
            assert first["aligned_type"]==final["aligned_type"]==3 and final["tick"]>first["tick"]
            assert first["last_beat"]==final["last_beat"]==bool((0x80000000+index*64)&64)
            prefix=f"io_bypass_{index%3}_"
            s1,s2=row["observed_s1"],row["observed_s2"]
            assert s1[prefix+"s1Resp_valid"]==1 and s1[prefix+"s1Resp_bits_paddr"]==0x80000000+index*64
            assert s2=={prefix+"s2Resp_valid":1,prefix+"s2Resp_bits_data":data*((1<<64)+1),prefix+"s2Resp_bits_derr":int(error),prefix+"s2Resp_bits_nderr":int(nderr)}
    assert len(seen)==128 and set(seen.values())=={1}
    if dut!="load_queue_uncache":assert item["actual_Replay_grants"]==item["actual_slot_feedbacks"]==128
    else:assert not item["VLQ_Replay_S3_claimed"]
    return dict(path=str(path.relative_to(ROOT)),SHA256=sha256_file(path),witness=item)


def audit_pair(dut,before,after,scenario):
    a,b=validate_run(before,dut),validate_run(after,dut)
    assert a["source"]==b["source"]
    x,y=cases(before),cases(after)
    assert len(y)==len(x)+1 and set(x)<set(y) and all(y[node]==value for node,value in x.items())
    added=next(iter(set(y)-set(x)))
    closure=audit_delta(before,after,dut,dut.upper()+"-LOAD-RESPONSE-PAYLOAD",added)
    assert all(closure["verification"].values())
    filename=dut+".summary.json"
    old,new=node_summaries(before,filename),node_summaries(after,filename)
    assert all(new[node]==value for node,value in old.items())
    targets=dict(before=target_summary(a["dat"],dut),after=target_summary(b["dat"],dut))
    assert targets["after"]["hit"]==6144
    functions={name:functional_counts(name,dut,scenario) for name in (before,after)}
    assert functions[after]["checked"]["count"]>functions[before]["checked"]["count"]
    report=dict(format="lsq-load-response-payload-evidence-v1",dut=dut,before_run=before,after_run=after,
        contract="docs/contracts/load-response-payload-pool.md",producer_source=producer_source(),
        baseline_tests=len(x),after_tests=len(y),added_nodes=[added],source_aggregate=a["source"]["aggregate_SHA256"],native_build_id=closure["native_build_id"],
        raw_nonwrapper_metrics=closure["metrics"],response_data_targets=targets,public_lifetime=witness(after,dut),functional=functions,
        original_source_line_coverage=line_delta(source_lines(a["meta"],a["dat"],dut),source_lines(b["meta"],b["dat"],dut)),
        verification=dict(actual_native_parent_and_full_reference=True,same_source_build_and_three_point_universes=True,
            old_results_and_primary_streams_equal=True,no_old_native_hit_lost=True,all16_entry_data_directions_hit=True,
            both_types_all_four_error_combinations=True,original128_response_and_consumption_UIDs_checked=True,
            source_correct_parent_S3_and_actual_prefix_completion=True,fault_completion_not_architectural_retirement=True),
        limits="Serialized positive response control only. Old SID-returned-before-consumption failures, mixed traffic, S4/cross-page, disabled feedback, backend trap and other full-goal domains are not waived or replaced.")
    write_report(ROOT/"results"/after/"load-response-payload-evidence-v1.json",report)
    return report


def expected_nodes():
    original=cases(STORE_FULL)
    unified=cases("lsq-progress-regression-15")
    extra={node:value for node,value in unified.items() if node.startswith(("tests.load_uncache.","tests.load_queue."))}
    assert len(original)==1182 and len(extra)==271 and not original.keys()&extra.keys()
    original.update(extra)
    # The checkpoint supplement was added after regression15 and is part of
    # the full current load_queue directory, never silently omit its node.
    checkpoint=cases("lq-checkpoint-pool-after-01")
    for node,value in checkpoint.items():
        if node.startswith("tests.load_queue.") and node not in original:original[node]=value
    return original


LQU_RELOCATED_NODES=(
    "tests.load_uncache.test_initial_probes::test_sid_reused_after_response_preserves_old_unconsumed_data",
    *(f"tests.load_uncache.test_sid_boundaries::test_old_data_held_while_new_same_sid_response_arrives[{i}]" for i in (0,3,15)),
    *(f"tests.load_uncache.test_sid_boundaries::test_old_error_held_while_new_same_sid_error_arrives[{i}]" for i in (0,3,15)),
    "tests.load_uncache.test_timing_boundaries::test_multiple_mmio_selectors_interface_priority_not_rob_legality_claim",
)


def relocated_failure_source_evidence():
    previous=ROOT/"results/entry-toggle-gap-after-01/verification-source/lsqverify/load_uncache/probe.py"
    current=ROOT/"lsqverify/load_uncache/probe.py"
    assert sha256_file(previous)=="e0caec07f0513b45210caa4a24ec84541cd26c369df0f20a89c8446195785f17"
    assert sha256_file(current)=="117820cc947b82e5fc39b74278db4ea6677f688b012c5a0f8ecac7eb94cfe77f"
    left,right=previous.read_text(),current.read_text()
    changes=[row for row in difflib.SequenceMatcher(a=left.splitlines(),b=right.splitlines()).get_opcodes() if row[0]!="equal"]
    assert changes==[("insert",12,12,12,13)]
    old,new=ast.parse(left),ast.parse(right)
    scenarios=next(node for node in new.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="SCENARIOS" for t in node.targets))
    assert isinstance(scenarios.value,ast.Dict) and scenarios.value.keys[0].value=="LQU-BYPASS.payload_pool"
    scenarios.value.keys.pop(0);scenarios.value.values.pop(0)
    assert ast.dump(old,include_attributes=False)==ast.dump(new,include_attributes=False)
    return dict(previous_source=str(previous.relative_to(ROOT)),previous_SHA256=sha256_file(previous),
        current_source=str(current.relative_to(ROOT)),current_SHA256=sha256_file(current),
        sole_diff=[list(row) for row in changes],all_preexisting_ASTs_equal=True,exact_nodes=list(LQU_RELOCATED_NODES),
        exact_frame_relocations={"255":256,"266":267},raw_JUnit_or_failure_text_rewritten=False)


def compare_preexisting_nodes(expected,current):
    assert set(expected)<=set(current)
    changed={node for node,value in expected.items() if current[node]!=value}
    assert changed==set(LQU_RELOCATED_NODES)
    normalized_left,normalized_right=dict(expected),{node:current[node] for node in expected}
    for node in LQU_RELOCATED_NODES:
        assert expected[node]["outcome"]==current[node]["outcome"]=="FAIL"
        # Do not normalize arbitrary line numbers, assertions or payloads.
        frame=re.compile(r"(?m)^lsqverify/load_uncache/probe\.py:(255|266): in consume$")
        assert len(frame.findall(expected[node]["detail"]))==1
        relocated=frame.sub(lambda m:f"lsqverify/load_uncache/probe.py:{int(m[1])+1}: in consume",expected[node]["detail"])
        assert current[node]["detail"]==relocated
        normalized_right[node]=dict(current[node],detail=expected[node]["detail"])
    assert normalized_left==normalized_right
    return dict(source=relocated_failure_source_evidence(),all_other_results_and_failure_bytes_equal=True,
        exact_changed_nodes=sorted(changed),normalized_original_failure_SHA256=failure_digest(normalized_left),
        normalized_current_failure_SHA256=failure_digest(normalized_right))


def audit_full():
    status,source_set=stable_run(FULL);before_status,before_source=stable_run(BASELINE)
    assert source_set==before_source
    old,new=cases(BASELINE),cases(FULL);expected=expected_nodes()
    assert set(old)==set(expected)
    source_relocation=compare_preexisting_nodes(expected,old)
    added=set(new)-set(old)
    assert len(added)==3 and added==set().union(*(set(cases(after))-set(cases(before)) for _,before,after,_ in PAIRS))
    assert len(new)==len(old)+3 and all(new[node]==value for node,value in old.items())
    assert all(new[node]["outcome"]=="PASS" for node in added)
    assert failure_digest(old)==failure_digest(new)
    assert before_status["manifest_tests"]["FAIL"]==status["manifest_tests"]["FAIL"]==192
    assert before_status["pytest_exitstatus"]==status["pytest_exitstatus"]==1
    interrupted=ROOT/"results"/INTERRUPTED
    interruption=load(interrupted/"interruption-audit-v1.json")
    assert load(interrupted/"execution/manifest.json")["state"]=="running"
    assert not (interrupted/"pytest.xml").exists()
    assert interruption["state_observed"]=="INTERRUPTED_NOT_COMMITTED" and interruption["missing_worker_receipts"]==["gw2","gw7"]
    for name,extra in ((BASELINE,[f"--ignore={p}" for p in NEW_FILES]),(FULL,[])):
        command=load(ROOT/"results"/name/"command.json")["command"]
        assert command[command.index("--lsq-trace-max-mb")+2:]==FULL_PATHS+extra+["--tb=short"]
        manifest=load(ROOT/"results"/name/"execution/manifest.json")
        assert len([a for a in manifest["artifacts"] if a["kind"]=="native"])==8
    a,b=contributors(BASELINE),contributors(FULL)
    for dut,items in a.items():assert all(same_summary(value,b[dut][node]) for node,value in items.items())
    assert {dut:len(items) for dut,items in a.items()}==dict(forward_module=186,physical_store_queue=70,store_queue=90,lsq_wrapper=744)
    assert len(b["lsq_wrapper"])==745
    nodes=set().union(*(set(items) for items in b.values()))
    for dut in ("load_queue_uncache","load_queue","virtual_store_queue","unalign_queue"):
        old_stream,new_stream=node_summaries(BASELINE,dut+".summary.json"),node_summaries(FULL,dut+".summary.json")
        assert all(new_stream[node]==value for node,value in old_stream.items())
        assert len(new_stream)==len(old_stream)+int(dut in ("load_queue_uncache","load_queue"))
        m,_=native(FULL,dut);assert m["artifact"]["input_files"]==len(new_stream)
        nodes|={xml_node(node) for node in new_stream}
    assert nodes==set(new)
    a,b=journal_streams(BASELINE),journal_streams(FULL)
    assert len(a)==2232 and len(b)==2235 and all(b[key]==value for key,value in a.items())
    original_store=cases(STORE_FULL)
    assert all(old[node]==value for node,value in original_store.items())
    rows=[]
    for dut in ("forward_module","physical_store_queue","store_queue","lsq_wrapper","unalign_queue","virtual_store_queue","load_queue_uncache","load_queue"):
        ma,da=native(BASELINE,dut);mb,db=native(FULL,dut)
        assert ma["artifact"]["build"]==mb["artifact"]["build"]
        for filename,digest in mb["artifact"]["build"]["files"].items():assert sha256_file(Path(filename))==digest
        parsed=summarize(db,mb["artifact"]["build"],mb["artifact"])
        assert parsed["raw_parser_matches_analyzer"] and parsed["coverage_artifact_matches_dat"]
        a,b=point_sets(da),point_sets(db);metrics={}
        for kind in a:
            assert a[kind]["all"]==b[kind]["all"] and a[kind]["hit"]<=b[kind]["hit"]
            gain=b[kind]["hit"]-a[kind]["hit"]
            metrics[kind]=dict(before_hit=len(a[kind]["hit"]),after_hit=len(b[kind]["hit"]),total=len(b[kind]["all"]),
                newly_hit=len(gain),newly_hit_SHA256=digest_keys(gain),newly_missing=0,still_missing=len(b[kind]["missing"]))
        row=dict(dut=dut,old_run=BASELINE,native_build_id=mb["artifact"]["build"]["build_id"],metrics=metrics,
            before_coverage_dat_SHA256=sha256_file(da),after_coverage_dat_SHA256=sha256_file(db),
            original_native_inputs=ma["artifact"]["input_files"],current_native_inputs=mb["artifact"]["input_files"],
            original_source_line_coverage=line_delta(source_lines(ma,da,dut),source_lines(mb,db,dut)))
        if dut in {p[0] for p in PAIRS}:
            directed=next(p[2] for p in PAIRS if p[0]==dut)
            assert witness(FULL,dut)["witness"]==witness(directed,dut)["witness"]
            row["public_witness_SHA256"]=witness(FULL,dut)["SHA256"]
            row["response_data_targets"]=dict(before=target_summary(da,dut),after=target_summary(db,dut))
            assert row["response_data_targets"]["after"]["hit"]==6144
        else:
            assert sha256_file(da)==sha256_file(db)
            row["unchanged_native_dat_SHA256"]=sha256_file(db)
        rows.append(row)
    prior=load(ROOT/"results"/STORE_FULL/"sq-scalar-reservation-contributor-evidence-v1.json")
    actor_hashes=prior["unchanged_generic_actor_SHA256"]
    assert all(sha256_file(ROOT/path)==digest for path,digest in actor_hashes.items())
    assert failure_witness(FULL)["observed_old_owners"]==failure_witness(STORE_FULL)["observed_old_owners"]
    report=dict(format="lsq-load-response-payload-contributor-v1",run=FULL,baseline_run=BASELINE,status=status,baseline_status=before_status,
        source_aggregate=source_set["aggregate_SHA256"],original_nodes=len(old),current_nodes=len(new),added_nodes=sorted(added),
        added_passing_nodes=3,original_failures=192,original_failure_SHA256=failure_digest(old),current_failure_SHA256=failure_digest(new),
        expected_node_source_relocation=source_relocation,
        interrupted_run_preserved=dict(run=INTERRUPTED,evidence=str((interrupted/"interruption-audit-v1.json").relative_to(ROOT)),
            evidence_SHA256=sha256_file(interrupted/"interruption-audit-v1.json"),promoted_or_merged=False),
        prior_six_build_nodes=1182,additional_load_contributor_nodes=len(old)-1182,
        original_wrapper_public_check_actor_summaries_equal=2232,rows=rows,unchanged_generic_actor_SHA256=actor_hashes,
        required_new_functional_failures=prior["required_new_functional_failures"],
        prior_domain_limited_evidence=f"results/{STORE_FULL}/sq-scalar-reservation-contributor-evidence-v1.json",
        head_permit_failure=failure_witness(FULL),producer_source=producer_source(),
        coverage_monotonicity=dict(name="all_old_native_hits_retained",passed=True,status="PASS",failed_duts=[],newly_missing_toggle_points=0,required=True,waived=False),
        verification=dict(actual_fresh_complete_eight_build_baseline_and_after=True,all_original1182_and_load_directory_results_preserved=True,
            all192_failure_details_equal=True,all_original_contributors_and_public_streams_equal=True,
            all_three_witnesses_equal_directed=True,same_source_builds_and_three_point_universes=True,no_old_native_hit_lost=True,
            original_required_head_permit_failure_kept=True,original_SID_failures_not_replaced=True,
            locked_analyzer_and_fixed_build_hashes_checked=True,original_generic_actor_hashes_unchanged=True,
            source_correct_S3_and_fault_retirement_limits_explicit=True,no_cycle_JSON_or_waveforms=True),
        limits="Eight-build actual execution expands contributors but does not close the whole38-DUT target.192FAILs remain required; response-data directed gains are not unified-regression15 numerator updates. Mixed/SID/S4/cross-page/disabled-feedback and prior domain limits remain open.")
    write_report(ROOT/"results"/FULL/"load-response-payload-contributor-evidence-v1.json",report)
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--full",action="store_true");args=parser.parse_args()
    for pair in PAIRS:
        row=audit_pair(*pair)
        print(json.dumps({k:row[k] for k in ("dut","baseline_tests","after_tests","raw_nonwrapper_metrics","verification")},indent=2))
    if args.full:print(json.dumps(audit_full(),indent=2))
