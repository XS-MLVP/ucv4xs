#!/usr/bin/env python3
"""Capacity-cancel evidence, including the required head-permit counterexample."""
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
from audit_vsq_recovery_boundaries_v1 import SOURCES
from audit_vsq_release_windows_v1 import FULL_PATHS, line_delta

ROOT = Path(__file__).resolve().parents[1]
BEFORE_FULL = "vsq-retire-batch-contributor-regression-01"
FULL = "vsq-cancel-capacity-contributor-regression-01"
FAIL_NODE = "tests.store_queue.test_cancel_capacity::test_real_cancel_capacity_old_bytes_and_every_new_UID_normal_consumption[True]"
PAIRS = (
    ("virtual_store_queue", "vsq-cancel-capacity-baseline-01", "vsq-cancel-capacity-after-01", "VSQ-REDIRECT.capacity_suffix", (4, 5, 6, 7)),
    ("store_queue", "sq-cancel-capacity-baseline-01", "sq-cancel-capacity-after-01", "SQ-RECOVER.capacity_suffix", (2, 3, 4, 5, 6)),
    ("lsq_wrapper", "lsq-cancel-capacity-baseline-01", "lsq-cancel-capacity-after-01", "LSQ-RECOVER.reuse", (4, 6)),
)


def load(path):
    return json.loads(path.read_text())


def targets(dat, dut, bits):
    want = {f"cancelCount[{bit}]:{direction}" for bit in bits for direction in ("0->1", "1->0")}
    result = [p for p in records(dat) if p["t"] == "toggle" and p["f"] == str(ROOT / SOURCES[dut]) and p["o"] in want]
    assert len(result) == len(want)
    return [dict(source=SOURCES[dut], source_line=int(p["l"]), point=p["o"], hierarchy=p["h"], hit=p["hit"]) for p in sorted(result, key=lambda p: p["o"])]


def witnesses(run, dut):
    paths = [p for p in (ROOT / "results" / run / "cases").rglob("vsq-cancel-capacity-witness.json") if load(p)["dut"] == dut]
    assert len(paths) == 1
    path, report = paths[0], load(paths[0])
    assert report["format"] == "lsq-vsq-cancel-capacity-witness-v1" and len(report["public_lifetime_SHA256"]) == 64
    specs = [(0,4,2), (62,8,2), (126,16,2), (190,32,2), (254,64,0)]
    if dut == "virtual_store_queue":specs.append((318,128,0))
    if dut == "lsq_wrapper":specs = [(0,16,2),(62,64,0)]
    assert len(report["profiles"]) == len(specs)
    old_uids, new_uids = set(), set()
    for index, (part, (base, count, kept)) in enumerate(zip(report["profiles"], specs)):
        assert part["profile"] == index and part["physical_base"] == base and part["cancel_uops"] == count and part["kept_uops"] == kept
        assert part["actual_recovered_tail"] == (base + kept) % 256 and part["physical_flows"] <= 64
        reused = part["reuse_old_new_virtual_flow_end"] if dut == "virtual_store_queue" else part["reuse_old_new_position"]
        assert len(reused) == count and len({row[2] for row in reused}) == count
        assert {row[1] for row in reused} == set(part["new_completed_uids"])
        assert min(row[1] for row in reused) > max(row[0] for row in reused)
        old_uids.update(row[0] for row in reused); new_uids.update(row[1] for row in reused)
        if "recovery" in part:
            assert part["recovery"]["actual_sq_responses"] == [(base + kept) % 256]
            assert part["recovery"]["sq_stall_cycles"] > 0
        if dut == "lsq_wrapper":
            assert part["original_Load_completions"] == int(bool(kept)) and part["new_Load_completions"] == part["cancelled_Load_uids"] == 1
    assert old_uids.isdisjoint(new_uids) and len(old_uids) == len(new_uids) == sum(item[1] for item in specs)
    if dut == "virtual_store_queue":
        assert report["normal_virtual_uids"] == 446 and report["cancelled_virtual_uids"] == report["exact_virtual_slot_reuses"] == 252
        assert report["normal_physical_flows"] == 382 and not report["parent_memory_claimed"]
    else:
        total, cancelled = (318,124) if dut == "store_queue" else (126,80)
        assert report["normal_store_uids"] == report["actual_Sbuffer_fragments"] == total
        assert report["cancelled_store_uids"] == report["exact_physical_slot_reuses"] == cancelled
        if dut == "store_queue":assert not report["head_permit_before_redirect"]
        else:assert report["normal_Load_uids"] == 3 and report["cancelled_Load_uids"] == 2
    return dict(path=str(path.relative_to(ROOT)), SHA256=sha256_file(path), witness=report)


