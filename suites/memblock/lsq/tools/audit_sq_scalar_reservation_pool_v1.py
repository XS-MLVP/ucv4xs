#!/usr/bin/env python3
"""128scalar LSQ-interface capacity evidence; not normal full-core acceptance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_checkpoint_pool_v1 import validate_run
from audit_coverage_points_v1 import records,sha256_file,summarize
from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases,failure_digest
from audit_failure_preservation_v1 import pytest_status
from audit_gap_closure_v1 import audit as audit_delta,digest_keys,native,point_sets
from audit_native_case_probe_v1 import journal_streams,stable_run,xml_node
from audit_native_contributor_scope_v1 import contributors,same_summary
from audit_store_strict_lifetimes_v1 import source_lines
from audit_uq_page_pairs_v1 import functional_counts,node_summaries
from audit_vsq_cancel_capacity_v1 import FAIL_NODE,failure_witness
from audit_vsq_recovery_boundaries_v1 import ROOT,SOURCES
from audit_vsq_release_windows_v1 import FULL_PATHS,line_delta
from audit_vsq_retire_known_width_v1 import FULL as BEFORE_FULL,witness as known_witness

FULL="sq-scalar-reservation-contributor-regression-01"
DOMAIN="UNIT_INTERFACE_LSQ_CAPACITY"
PAIRS=(
    ("store_queue","sq-scalar-reservation-baseline-01","sq-scalar-reservation-after-01","SQ-INTERFACE.scalar_pool"),
    ("lsq_wrapper","lsq-scalar-reservation-baseline-01","lsq-scalar-reservation-after-01","LSQ-RECOVER.reuse"),
)


def load(path):
    return json.loads(path.read_text())


def target_points(dat,dut):
    points=[p for p in records(dat) if p["t"]=="toggle" and p["f"]==str(ROOT/SOURCES[dut])
            and p["o"] in ("cancelCount[7]:0->1","cancelCount[7]:1->0")]
    assert len(points)==2
    return [dict(source=SOURCES[dut],source_line=int(p["l"]),point=p["o"],hierarchy=p["h"],hit=p["hit"]) for p in sorted(points,key=lambda p:p["o"])]


def witness(run,dut):
    paths=[p for p in (ROOT/"results"/run/"cases").rglob("sq-scalar-reservation-witness.json") if load(p)["dut"]==dut]
    assert len(paths)==1
    path,item=paths[0],load(paths[0])
    assert item["format"]=="lsq-sq-scalar-reservation-witness-v1" and item["domain"]==DOMAIN
    assert not item["normal_full_core_producer_proven"] and len(item["public_lifetime_SHA256"])==64
    assert item["normal_store_uids"]==item["cancelled_store_uids"]==item["actual_Sbuffer_fragments"]==item["exact_absolute_position_reuses"]==256
    assert item["resets_between_profiles"]==0 and len(item["profiles"])==2
    old,new=set(),set()
    for phase,(part,base) in enumerate(zip(item["profiles"],(0,128))):
        assert part["phase"]==phase and part["physical_base"]==base
        assert part["reserved_scalar_uops"]==128 and part["flows_per_uop"]==1 and part["actual_recovered_tail"]==base%256
        assert part["max_dispatch_stores_per_cycle"]==2 and part["older_nonmemory_branch_flushAfter"]
        assert len(part["old_executed_uids"])==len(part["old_unexecuted_uids"])==64
        prior=part["old_executed_uids"]+part["old_unexecuted_uids"]
        pairs=part["reuse_old_new_absolute_position"]
        assert len(pairs)==128 and [row[0] for row in pairs]==prior
        assert [row[2] for row in pairs]==list(range(base,base+128))
        assert [row[1] for row in pairs]==part["new_completed_uids"] and min(row[1] for row in pairs)>max(prior)
        old.update(prior);new.update(part["new_completed_uids"])
        assert part["actual_Sbuffer_fragments"]==128 and part["old_consumed_fragments"]==0
        assert part["actual_physical_tail"]==base+128
        assert part["recovery"]["actual_sq_responses"]==[base%256] and part["recovery"]["sq_stall_cycles"]>0
        if dut=="lsq_wrapper":
            assert part["original_Load_PA_bytes_checked"] and part["new_Load_S3_completed"]
            assert part["cancelled_Load_uids"]==part["normal_Load_uids"]==1
            assert part["recovery"]["actual_lq_responses"]==[phase]
    assert len(old)==len(new)==256 and old.isdisjoint(new)
    if dut=="lsq_wrapper":assert item["normal_Load_uids"]==item["cancelled_Load_uids"]==2
    return dict(path=str(path.relative_to(ROOT)),SHA256=sha256_file(path),witness=item)


def calibration():
    first,second="sq-scalar-reservation-probe-01","sq-scalar-reservation-probe-02"
    a,b=pytest_status(first),pytest_status(second)
    assert a["manifest_tests"]=={"FAIL":2} and a["pytest_exitstatus"]==1
    assert b["manifest_tests"]=={"PASS":2} and b["pytest_exitstatus"]==0
    assert set(cases(first))==set(cases(second))
    assert all("io_sqFull" in value["detail"] for value in cases(first).values())
    return dict(first_probe=a,corrected_probe=b,first_probe_failure_SHA256=failure_digest(cases(first)),
        explanation="Wrong new-test precondition treated public PSQ overflow full as removed VSQ full. Pinned source says >128, so exact128 is0. Only this expected pin value was corrected; original two FAIL/JUnit/dat remain. No comparison or original failure is disabled. No raw trace/input-prefix replay is claimed.")


def audit_pair(dut,before,after,scenario):
    a,b=validate_run(before,dut),validate_run(after,dut)
    assert a["source"]==b["source"]
    old,new=cases(before),cases(after)
    assert len(new)==len(old)+1 and set(old)<set(new) and all(new[node]==value for node,value in old.items())
    assert FAIL_NODE not in new
    added=next(iter(set(new)-set(old)))
    closure=audit_delta(before,after,dut,dut.upper()+"-SCALAR-RESERVATION-INTERFACE",added)
    assert all(closure["verification"].values())
    filename="store_queue.summary.json" if dut=="store_queue" else "lsq_wrapper.summary.json"
    x,y=node_summaries(before,filename),node_summaries(after,filename)
    assert all(y[node]==value for node,value in x.items())
    targets=dict(before=target_points(a["dat"],dut),after=target_points(b["dat"],dut))
    assert all(point["hit"]>0 for point in targets["after"])
    functions={name:functional_counts(name,dut,scenario) for name in (before,after)}
    assert functions[after]["checked"]["count"]>functions[before]["checked"]["count"]
    domain=load(ROOT/"results"/BEFORE_FULL/"sq-scalar-reservation-domain-v1.json")
    assert domain["domain"]==DOMAIN and not domain["normal_full_core_producer_proven"] and all(domain["verification"].values())
    report=dict(format="lsq-sq-scalar-reservation-evidence-v1",dut=dut,before_run=before,after_run=after,
        contract="docs/contracts/sq-scalar-reservation-pool.md",domain=DOMAIN,normal_full_core_producer_proven=False,
        source_domain_evidence=f"results/{BEFORE_FULL}/sq-scalar-reservation-domain-v1.json",
        baseline_tests=len(old),after_tests=len(new),added_nodes=[added],source_aggregate=a["source"]["aggregate_SHA256"],
        native_build_id=closure["native_build_id"],raw_nonwrapper_metrics=closure["metrics"],cancel_count_targets=targets,
        original_source_line_coverage=line_delta(source_lines(a["meta"],a["dat"],dut),source_lines(b["meta"],b["dat"],dut)),
        public_lifetime=witness(after,dut),functional=functions,calibration=calibration(),
        verification=dict(real_parent_native_DUT_and_full_reference=True,same_source_build_and_three_point_universes=True,
            original_nodes_and_primary_streams_equal=True,no_old_native_hit_lost=True,actual_target_directions_hit=True,
            LSQ_interface_reservation_vs64_issue_separate=True,every_cancelled_absolute_position_has_new_completed_UID=True,
            older_nonmemory_branch_not_head_store_self_flush=True,full_core_IQ_reachability_not_claimed=True),
        limits="Module-capacity interface evidence only. The64unexecuted STA are not declared resident in the configured32-entry IQ. No complete normal upstream resource history or global unreachability is proven. Original172failures and unified inventories remain.")
    write_report(ROOT/"results"/after/"sq-scalar-reservation-evidence-v1.json",report)
    return report


def audit_full():
    status,source=stable_run(FULL);old_status,_=stable_run(BEFORE_FULL)
    assert old_status["manifest_tests"]=={"PASS":1008,"FAIL":172}
    assert status["manifest_tests"]=={"PASS":1010,"FAIL":172} and status["total_cases"]==1182 and status["pytest_exitstatus"]==1
    old,new=cases(BEFORE_FULL),cases(FULL)
    assert len(old)==1180 and len(new)==1182 and all(new[node]==value for node,value in old.items())
    added=set(new)-set(old)
    assert added==set().union(*(set(cases(after))-set(cases(before)) for _,before,after,_ in PAIRS))
    assert len(added)==2 and all(new[node]["outcome"]=="PASS" for node in added)
    assert failure_digest(old)==failure_digest(new) and old[FAIL_NODE]==new[FAIL_NODE] and new[FAIL_NODE]["outcome"]=="FAIL"
    command=load(ROOT/"results"/FULL/"command.json")["command"]
    assert command[command.index("--lsq-trace-max-mb")+2:]==FULL_PATHS+["--tb=short"]
    manifest=load(ROOT/"results"/FULL/"execution/manifest.json")
    assert len([a for a in manifest["artifacts"] if a["kind"]=="native"])==6
    a,b=contributors(BEFORE_FULL),contributors(FULL)
    assert {dut:len(items) for dut,items in b.items()}==dict(forward_module=186,physical_store_queue=70,store_queue=90,lsq_wrapper=744)
    for dut,items in a.items():assert all(same_summary(value,b[dut][node]) for node,value in items.items())
    nodes=set().union(*(set(items) for items in b.values()))
    for dut,filename,count in (("virtual_store_queue","virtual_store_queue.summary.json",50),("unalign_queue","unalign_queue.summary.json",42)):
        x,y=node_summaries(BEFORE_FULL,filename),node_summaries(FULL,filename)
        assert len(x)==len(y)==count and x==y
        meta,_=native(FULL,dut);assert meta["artifact"]["input_files"]==count
        nodes|={xml_node(node) for node in y}
    assert nodes==set(new)
    a,b=journal_streams(BEFORE_FULL),journal_streams(FULL)
    assert len(a)==2229 and len(b)==2232 and all(b[key]==value for key,value in a.items())
    rows=[]
    for dut in ("forward_module","physical_store_queue","store_queue","lsq_wrapper","unalign_queue","virtual_store_queue"):
        ma,da=native(BEFORE_FULL,dut);mb,db=native(FULL,dut)
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
        row=dict(dut=dut,old_run=BEFORE_FULL,native_build_id=mb["artifact"]["build"]["build_id"],metrics=metrics,
            original_native_inputs=ma["artifact"]["input_files"],current_native_inputs=mb["artifact"]["input_files"],
            original_source_line_coverage=line_delta(source_lines(ma,da,dut),source_lines(mb,db,dut)))
        if dut in ("store_queue","lsq_wrapper"):
            after=next(after for key,_,after,_ in PAIRS if key==dut)
            actual,selected=witness(FULL,dut),witness(after,dut)
            assert actual["witness"]==selected["witness"]
            row["public_witness_SHA256"]=actual["SHA256"]
            row["cancel_count_targets"]=dict(before=target_points(da,dut),after=target_points(db,dut))
            assert all(point["hit"]>0 for point in row["cancel_count_targets"]["after"])
            row["new_coverage_domain"]=DOMAIN
            row["normal_full_core_producer_proven"]=False
        else:
            assert sha256_file(da)==sha256_file(db)
            row["unchanged_native_dat_SHA256"]=sha256_file(db)
        if dut in SOURCES:assert known_witness(FULL,dut)["witness"]==known_witness(BEFORE_FULL,dut)["witness"]
        rows.append(row)
    prior=load(ROOT/"results"/BEFORE_FULL/"vsq-retire-known-width-contributor-evidence-v1.json")
    actor_hashes=prior["unchanged_generic_actor_SHA256"]
    assert all(sha256_file(ROOT/path)==digest for path,digest in actor_hashes.items())
    assert failure_witness(FULL)["observed_old_owners"]==failure_witness(BEFORE_FULL)["observed_old_owners"]
    report=dict(format="lsq-sq-scalar-reservation-contributor-v1",run=FULL,status=status,source_aggregate=source["aggregate_SHA256"],
        original_nodes=1180,current_nodes=1182,added_nodes=sorted(added),added_passing_nodes=2,original_failures=172,
        original_failure_SHA256=failure_digest(old),current_failure_SHA256=failure_digest(new),rows=rows,
        domain=DOMAIN,normal_full_core_producer_proven=False,unchanged_generic_actor_SHA256=actor_hashes,
        original_wrapper_public_check_actor_summaries_equal=2229,head_permit_failure=failure_witness(FULL),
        required_new_functional_failures=prior["required_new_functional_failures"],calibration=calibration(),
        coverage_monotonicity=dict(name="all_old_native_hits_retained",passed=True,status="PASS",failed_duts=[],newly_missing_toggle_points=0,required=True,waived=False),
        verification=dict(actual_fresh_complete_six_build_execution=True,old1180_results_and172_failure_details_equal=True,
            all_original_contributors_and_public_streams_equal=True,both_new_witnesses_equal_directed=True,
            known_retire_witnesses_preserved=True,required_head_permit_failure_and_old_bytes_preserved=True,
            same_builds_and_three_point_universes=True,no_old_native_hit_lost=True,
            locked_analyzer_and_fixed_build_hashes_checked=True,original_generic_actor_hashes_unchanged=True,
            module_interface_scope_not_promoted_to_full_core=True,source_launch_end_aggregates_equal=True,no_cycle_JSON_or_waveforms=True),
        limits="Actual LSQ module-interface128scalar coverage only. Complete backend32-entry-IQ resource history remains unproven. No normal full-core/global unreachable waiver, original172failure suppression, unified regression15 update, or all-LSQ acceptance.")
    write_report(ROOT/"results"/FULL/"sq-scalar-reservation-contributor-evidence-v1.json",report)
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--full",action="store_true");args=parser.parse_args()
    for pair in PAIRS:
        r=audit_pair(*pair)
        print(json.dumps({k:r[k] for k in ("dut","domain","baseline_tests","after_tests","raw_nonwrapper_metrics","verification")},indent=2))
    if args.full:print(json.dumps(audit_full(),indent=2))
