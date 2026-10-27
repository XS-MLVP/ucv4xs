#!/usr/bin/env python3
"""Known-width retirement on VSQ and both real parents; preserve every FAIL."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_checkpoint_pool_v1 import validate_run
from audit_coverage_points_v1 import records, sha256_file, summarize
from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases, failure_digest
from audit_gap_closure_v1 import audit as audit_delta, digest_keys, native, point_sets
from audit_native_case_probe_v1 import journal_streams, stable_run, xml_node
from audit_native_contributor_scope_v1 import contributors, same_summary
from audit_store_strict_lifetimes_v1 import source_lines
from audit_uq_page_pairs_v1 import functional_counts, node_summaries
from audit_vsq_cancel_capacity_v1 import FULL as BEFORE_FULL, PAIRS as CANCEL_PAIRS, FAIL_NODE, failure_witness
from audit_vsq_recovery_boundaries_v1 import ROOT, SOURCES
from audit_vsq_release_windows_v1 import FULL_PATHS, line_delta

FULL = "vsq-retire-known-width-contributor-regression-01"
PAIRS = (
    ("virtual_store_queue", "vsq-retire-known-width-baseline-01", "vsq-retire-known-width-after-01", "VSQ-RETIRE.batch_width"),
    ("store_queue", "sq-retire-known-width-baseline-01", "sq-retire-known-width-after-01", "SQ-PERMIT.retired"),
    ("lsq_wrapper", "lsq-retire-known-width-baseline-01", "lsq-retire-known-width-after-01", "LSQ-RETIRE.multi_flow"),
)
PRIMARY = dict(virtual_store_queue="virtual_store_queue.summary.json", store_queue="store_queue.summary.json", lsq_wrapper="lsq_wrapper.summary.json")
PROFILES = ((1, 1), (8, 8), (8, 2), (1, 1))


def load(path):
    return json.loads(path.read_text())


def targets(dat, dut):
    want = {f"retireReqNumReg[{bit}]:{direction}" for bit in (4, 6) for direction in ("0->1", "1->0")}
    points = [p for p in records(dat) if p["t"] == "toggle" and p["f"] == str(ROOT / SOURCES[dut]) and p["o"] in want]
    assert len(points) == len(want)
    return [dict(source=SOURCES[dut], source_line=int(p["l"]), point=p["o"], hierarchy=p["h"], hit=p["hit"]) for p in sorted(points, key=lambda p: p["o"])]


def witness(run, dut):
    paths = [p for p in (ROOT/"results"/run/"cases").rglob("vsq-retire-known-width-witness.json") if load(p)["dut"] == dut]
    assert len(paths) == 1
    path, item = paths[0], load(paths[0])
    assert item["format"] == "lsq-vsq-retire-known-width-witness-v1" and len(item["public_lifetime_SHA256"]) == 64
    assert item["normal_virtual_uops"] == 18 and item["normal_physical_flows"] == 82
    assert item["cancelled_uids"] == item["resets_between_profiles"] == 0
    assert len(item["profiles"]) == 4
    base, seen, robs = 0, set(), set()
    for phase, (part, (count, flows)) in enumerate(zip(item["profiles"], PROFILES)):
        assert part["phase"] == phase and part["physical_base"] == base
        assert part["virtual_uops"] == count and part["flows_per_uop"] == flows and 0 < flows <= 16
        assert part["batch_physical_flows"] == count * flows <= 64
        assert set(part["normal_uids"]) == set(part["actual_completed_uids"]) and not seen & set(part["normal_uids"])
        assert len(part["normal_uids"]) == (count if dut == "virtual_store_queue" else count * flows)
        seen.update(part["normal_uids"])
        allocated = part["allocated_virtual_uops"]
        assert len(allocated) == count and [entry["flows"] for entry in allocated] == [flows] * count
        assert [entry["physical_end"] for entry in allocated] == [base + (i + 1) * flows for i in range(count)]
        batch_robs = {tuple(sorted(entry["rob"].items())) for entry in allocated}
        assert len(batch_robs) == count and not robs & batch_robs
        robs |= batch_robs
        if dut == "virtual_store_queue":
            moves = part["actual_retired_ptr_transitions"]
            assert [row[1] for row in moves] == [base % 256, (base + count * flows) % 256] and moves[1][0] > moves[0][0]
        else:
            assert part["actual_Sbuffer_fragments"] == count * flows and part["zero_consumed_fragments_before_permission"]
            assert part["all_S2_STD_ready_before_permit_tick"] > 0
        if dut == "lsq_wrapper":
            assert part["original_Load_S3_completed"] and part["original_Load_PA_bytes_checked"]
            assert part["retirement_ROB_boundary"]["value"] == allocated[0]["rob"]["value"] + count
        base += count * flows
        assert part["actual_physical_tail"] == base
    assert base == 82 and len(robs) == 18 and len(seen) == (18 if dut == "virtual_store_queue" else 82)
    if dut == "virtual_store_queue":assert not item["parent_memory_claimed"]
    else:assert item["actual_Sbuffer_fragments"] == 82
    if dut == "lsq_wrapper":assert item["normal_Load_uids"] == 4
    return dict(path=str(path.relative_to(ROOT)), SHA256=sha256_file(path), witness=item)


def audit_pair(dut, before, after, scenario):
    old, new = validate_run(before, dut), validate_run(after, dut)
    assert old["source"] == new["source"]
    a, b = cases(before), cases(after)
    assert set(a) < set(b) and len(b) == len(a) + 1 and all(b[node] == value for node, value in a.items())
    assert FAIL_NODE not in b
    node = next(iter(set(b) - set(a)))
    closure = audit_delta(before, after, dut, dut.upper() + "-RETIRE-KNOWN-WIDTH", node)
    assert all(closure["verification"].values())
    prior, current = targets(old["dat"], dut), targets(new["dat"], dut)
    assert all(point["hit"] > 0 for point in current)
    old_stream, new_stream = node_summaries(before, PRIMARY[dut]), node_summaries(after, PRIMARY[dut])
    assert all(new_stream[node] == value for node, value in old_stream.items())
    functions = {name: functional_counts(name, dut, scenario) for name in (before, after)}
    assert functions[after]["checked"]["count"] > functions[before]["checked"]["count"]
    report = dict(format="lsq-vsq-retire-known-width-evidence-v1", dut=dut, before_run=before, after_run=after,
        contract="docs/contracts/vsq-retire-known-width.md", baseline_tests=len(a), after_tests=len(b), added_nodes=[node],
        source_aggregate=old["source"]["aggregate_SHA256"], native_build_id=closure["native_build_id"],
        raw_nonwrapper_metrics=closure["metrics"], retire_count_targets=dict(before=prior, after=current),
        original_source_line_coverage=line_delta(source_lines(old["meta"],old["dat"],dut),source_lines(new["meta"],new["dat"],dut)),
        functional=functions, public_lifetime=witness(after,dut),
        verification=dict(actual_native_dut_and_full_reference=True, same_source_build_and_three_point_universes=True,
            all_original_results_and_primary_streams_equal=True, no_old_native_hit_lost=True,
            actual_native_count_directions_hit=True, known_warmup_then_64_16_1_batches=True,
            bounded_flow_reservation_and_issue=True, all_original_UIDs_normal_completion=True,
            original_Load_PA_and_S3_completed_if_wrapper=True),
        limits="Positive directed selection, not a replacement for the required head-precommit/flushSelf failure or full six-build execution. No high startup-bit/global illegal-input waiver, 128-uop-parent or all-LSQ acceptance.")
    write_report(ROOT/"results"/after/"vsq-retire-known-width-evidence-v1.json", report)
    return report


def audit_full():
    status, source = stable_run(FULL)
    baseline_status, _ = stable_run(BEFORE_FULL)
    assert baseline_status["manifest_tests"] == {"PASS":1005,"FAIL":172}
    assert status["manifest_tests"] == {"PASS":1008,"FAIL":172} and status["total_cases"] == 1180 and status["pytest_exitstatus"] == 1
    old, new = cases(BEFORE_FULL), cases(FULL)
    assert len(old) == 1177 and len(new) == 1180 and all(new[node] == value for node,value in old.items())
    added = set(new)-set(old)
    assert added == set().union(*(set(cases(after))-set(cases(before)) for _,before,after,_ in PAIRS))
    assert len(added) == 3 and all(new[node]["outcome"] == "PASS" for node in added)
    assert failure_digest(old) == failure_digest(new) and old[FAIL_NODE] == new[FAIL_NODE] and new[FAIL_NODE]["outcome"] == "FAIL"
    manifest = load(ROOT/"results"/FULL/"execution/manifest.json")
    assert len([a for a in manifest["artifacts"] if a["kind"] == "native"]) == 6
    command = load(ROOT/"results"/FULL/"command.json")["command"]
    assert command[command.index("--lsq-trace-max-mb")+2:] == FULL_PATHS + ["--tb=short"]
    a,b = contributors(BEFORE_FULL),contributors(FULL)
    assert {dut:len(items) for dut,items in b.items()} == dict(forward_module=186,physical_store_queue=70,store_queue=89,lsq_wrapper=743)
    for dut,items in a.items():assert all(same_summary(value,b[dut][node]) for node,value in items.items())
    nodes = set().union(*(set(items) for items in b.values()))
    for dut,filename,previous in (("virtual_store_queue","virtual_store_queue.summary.json",49),("unalign_queue","unalign_queue.summary.json",42)):
        a,b = node_summaries(BEFORE_FULL,filename),node_summaries(FULL,filename)
        assert len(a) == previous and len(b) == previous+int(dut=="virtual_store_queue") and all(b[node] == value for node,value in a.items())
        meta,_ = native(FULL,dut);assert meta["artifact"]["input_files"] == len(b)
        nodes |= {xml_node(node) for node in b}
    assert nodes == set(new)
    a,b = journal_streams(BEFORE_FULL),journal_streams(FULL)
    assert len(a) == 2226 and len(b) == 2229 and all(b[key] == value for key,value in a.items())
    rows=[]
    for dut in ("forward_module","physical_store_queue","store_queue","lsq_wrapper","unalign_queue","virtual_store_queue"):
        ma,da = native(BEFORE_FULL,dut);mb,db = native(FULL,dut)
        assert ma["artifact"]["build"] == mb["artifact"]["build"]
        for filename,digest in mb["artifact"]["build"]["files"].items():assert sha256_file(Path(filename)) == digest
        parsed = summarize(db,mb["artifact"]["build"],mb["artifact"])
        assert parsed["raw_parser_matches_analyzer"] and parsed["coverage_artifact_matches_dat"]
        a,b = point_sets(da),point_sets(db);metrics={}
        for kind in a:
            assert a[kind]["all"] == b[kind]["all"] and a[kind]["hit"] <= b[kind]["hit"]
            gain = b[kind]["hit"] - a[kind]["hit"]
            metrics[kind] = dict(before_hit=len(a[kind]["hit"]),after_hit=len(b[kind]["hit"]),total=len(b[kind]["all"]),
                newly_hit=len(gain),newly_hit_SHA256=digest_keys(gain),newly_missing=0,still_missing=len(b[kind]["missing"]))
        row = dict(dut=dut,old_run=BEFORE_FULL,native_build_id=mb["artifact"]["build"]["build_id"],metrics=metrics,
            original_native_inputs=ma["artifact"]["input_files"],current_native_inputs=mb["artifact"]["input_files"],
            original_source_line_coverage=line_delta(source_lines(ma,da,dut),source_lines(mb,db,dut)))
        if dut in SOURCES:
            directed = next(after for key,_,after,_ in PAIRS if key == dut)
            actual,selected = witness(FULL,dut),witness(directed,dut)
            assert actual["witness"] == selected["witness"]
            row["public_witness_SHA256"] = actual["SHA256"]
            row["retire_count_targets"] = dict(before=targets(da,dut),after=targets(db,dut))
            assert all(point["hit"] > 0 for point in row["retire_count_targets"]["after"])
            row["remaining_count_domain_directions"] = [dict(source=SOURCES[dut],source_line=int(p["l"]),point=p["o"],hierarchy=p["h"],hit=0)
                for p in records(db) if p["t"] == "toggle" and p["f"] == str(ROOT/SOURCES[dut]) and not p["hit"]
                and (p["o"].startswith("retireReqNumReg[") or p["o"].startswith("cancelCount["))]
            assert len(row["remaining_count_domain_directions"]) == (2 if dut == "virtual_store_queue" else 4)
        else:
            assert sha256_file(da) == sha256_file(db)
            row["unchanged_native_dat_SHA256"] = sha256_file(db)
        rows.append(row)
    for filename in ("store_queue.summary.json","sq_actor.summary.json","sq_checks.summary.json"):
        def failed(run):return next(value for node,value in node_summaries(run,filename).items() if xml_node(node)==FAIL_NODE)
        assert failed(BEFORE_FULL)==failed(FULL)
    prior = load(ROOT/"results"/BEFORE_FULL/"vsq-cancel-capacity-contributor-evidence-v1.json")
    hashes = prior["unchanged_generic_actor_SHA256"]
    assert all(sha256_file(ROOT/path)==digest for path,digest in hashes.items())
    assert failure_witness(FULL)["observed_old_owners"] == failure_witness(BEFORE_FULL)["observed_old_owners"]
    # The three successful cancellation histories are also kept byte-identical.
    for dut,_,after,_,_ in CANCEL_PAIRS:
        from audit_vsq_cancel_capacity_v1 import witnesses
        assert witnesses(FULL,dut)["witness"] == witnesses(after,dut)["witness"]
    report = dict(format="lsq-vsq-retire-known-width-contributor-v1",run=FULL,status=status,source_aggregate=source["aggregate_SHA256"],
        original_nodes=1177,current_nodes=1180,added_nodes=sorted(added),added_passing_nodes=3,original_failures=172,
        original_failure_SHA256=failure_digest(old),current_failure_SHA256=failure_digest(new),rows=rows,
        unchanged_generic_actor_SHA256=hashes,original_wrapper_public_check_actor_summaries_equal=2226,
        head_permit_failure=failure_witness(FULL),required_new_functional_failures=prior["required_new_functional_failures"],
        coverage_monotonicity=dict(name="all_old_native_hits_retained",passed=True,status="PASS",failed_duts=[],newly_missing_toggle_points=0,required=True,waived=False),
        verification=dict(actual_fresh_complete_six_build_execution=True,old1177_results_and172_failure_details_equal=True,
            all_original_contributors_and_public_streams_equal=True,all_three_witnesses_equal_directed=True,
            required_head_permit_failure_and_old_bytes_retained=True,all_prior_cancellation_witnesses_equal=True,
            same_builds_and_three_point_universes=True,no_old_native_hit_lost=True,
            locked_analyzer_and_fixed_build_hashes_checked=True,original_generic_actor_hashes_unchanged=True,
            source_launch_end_aggregates_equal=True,no_cycle_JSON_or_waveforms=True),
        limits="Evidence/coverage audit PASS is not functional acceptance of the172required failures. No startup high-bit or head-flush legality waiver, unified regression15 numerator update, or reduced parent scope is claimed.")
    write_report(ROOT/"results"/FULL/"vsq-retire-known-width-contributor-evidence-v1.json",report)
    return report


if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--full",action="store_true");args=parser.parse_args()
    for pair in PAIRS:
        row=audit_pair(*pair)
        print(json.dumps({k:row[k] for k in ("dut","baseline_tests","after_tests","raw_nonwrapper_metrics","verification")},indent=2))
    if args.full:print(json.dumps(audit_full(),indent=2))