def failure_witness(run):
    paths = list((ROOT / "results" / run / "cases").rglob("vsq-cancel-capacity-failure.json"))
    assert len(paths) == 1
    path, item = paths[0], load(paths[0])
    assert item["physical_base"] == 254 and item["cancel_uops"] == 64 and item["kept_uops"] == 0 and item["head_permit_before_redirect"]
    assert all(not owner["parts"] for owner in item["cancelled_old_owners"])
    pins, observed_old = item["actual_public_Sbuffer"], []
    for lane in range(2):
        prefix = f"io_writeToSbuffer_req_{lane}_"
        if not pins[prefix + "valid"]:continue
        va = pins[prefix + "bits_vaddr"]
        old = [owner for owner in item["cancelled_old_owners"] if owner["vaddr"] // 16 * 16 == va]
        assert len(old) == 1 and not any(owner["vaddr"] // 16 * 16 == va for owner in item["replacement_owners"])
        owner = old[0]
        assert pins[prefix + "bits_addr"] == owner["paddr"] // 16 * 16
        mask = pins[prefix + "bits_mask"]
        byte_bits = sum(255 << (8 * b) for b in range(16) if mask >> b & 1)
        assert mask == 255 and not ((pins[prefix + "bits_data"] ^ owner["data"]) & byte_bits)
        observed_old.append(dict(lane=lane, uid=owner["uid"], position=owner["position"], vaddr=va))
    assert observed_old and item["tick"] == 932
    return dict(path=str(path.relative_to(ROOT)), SHA256=sha256_file(path), observed_old_owners=observed_old,
                identity_matches_cancelled_not_replacement=True, classification="OPEN_HEAD_PRECOMMIT_FLUSHSELF_BOUNDARY",
                upstream_legality_proven=False, waived=False)


def audit_pair(dut, before, after, scenario, bits):
    old, new = validate_run(before, dut), validate_run(after, dut)
    assert old["source"] == new["source"]
    old_cases, new_cases = cases(before), cases(after)
    assert set(old_cases) < set(new_cases) and len(new_cases) == len(old_cases) + 1
    assert all(new_cases[node] == value for node, value in old_cases.items())
    new_node = next(iter(set(new_cases) - set(old_cases)))
    assert FAIL_NODE not in new_cases
    closure = audit_delta(before, after, dut, dut.upper() + "-CANCEL-CAPACITY-PUBLIC-REUSE", new_node)
    assert all(closure["verification"].values())
    old_targets, new_targets = targets(old["dat"], dut, bits), targets(new["dat"], dut, bits)
    assert all(point["hit"] > 0 for point in new_targets)
    functions = {name:functional_counts(name, dut, scenario) for name in (before, after)}
    assert functions[after]["checked"]["count"] > functions[before]["checked"]["count"]
    primary_name = "virtual_store_queue.summary.json" if dut == "virtual_store_queue" else "store_queue.summary.json" if dut == "store_queue" else "lsq_wrapper.summary.json"
    original, current = node_summaries(before, primary_name), node_summaries(after, primary_name)
    assert all(current[node] == value for node, value in original.items())
    result = dict(format="lsq-vsq-cancel-capacity-evidence-v1", dut=dut, before_run=before, after_run=after,
        contract="docs/contracts/vsq-cancel-capacity.md", baseline_tests=len(old_cases), after_tests=len(new_cases), added_nodes=[new_node],
        source_aggregate=old["source"]["aggregate_SHA256"], native_build_id=closure["native_build_id"], raw_nonwrapper_metrics=closure["metrics"],
        cancel_count_targets=dict(before=old_targets, after=new_targets), functional=functions,
        original_source_line_coverage=line_delta(source_lines(old["meta"],old["dat"],dut), source_lines(new["meta"],new["dat"],dut)),
        public_reuse=witnesses(after,dut),
        verification=dict(actual_native_dut_and_full_reference=True, same_source_build_and_three_point_universes=True,
            old_nodes_and_primary_streams_equal=True, no_old_hit_lost=True, actual_target_directions_hit=True,
            every_cancelled_slot_has_distinct_completed_new_UID=True, legal_virtual_vs_physical_capacity_separate=True,
            locked_analyzer_artifact_and_source_hashes_checked=True),
        limits="Directed selected positive run only, not substitute for required original SQ head-permit failure. That node is retained in both probes and the full contributor execution. No all-LSQ/128-uop-parent or release-wait closure is claimed.")
    write_report(ROOT / "results" / after / "vsq-cancel-capacity-evidence-v1.json", result)
    return result


def audit_full():
    status, source = stable_run(FULL)
    previous_status, _ = stable_run(BEFORE_FULL)
    assert previous_status["manifest_tests"] == {"PASS":1002,"FAIL":171}
    assert status["manifest_tests"] == {"PASS":1005,"FAIL":172} and status["total_cases"] == 1177 and status["pytest_exitstatus"] == 1
    old, current = cases(BEFORE_FULL), cases(FULL)
    assert len(old) == 1173 and set(old) < set(current) and all(current[node] == value for node,value in old.items())
    added = set(current) - set(old)
    assert len(added) == 4 and {node for node in added if current[node]["outcome"] == "FAIL"} == {FAIL_NODE}
    positives = set().union(*(set(cases(after))-set(cases(before)) for _,before,after,_,_ in PAIRS))
    assert added == positives | {FAIL_NODE}
    assert failure_digest(old) == failure_digest({node:current[node] for node in old})
    command = load(ROOT / "results" / FULL / "command.json")["command"]
    assert command[command.index("--lsq-trace-max-mb")+2:] == FULL_PATHS + ["--tb=short"]
    manifest = load(ROOT / "results" / FULL / "execution/manifest.json")
    assert len([a for a in manifest["artifacts"] if a["kind"] == "native"]) == 6
    previous, fresh = contributors(BEFORE_FULL), contributors(FULL)
    assert {dut:len(items) for dut,items in fresh.items()} == dict(forward_module=186,physical_store_queue=70,store_queue=88,lsq_wrapper=742)
    for dut,items in previous.items():assert all(same_summary(value,fresh[dut][node]) for node,value in items.items())
    nodes = set().union(*(set(items) for items in fresh.values()))
    for dut,filename,n in (("virtual_store_queue","virtual_store_queue.summary.json",48),("unalign_queue","unalign_queue.summary.json",42)):
        a,b = node_summaries(BEFORE_FULL,filename),node_summaries(FULL,filename)
        assert len(a)==n and len(b)==n+int(dut=="virtual_store_queue") and all(b[node]==value for node,value in a.items())
        meta,_ = native(FULL,dut);assert meta["artifact"]["input_files"] == len(b)
        nodes |= {xml_node(node) for node in b}
    assert nodes == set(current)
    a,b=journal_streams(BEFORE_FULL),journal_streams(FULL)
    assert len(a)==2223 and len(b)==2226 and all(b[key]==value for key,value in a.items())
    rows=[]
    for dut in ("forward_module","physical_store_queue","store_queue","lsq_wrapper","unalign_queue","virtual_store_queue"):
        old_meta,old_dat=native(BEFORE_FULL,dut);new_meta,new_dat=native(FULL,dut)
        assert old_meta["artifact"]["build"]==new_meta["artifact"]["build"]
        for filename,digest in new_meta["artifact"]["build"]["files"].items():assert sha256_file(Path(filename))==digest
        analyzed=summarize(new_dat,new_meta["artifact"]["build"],new_meta["artifact"])
        assert analyzed["raw_parser_matches_analyzer"] and analyzed["coverage_artifact_matches_dat"]
        before,after=point_sets(old_dat),point_sets(new_dat);metrics={}
        for kind in before:
            assert before[kind]["all"]==after[kind]["all"] and before[kind]["hit"]<=after[kind]["hit"]
            gained=after[kind]["hit"]-before[kind]["hit"]
            metrics[kind]=dict(before_hit=len(before[kind]["hit"]),after_hit=len(after[kind]["hit"]),total=len(after[kind]["all"]),
                               newly_hit=len(gained),newly_hit_SHA256=digest_keys(gained),newly_missing=0,still_missing=len(after[kind]["missing"]))
        row=dict(dut=dut,old_run=BEFORE_FULL,native_build_id=new_meta["artifact"]["build"]["build_id"],metrics=metrics,
                 original_native_inputs=old_meta["artifact"]["input_files"],current_native_inputs=new_meta["artifact"]["input_files"],
                 original_source_line_coverage=line_delta(source_lines(old_meta,old_dat,dut),source_lines(new_meta,new_dat,dut)))
        if dut in SOURCES:
            directed=next(after for key,_,after,_,_ in PAIRS if key==dut)
            actual,selected=witnesses(FULL,dut),witnesses(directed,dut)
            assert actual["witness"]==selected["witness"]
            row["full_witness_SHA256"]=actual["SHA256"]
            bits=next(bits for key,_,_,_,bits in PAIRS if key==dut)
            row["cancel_count_targets"]=dict(before=targets(old_dat,dut,bits),after=targets(new_dat,dut,bits))
            assert all(point["hit"]>0 for point in row["cancel_count_targets"]["after"])
        rows.append(row)
    original_probe,probe=cases("vsq-cancel-capacity-probe-01"),cases("vsq-cancel-capacity-probe-02")
    assert original_probe[FAIL_NODE]["outcome"] == probe[FAIL_NODE]["outcome"] == current[FAIL_NODE]["outcome"] == "FAIL"
    for name in ("vsq-cancel-capacity-probe-02",FULL):
        assert "StopIteration" in cases(name)[FAIL_NODE]["detail"]
        assert failure_witness(name)["observed_old_owners"] == failure_witness("vsq-cancel-capacity-probe-02")["observed_old_owners"]
    for filename in ("store_queue.summary.json","sq_actor.summary.json","sq_checks.summary.json"):
        streams=[node_summaries(name,filename) for name in ("vsq-cancel-capacity-probe-01","vsq-cancel-capacity-probe-02",FULL)]
        def failed(data):return next(value for node,value in data.items() if xml_node(node)==FAIL_NODE)
        assert failed(streams[0])==failed(streams[1])==failed(streams[2])
    actor_hashes = load(ROOT / "results/uq-page-contributor-regression-01/uq-page-contributor-regression-evidence-v1.json")["unchanged_generic_actor_SHA256"]
    assert all(sha256_file(ROOT/path)==digest for path,digest in actor_hashes.items())
    result=dict(format="lsq-vsq-cancel-capacity-contributor-v1",run=FULL,status=status,source_aggregate=source["aggregate_SHA256"],
        original_nodes=1173,current_nodes=1177,added_nodes=sorted(added),added_passing_nodes=3,original_failures=171,new_required_failures=[FAIL_NODE],
        original_failure_SHA256=failure_digest(old),current_failure_SHA256=failure_digest(current),rows=rows,
        original_wrapper_public_check_actor_summaries_equal=2223,head_permit_failure=failure_witness(FULL),
        unchanged_generic_actor_SHA256=actor_hashes,
        required_new_functional_failures=[dict(dut="store_queue",node=FAIL_NODE,outcome="FAIL",required=True,waived=False,
            evidence=f"results/{FULL}/vsq-cancel-capacity-contributor-evidence-v1.json",classification="OPEN_HEAD_PRECOMMIT_FLUSHSELF_BOUNDARY")],
        coverage_monotonicity=dict(name="all_old_native_hits_retained",passed=True,status="PASS",failed_duts=[],newly_missing_toggle_points=0,required=True,waived=False),
        verification=dict(actual_fresh_complete_six_build_execution=True,old1173_results_and171_failure_details_equal=True,
            all_original_contributors_and_public_streams_equal=True,all_three_positive_witnesses_equal_directed=True,
            one_new_head_permit_FAIL_explicitly_retained=True,failed_case_public_actor_check_streams_equal_both_probes=True,
            same_builds_and_three_point_universes=True,no_old_hit_lost=True,source_launch_end_aggregates_equal=True,
            original_generic_actor_hashes_unchanged=True,
            locked_analyzer_and_fixed_build_hashes_checked=True,no_cycle_JSON_or_waveforms=True),
        limits="Coverage/artifact audit PASS is not functional acceptance. The new required SQ head-precommit/flushSelf counterexample stays FAIL and has no upstream-legality exemption. Positive unlicensed cancellation does not replace it. All original171failures and regression15 unified227failures/denominators remain.")
    write_report(ROOT/"results"/FULL/"vsq-cancel-capacity-contributor-evidence-v1.json",result)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--full",action="store_true");args=parser.parse_args()
    for pair in PAIRS:
        result=audit_pair(*pair)
        print(json.dumps({k:result[k] for k in ("dut","baseline_tests","after_tests","raw_nonwrapper_metrics","verification")},indent=2))
    if args.full:print(json.dumps(audit_full(),indent=2))
