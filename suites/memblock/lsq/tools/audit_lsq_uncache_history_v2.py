#!/usr/bin/env python3
"""210-case v2: same semantic core, correct the rejected consumer-helper proof.

v1 is preserved verbatim in launch/evidence sources. Its actual transaction
checks succeeded; the helper-proof assertion guessed LQ8, while min-visible
fair consumption actually fired legal held LQ3. This is NOT a DUT waiver.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_uncache_history_v1 import inspect_uncache
from audit_lsq_population_v1 import RAW, events, inspect_replay, paths_by_node, same_raw
from audit_sq_initial import ROOT, sha, verify_common


def consumer_proof(paths, nodes):
    original=ROOT/"results/lsq-uncache-population-01"
    old,_,old_nodes=verify_common(original)
    assert old["tests"] == {"PASS":12,"FAIL":3}
    originals,corrections=paths_by_node(original),[]
    for node,failed in old_nodes.items():
        assert not nodes[node]
        if not failed:
            same_raw(originals[node],paths[node])
            continue
        assert "-nc]" in node
        old_trace=list(events(originals[node]))
        assert all(row["checked"] and "error" not in row for row in old_trace)
        held={old_trace[-1]["after"][f"io_replay_{bank}_bits_uop_lqIdx_value"] for bank in range(3) if old_trace[-1]["after"][f"io_replay_{bank}_valid"]}
        assert held == {3,4,8}
        prefix=0
        for before,after in zip(old_trace,events(paths[node])):
            if all(before[key] == after[key] for key in RAW):
                prefix+=1
                continue
            assert before["post_tick"] == after["post_tick"] == 170 and not any(before["input"]["replay_ready"])
            fired=[bank for bank in range(3) if after["input"]["replay_ready"][bank]]
            assert len(fired) == 1 and after["before"][f"io_replay_{fired[0]}_valid"]
            actual_uid=after["before"][f"io_replay_{fired[0]}_bits_uop_lqIdx_value"]
            assert actual_uid == min(held) == 3
            break
        assert prefix == 84
        corrections.append(dict(nodeid=node,common_raw_samples_before_fixed_order_wait=prefix,old_held_valid_lq_candidates=sorted(held),
                                corrected_first_additional_legal_grant_lq=actual_uid,old_model_and_dut_agreed=True,
                                original_trace_sha256=sha(originals[node]),corrected_trace_sha256=sha(paths[node])))
    assert len(corrections) == 3
    return corrections


def audit(name):
    run,baseline=ROOT/"results"/name,ROOT/"results/lsq-expanded-10"
    manifest,source,nodes=verify_common(run)
    old,_,old_nodes=verify_common(baseline)
    assert manifest["tests"] == {"PASS":173,"FAIL":37} and len(nodes) == 210
    assert old["tests"] == {"PASS":157,"FAIL":37} and len(old_nodes) == 194
    paths,old_paths=paths_by_node(run),paths_by_node(baseline)
    assert set(paths) == set(nodes) and set(old_paths) == set(old_nodes) <= set(nodes)
    counts,cases,visits=Counter(),[],set()
    for node,path in sorted(paths.items()):
        if node in old_nodes:
            assert nodes[node] == old_nodes[node]
            records=same_raw(path,old_paths[node])
            counts["previous194_all_raw_samples_bitwise_rechecked"]+=1
            detail=dict(raw_samples_bitwise_equal_previous=records)
        else:
            assert not nodes[node]
            if node.startswith("tests/lsq_wrapper/test_uncache_population.py::"):
                detail=inspect_uncache(path)
                visits.update(tuple(item) for item in detail["actual_mid_kind_bypass_visits"])
                counts["new_uncache_cases"]+=1
                counts["new_cancelled_original_uids"]+=detail["cancelled"]
            else:
                assert "test_three_lane_two_strict_waits_" in node
                detail=inspect_replay(path,False)
                assert detail["allocated"] == detail["completed"] == 128 and len(detail["slots_by_enqueue_lane"]) == 120
                counts["new_two_ma_full_pool_cases"]+=1
            for key in ("allocated","completed"):
                counts["new_"+key]+=detail[key]
            counts.update(detail["counts"])
            records=sum(1 for _ in events(path))
        counts["all_continuous_raw_records"]+=records
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),result="FAIL" if nodes[node] else "PASS",**detail))
    assert counts["previous194_all_raw_samples_bitwise_rechecked"] == 194 and counts["new_uncache_cases"] == 15 and counts["new_two_ma_full_pool_cases"] == 1
    assert counts["new_allocated"] == 446 and counts["new_completed"] == 443 and counts["new_cancelled_original_uids"] == 3
    assert counts["actual_original_uncache_request_fires"] == counts["actual_direction_bound_id_responses"] == counts["actual_direction_and_sid_bound_responses"] == counts["actual_original_bypass_s2_data_error_consumptions"] == counts["actual_original_uncache_replay_grants"] == 306
    assert counts["two_full_16_mid_generations_actually_consumed_cases"] == 9
    assert counts["actual_cancelled_s3_done_but_not_vlq_completed_loads"] == counts["cancelled_same_lq_slot_new_uid_bus_bypass_completed"] == counts["actual_both_branch_recovery_responses"] == counts["real_nc_nuke_same_original_slot_c0_feedbacks"] == 3
    assert visits == {(mid,kind,lane) for mid in range(16) for kind in ("nc","mmio_memory","io") for lane in range(3)}
    corrections=consumer_proof(paths,nodes)
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files=(Path(__file__),ROOT/"tools/audit_lsq_uncache_history_v1.py",ROOT/"tools/audit_lsq_population_v1.py",
           ROOT/"tools/audit_lsq_memory_v1.py",ROOT/"tools/audit_lsq_bus_v2.py",ROOT/"tools/audit_lsq_bus_v3.py")
    for file in files:
        copy_to=dest/file.name
        if copy_to.exists():
            assert sha(copy_to) == sha(file)
        else:
            shutil.copy2(file,copy_to)
    rejected=dest/"audit_lsq_uncache_history_v1.py"
    assert sha(rejected) == sha(run/"verification-source/tools/audit_lsq_uncache_history_v1.py") == "2e21794d6f474a1a386019cad0a1c448b0f8e753a075b1734d69a782bd858489"
    previous_audit=baseline/"wrap-history-audit-v1.json"
    assert json.loads(previous_audit.read_text())["tests"] == old["tests"]
    report=dict(run=name,status="NOT_PASS_210_case_full_uncache_nc_rar_and_recovery_histories_audited",tests=manifest["tests"],snapshot_files=len(source),
                counts=dict(counts),actual_mid_kind_bypass_witnesses=len(visits),consumer_helper_corrections=corrections,
                rejected_v1_helper_proof=dict(auditor_sha256=sha(rejected),scope="helper-correction explanation only, not a DUT/reference/test failure",wrong_expected_first_additional_lq=8,actual_legal_first_additional_lq=3,actual_old_held_candidates=[3,4,8],test_stimuli_changed=False),
                previous_wrap_audit_sha256=sha(previous_audit),auditor_sha256={file.name:sha(dest/file.name) for file in files},cases=cases,
                limits="Exact210 scope: identical independent transaction core to preserved v1, which rejected only a wrong helper-proof guess8 versus actual fair min-visible3. All194 prior raw histories/37FAIL unchanged, including16 protocol-only probes. New15 strict Uncache cases cover mid0..15 xNC/memoryMMIO/IO x3bypass lanes, two generations,306 external attempts/grants/data consumptions; NC RAR uses real returned/bypassed NC data and actual C0 re-read plus independent branch redirect, not an invented RAR-generated redirect. Three cancelled already-S3-done but not VLQ-completed young UIDs each have same-LQ new UID completed, retired old Store bytes preserved. New twoMA+TLB120 pool uses real SQ. SID ownership ends at resp.fire; no requirement to hold SID until data consumption, old SID failure not waived. No full reset/all cancellation phases/random/Backend/ISA/fresh elaboration acceptance.")
    output=run/"uncache-history-audit-v2.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({key:value for key,value in report.items() if key not in ("cases","consumer_helper_corrections")},indent=2,ensure_ascii=False))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
