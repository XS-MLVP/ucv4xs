#!/usr/bin/env python3
"""253-case v2 delivery gate; reject/reproduce the three invalid prelude cases.

The v1 independent UID/protocol core is unchanged. v2 adds explicit evidence
that old12's green prelude dispatch behind ROB head is rejected, then checks
the actual legal producer correction rather than weakening retirement rules.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_recovery_history_v1 import inspect
from audit_lsq_population_v1 import RAW, events, paths_by_node, same_raw
from audit_lsq_bus_v2 import rob
from audit_sq_initial import ROOT,sha,verify_common


def has_prelude(node):
    return "test_both_real_branches_full_query_replay_pools_" in node and any(node.endswith(f"[{k}]") for k in (1,2,3))


def original_failure_prefixes(paths):
    reports=[]
    for name,expected in (("lsq-uncache-recovery-01",5),("lsq-shared-recovery-01",4),("lsq-pending-reset-01",2)):
        directory=ROOT/"results"/name
        _,_,nodes=verify_common(directory)
        old=paths_by_node(directory)
        failed=0
        for node,was_failed in nodes.items():
            if has_prelude(node):
                assert not was_failed
                continue  # separately rejected as illegal, NOT same_raw waived
            if not was_failed:
                same_raw(old[node],paths[node])
                continue
            earlier=list(events(old[node]))
            later=events(paths[node])
            for before in earlier:
                after=next(later)
                assert all(before[key]==after[key] for key in RAW)
            assert next(later,None) is not None
            failed+=1
            reports.append(dict(original_run=name,nodeid=node,all_original_native_raw_records_are_unchanged_prefix=len(earlier),
                                original_trace_sha256=sha(old[node]),corrected_trace_sha256=sha(paths[node]),
                                original_scope="actor generation ambiguity" if "uncache-recovery" in name else "reference domain/connection/reset phase assumption",
                                dut_or_stimulus_changed_to_bless_failure=False))
        assert failed==expected
    assert len(reports)==11
    return reports


def active_transactions(path):
    result=[]
    for row in events(path):
        inp=row["input"]
        for kind,field in (("dispatch","valid"),("addresses","valid"),("data","valid"),("loads","execution"),("raw_queries","valid"),("rar_queries","valid")):
            for packet in inp[kind]:
                valid=packet[field]["valid"] if field=="execution" else packet[field]
                if valid:
                    result.append((kind,packet))
    return result


def reject_green_illegal_preludes(paths):
    original=ROOT/"results/lsq-expanded-12"
    manifest,source,nodes=verify_common(original)
    assert manifest["tests"]=={"PASS":216,"FAIL":37} and len(source)==343
    old=paths_by_node(original)
    rejected=[]
    unchanged=0
    for node,path in old.items():
        if not has_prelude(node):
            same_raw(path,paths[node])
            unchanged+=1
            continue
        assert not nodes[node]
        bad=next(row for row in events(path) if any(d["valid"] and rob(d["rob"])<rob(row["input"]["pending"]) for d in row["input"]["dispatch"]))
        new=next(row for row in events(paths[node]) if any(d["valid"] for d in row["input"]["dispatch"]))
        assert bad["input"]["pending"]["value"]==9 and new["input"]["pending"]["value"]==0
        assert new["input"]["pending_next"]==new["input"]["pending"] and new["input"]["dispatch"]==bad["input"]["dispatch"]
        assert active_transactions(path)==active_transactions(paths[node]), "no smaller pool, changed transactions, removed cases or narrowed completion domain"
        try:
            inspect(path)
        except AssertionError:
            pass
        else:
            raise AssertionError("preserved independent retirement core must reject the illegal original green prelude")
        rejected.append(dict(nodeid=node,original_native_result="PASS_but_rejected_input_domain",first_illegal_dispatch_tick=bad["post_tick"],
                             original_pending_rob=bad["input"]["pending"],corrected_pending_rob=new["input"]["pending"],
                             all_active_original_transactions_preserved=True,independent_v1_core_still_rejects_old_trace=True,
                             original_trace_sha256=sha(path),corrected_trace_sha256=sha(paths[node])))
    assert len(rejected)==3 and unchanged==250
    return dict(original_run=original.name,unchanged_other_case_raw_histories=unchanged,rejected_original_native_pass_preludes=rejected)


def audit(name):
    assert name=="lsq-expanded-13", "exact253 corrected producer scope; add a version for later ranges"
    run,prior=ROOT/"results"/name,ROOT/"results/lsq-expanded-11"
    manifest,source,nodes=verify_common(run)
    old,_,old_nodes=verify_common(prior)
    assert manifest["tests"]=={"PASS":216,"FAIL":37} and len(nodes)==253
    assert old["tests"]=={"PASS":173,"FAIL":37} and len(old_nodes)==210
    paths,old_paths=paths_by_node(run),paths_by_node(prior)
    assert set(paths)==set(nodes) and set(old_paths)==set(old_nodes)<=set(nodes)
    counts,cases,wake_mid=Counter(),[],set()
    for node,path in sorted(paths.items()):
        if node in old_nodes:
            assert nodes[node]==old_nodes[node]
            records=same_raw(path,old_paths[node])
            detail=dict(all_raw_samples_equal_previous210=records)
            counts["previous210_cases_all_raw_samples_unchanged"]+=1
        else:
            assert not nodes[node]
            detail=inspect(path)
            records=detail["counts"]["raw_records"]
            counts.update(detail["counts"])
            for key in ("allocated","completed","cancelled","reset_aborted"):
                counts["new_"+key]+=detail[key]
            counts["new_cases"]+=1
            if "test_each_real_mid_wakeup_cancel_" in node:
                assert len(detail["actual_mid_next_edge_redirect_witnesses"])==1
                witness=detail["actual_mid_next_edge_redirect_witnesses"][0]
                assert node.endswith(f'[{witness["mid"]}]')
                wake_mid.add(witness["mid"])
        counts["all_continuous_raw_records"]+=records
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),result="FAIL" if nodes[node] else "PASS",**detail))
    assert counts["previous210_cases_all_raw_samples_unchanged"]==210 and counts["new_cases"]==43
    assert counts["new_allocated"]==1897 and counts["new_completed"]==996 and counts["new_cancelled"]==848 and counts["new_reset_aborted"]==53
    assert counts["new_allocated"]==counts["new_completed"]+counts["new_cancelled"]+counts["new_reset_aborted"]
    assert counts["all_aborted_loads_same_physical_slot_new_uid_completed"]==844 and counts["all_aborted_stores_same_physical_slot_new_uid_completed"]==57
    assert counts["actual_original_load_bus_fires"]==704 and counts["actual_original_store_bus_write_fires"]==2
    assert counts["actual_original_sid_responses"]==686 and counts["external_jobs_aborted_by_common_reset_not_returned"]==20
    assert counts["actual_original_bypass_data_error_consumptions"]==396 and counts["actual_resetless_old_s1_data_error_s2_on_reset"]==1
    assert counts["actual_original_replay_grants"]==879 and counts["actual_original_slot_feedbacks"]==876 and counts["actual_original_store_byte_fragment_fires"]==99
    assert wake_mid==set(range(16)) and counts["actual_full_120_replay_same_slots_granted_feedback_completed_cases"]==4
    assert counts["actual_capacity_rollback_complete_metadata"]==3 and counts["common_system_active_reset_events"]==13
    helper_proofs=original_failure_prefixes(paths)
    rejected_preludes=reject_green_illegal_preludes(paths)
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files=(Path(__file__),ROOT/"tools/audit_lsq_recovery_history_v1.py",ROOT/"tools/audit_lsq_population_v1.py",ROOT/"tools/audit_lsq_memory_v1.py",ROOT/"tools/audit_lsq_bus_v2.py",ROOT/"tools/audit_lsq_bus_v3.py")
    for file in files:
        target=dest/file.name
        if target.exists():
            assert sha(target)==sha(file)
        else:
            shutil.copy2(file,target)
    report=dict(run=name,status="NOT_PASS_253_case_legal_shared_recovery_reset_and_external_obligations_audited",tests=manifest["tests"],snapshot_files=len(source),
                counts=dict(counts),all_16_mid_next_response_edge_redirect_witnesses=sorted(wake_mid),helper_corrections_original_raw_prefix_proofs=helper_proofs,
                rejected_green_preludes_and_actual_producer_correction=rejected_preludes,
                previous210_history_audit_sha256=sha(prior/"uncache-history-audit-v2.json"),auditors={file.name:sha(dest/file.name) for file in files},cases=cases,
                limits="Exact253 scope: independent v1 transaction/retirement core unchanged and still rejects original3 illegal prelude traces; v2 proves only pending0-before-ROB1.. replaced illegal pending9 and all active transactions preserved. All old210 raw histories/37FAIL/16 explicitly protocol-only probes unchanged. New43 strict cases check original UIDs, both-branch recovery/full120Replay-56RAW-96RAR refill, every redirect external response, original bytes/errors; all901 cancel/reset owners have same physical slot new UID truly complete. Common system reset explicitly aborts20 external jobs,2 already-accepted external Store writes NOT retracted/NOT counted complete. Local-only reset with late old external responses remains unverified. Resetless old s1 data/errors emerge at s2 during reset and are checked, never globally masked. No full legal mixed random/fair-drain, arbitrary parameters, fresh elaboration or Backend/ISA signoff.")
    output=run/"recovery-history-audit-v2.json"
    if output.exists():
        assert json.loads(output.read_text())==report
    else:
        output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({key:value for key,value in report.items() if key not in ("cases","helper_corrections_original_raw_prefix_proofs","rejected_green_preludes_and_actual_producer_correction")},indent=2,ensure_ascii=False))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
