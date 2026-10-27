#!/usr/bin/env python3
"""Summarize full-run gap classifications and verified directed supplements."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from audit_evidence_io import write_report

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def counter_rows(rows: list[dict], field: str) -> dict:
    counter = Counter()
    for row in rows:
        counter.update(row.get(field, {}))
    return dict(sorted(counter.items()))


def audit(name: str) -> dict:
    run = ROOT / "results" / name
    line = load(run / "line-gap-closure-audit-v1.json")
    toggle = load(run / "toggle-gap-classification-v1.json")
    branch = load(run / "branch-gap-classification-v1.json")
    initial = load(run / "initial-branch-boundary-audit-v1.json")
    assert line["format"] == "lsq-line-gap-closure-v1"
    assert toggle["format"] == "lsq-toggle-gap-classification-v1" and toggle["native_duts"] == 38
    assert branch["format"] == "lsq-branch-gap-classification-v1" and branch["native_duts"] == 38
    assert all(initial["verification"].values()) and initial["total_missing_branch_points"] == branch["total_missing_branch_points"]
    contributor_path = ROOT / "results/store-strict-contributor-regression-02/store-strict-contributor-regression-evidence-v1.json"
    contributor = load(contributor_path)
    assert all(contributor["verification"].values()) and contributor["coverage_monotonicity"]["passed"]
    assert contributor["original_nodes"] == 1059 and contributor["current_nodes"] == 1066
    prefix_rerun_path = ROOT / "results/store-prefix-contributor-regression-01/store-prefix-contributor-regression-evidence-v1.json"
    prefix_rerun = load(prefix_rerun_path)
    assert all(prefix_rerun["verification"].values()) and prefix_rerun["coverage_monotonicity"]["passed"]
    uq_rerun_path = ROOT / "results/uq-page-contributor-regression-01/uq-page-contributor-regression-evidence-v1.json"
    uq_rerun = load(uq_rerun_path)
    assert all(uq_rerun["verification"].values()) and uq_rerun["coverage_monotonicity"]["passed"]
    release_rerun_path = ROOT / "results/vsq-release-contributor-regression-01/vsq-release-contributor-regression-evidence-v1.json"
    release_rerun = load(release_rerun_path)
    assert all(release_rerun["verification"].values()) and release_rerun["coverage_monotonicity"]["passed"]
    deep_rerun_path = ROOT / "results/vsq-deep-suffix-contributor-regression-01/vsq-deep-suffix-contributor-evidence-v1.json"
    deep_rerun = load(deep_rerun_path)
    assert all(deep_rerun["verification"].values()) and deep_rerun["coverage_monotonicity"]["passed"]
    batch_rerun_path = ROOT / "results/vsq-retire-batch-contributor-regression-01/vsq-retire-batch-contributor-evidence-v1.json"
    batch_rerun = load(batch_rerun_path)
    assert all(batch_rerun["verification"].values()) and batch_rerun["coverage_monotonicity"]["passed"]
    cancel_path = ROOT / "results/vsq-cancel-capacity-contributor-regression-01/vsq-cancel-capacity-contributor-evidence-v1.json"
    cancel = load(cancel_path)
    assert all(cancel["verification"].values()) and cancel["coverage_monotonicity"]["passed"]
    known_path = ROOT / "results/vsq-retire-known-width-contributor-regression-01/vsq-retire-known-width-contributor-evidence-v1.json"
    known = load(known_path)
    assert all(known["verification"].values()) and known["coverage_monotonicity"]["passed"]
    scalar_path = ROOT / "results/sq-scalar-reservation-contributor-regression-01/sq-scalar-reservation-contributor-evidence-v1.json"
    scalar = load(scalar_path)
    assert all(scalar["verification"].values()) and scalar["coverage_monotonicity"]["passed"]
    assert scalar["domain"] == "UNIT_INTERFACE_LSQ_CAPACITY" and not scalar["normal_full_core_producer_proven"]
    response_path = ROOT / "results/load-response-contributor-regression-02/load-response-payload-contributor-evidence-v1.json"
    response = load(response_path)
    assert all(response["verification"].values()) and response["coverage_monotonicity"]["passed"]
    assert response["current_nodes"] == 1457 and response["original_failures"] == 192
    raw_path = ROOT / "results/load-raw-owners-contributor-regression-02/load-RAW-owners-contributor-evidence-v1.json"
    raw = load(raw_path)
    assert all(raw["verification"].values()) and raw["coverage_monotonicity"]["passed"]
    assert raw["current_nodes"] == 1569 and raw["original_failures"] == 192
    assert raw["required_new_functional_failures"] == response["required_new_functional_failures"]
    recovery_boundary = load(run / "vsq-recovery-boundary-audit-v1.json")
    assert all(recovery_boundary["verification"].values()) and recovery_boundary["proven_post_reset_state3_points"] == 3

    closure_paths = [
        ROOT / "results/vlq-toggle-gap-after-02/directed-gap-closure-virtual_load_queue-v1.json",
        ROOT / "results/entry-toggle-gap-after-01/directed-gap-closure-uncache_entry_0-v1.json",
        ROOT / "results/entry-toggle-gap-after-02/directed-gap-closure-uncache-entry-family-v1.json",
        ROOT / "results/raw-toggle-gap-after-03/directed-gap-closure-load_queue_raw-v1.json",
        ROOT / "results/raw-toggle-gap-after-05/directed-gap-closure-load_queue_raw-v1.json",
        ROOT / "results/vsq-gap-after-04/directed-gap-closure-virtual_store_queue-v1.json",
        ROOT / "results/replay-metadata-gap-after-02/directed-gap-closure-load_queue_replay-v1.json",
        ROOT / "results/rar-latter-gap-after-02/directed-gap-closure-load_queue_rar-v1.json",
        ROOT / "results/deq-width-gap-after-02/directed-gap-closure-deq_module-v1.json",
        ROOT / "results/replay-checkpoint-pool-after-01/directed-gap-closure-load_queue_replay-v1.json",
        ROOT / "results/lq-checkpoint-pool-after-01/directed-gap-closure-load_queue-v1.json",
        ROOT / "results/lsq-checkpoint-pool-after-01/directed-gap-closure-lsq_wrapper-v1.json",
        ROOT / "results/forward-payload-pool-after-02/directed-gap-closure-forward_module-v1.json",
        ROOT / "results/psq-payload-pool-after-02/directed-gap-closure-physical_store_queue-v1.json",
        ROOT / "results/sq-payload-pool-after-02/directed-gap-closure-store_queue-v1.json",
        ROOT / "results/psq-strict-lifetimes-after-01/directed-gap-closure-physical_store_queue-v1.json",
        ROOT / "results/sq-strict-lifetimes-after-01/directed-gap-closure-store_queue-v1.json",
        ROOT / "results/lsq-strict-lifetimes-after-01/directed-gap-closure-lsq_wrapper-v1.json",
        ROOT / "results/forward-prefix-byte-after-01/directed-gap-closure-forward_module-v1.json",
        ROOT / "results/psq-prefix-byte-after-01/directed-gap-closure-physical_store_queue-v1.json",
        ROOT / "results/sq-prefix-byte-after-01/directed-gap-closure-store_queue-v1.json",
        ROOT / "results/lsq-prefix-byte-after-01/directed-gap-closure-lsq_wrapper-v1.json",
        ROOT / "results/uq-page-pairs-after-02/directed-gap-closure-unalign_queue-v1.json",
        ROOT / "results/psq-page-pairs-after-01/directed-gap-closure-physical_store_queue-v1.json",
        ROOT / "results/sq-page-pairs-after-01/directed-gap-closure-store_queue-v1.json",
        ROOT / "results/lsq-page-pairs-after-01/directed-gap-closure-lsq_wrapper-v1.json",
        ROOT / "results/vsq-release-windows-after-01/directed-gap-closure-virtual_store_queue-v1.json",
        ROOT / "results/sq-release-windows-after-01/directed-gap-closure-store_queue-v1.json",
        ROOT / "results/lsq-release-windows-after-01/directed-gap-closure-lsq_wrapper-v1.json",
        ROOT / "results/vsq-deep-suffix-after-02/directed-gap-closure-virtual_store_queue-v1.json",
        ROOT / "results/vsq-retire-batch-after-03/directed-gap-closure-virtual_store_queue-v1.json",
        ROOT / "results/vsq-cancel-capacity-after-01/directed-gap-closure-virtual_store_queue-v1.json",
        ROOT / "results/sq-cancel-capacity-after-01/directed-gap-closure-store_queue-v1.json",
        ROOT / "results/lsq-cancel-capacity-after-01/directed-gap-closure-lsq_wrapper-v1.json",
        ROOT / "results/vsq-retire-known-width-after-01/directed-gap-closure-virtual_store_queue-v1.json",
        ROOT / "results/sq-retire-known-width-after-01/directed-gap-closure-store_queue-v1.json",
        ROOT / "results/lsq-retire-known-width-after-01/directed-gap-closure-lsq_wrapper-v1.json",
        ROOT / "results/sq-scalar-reservation-after-01/directed-gap-closure-store_queue-v1.json",
        ROOT / "results/lsq-scalar-reservation-after-01/directed-gap-closure-lsq_wrapper-v1.json",
        ROOT / "results/lqu-response-payload-after-01/directed-gap-closure-load_queue_uncache-v1.json",
        ROOT / "results/lq-response-payload-after-01/directed-gap-closure-load_queue-v1.json",
        ROOT / "results/lsq-response-payload-after-01/directed-gap-closure-lsq_wrapper-v1.json",
        ROOT / "results/lq-RAW-owners-after-02/directed-gap-closure-load_queue-v1.json",
        ROOT / "results/lsq-RAW-owners-after-02/directed-gap-closure-lsq_wrapper-v1.json",
    ]
    closures = []
    for path in closure_paths:
        report = load(path)
        if report["format"] == "lsq-directed-gap-closure-v1":
            assert report["verification"]["same_native_build"]
            assert report["verification"]["all_denominators_unchanged"]
            assert report["verification"]["no_new_missing_points"]
            assert report["verification"]["after_functional_run_passed"]
            closures.append(dict(
                path=str(path.relative_to(ROOT)), dut=report["dut"], feature_id=report["feature_id"], case_id=report["case_id"],
                before_run=report["before_run"], after_run=report["after_run"], native_build_id=report["native_build_id"],
                metrics=report["metrics"], functional_before=report["functional_before"], functional_after=report["functional_after"],
                verification=report["verification"],
            ))
            if report["feature_id"] == "LRQ-METADATA-BOUNDARY-REUSE":
                closures[-1]["semantic_limit"] = "Historical two-single-allocation case proves boundary payloads, not same-slot reuse. Full public-slot lifecycle proof is in LRQ-CHECKPOINT-FULL-POOL-PUBLIC-REUSE and docs/contracts/replay-checkpoint-pool.md. Historical raw results are unchanged."
            if report["feature_id"] in ("LRQ-CHECKPOINT-FULL-POOL-PUBLIC-REUSE", "LQ-CHECKPOINT-FULL-POOL-PUBLIC-REUSE", "LSQ-CHECKPOINT-FULL-POOL-PUBLIC-REUSE"):
                evidence_path = path.parent / "checkpoint-pool-evidence-v1.json"
                evidence = load(evidence_path)
                assert evidence["after_run"] == report["after_run"] and evidence["dut"] == report["dut"]
                assert all(evidence["verification"].values())
                closures[-1]["checkpoint_pool_evidence"] = dict(
                    path=str(evidence_path.relative_to(ROOT)), contract=evidence["contract"],
                    registered_checkpoint_points=evidence["registered_checkpoint_points"],
                    original_source_line_coverage={k: v for k, v in evidence["original_source_line_coverage"].items() if k != "sources"},
                    regression15_gap_overlap=evidence["regression15_gap_overlap"],
                    verification=evidence["verification"],
                )
            if report["feature_id"] in ("FWD-FULL-WIDTH-PUBLIC-POOL-LIFETIMES", "PSQ-FULL-WIDTH-REAL-POOL-LIFETIMES", "SQ-FULL-WIDTH-REAL-POOL-LIFETIMES"):
                evidence_path = path.parent / "store-payload-pool-evidence-v1.json"
                evidence = load(evidence_path)
                assert evidence["after_run"] == report["after_run"] and evidence["dut"] == report["dut"]
                assert all(evidence["verification"].values())
                closures[-1]["store_payload_pool_evidence"] = dict(
                    path=str(evidence_path.relative_to(ROOT)), contract=evidence["contract"],
                    target_domains=evidence["target_domains"],
                    original_source_line_coverage={k: v for k, v in evidence["original_source_line_coverage"].items() if k != "sources"},
                    regression15_gap_overlap=evidence["regression15_gap_overlap"], verification=evidence["verification"],
                )
                rerun_path = ROOT / "results/store-payload-failure-retention-01/store-payload-regression-evidence-v1.json"
                rerun = load(rerun_path)
                assert all(rerun["verification"].values()) and rerun["status"]["manifest_tests"] == {"PASS": 268, "FAIL": 64}
                rerun_row = next(row for row in rerun["rows"] if row["dut"] == report["dut"])
                closures[-1]["actual_full_directory_rerun"] = dict(
                    path=str(rerun_path.relative_to(ROOT)), run=rerun["run"], tests=rerun["status"]["manifest_tests"],
                    original_nodes=329, added_passing_nodes=3, original_failures=64,
                    metrics=rerun_row["metrics"], original_source_line_coverage=rerun_row["original_source_line_coverage"],
                    verification=rerun["verification"],
                )
            if report["feature_id"] in ("PSQ-STRICT-REAL-STA-LIFETIMES", "SQ-STRICT-REAL-STA-LIFETIMES", "LSQ-STRICT-REAL-REPLAY-LIFETIMES"):
                evidence_path = path.parent / "store-strict-lifetimes-evidence-v1.json"
                evidence = load(evidence_path)
                assert evidence["after_run"] == report["after_run"] and evidence["dut"] == report["dut"]
                assert all(evidence["verification"].values())
                closures[-1]["strict_lifetimes_evidence"] = dict(
                    path=str(evidence_path.relative_to(ROOT)), contract=evidence["contract"],
                    strict_branch_targets=evidence["strict_branch_targets"],
                    original_source_line_coverage={k: v for k, v in evidence["original_source_line_coverage"].items() if k != "sources"},
                    regression15_gap_overlap=evidence["regression15_gap_overlap"], verification=evidence["verification"],
                )
                rerun_path = ROOT / "results/store-strict-directory-regression-01/store-strict-regression-evidence-v1.json"
                rerun = load(rerun_path)
                assert all(rerun["verification"].values()) and rerun["status"]["manifest_tests"] == {"PASS": 868, "FAIL": 157}
                rerun_row = next(row for row in rerun["rows"] if row["dut"] == report["dut"])
                closures[-1]["actual_full_directory_rerun"] = dict(
                    path=str(rerun_path.relative_to(ROOT)), run=rerun["run"], tests=rerun["status"]["manifest_tests"],
                    original_nodes=1018, added_passing_nodes=7, original_failures=157, metrics=rerun_row["metrics"],
                    original_source_line_coverage=rerun_row["original_source_line_coverage"], verification=rerun["verification"],
                    coverage_monotonicity=rerun["coverage_monotonicity"], open_toggle_loss=rerun_row["open_toggle_loss"],
                    complete_same_build_contributor_scope=False,
                    scope_correction="native-contributor-scope-diagnosis-v1.json",
                )
                contributor_row = next(row for row in contributor["rows"] if row["dut"] == report["dut"])
                closures[-1]["actual_complete_contributor_rerun"] = dict(
                    path=str(contributor_path.relative_to(ROOT)), run=contributor["run"],
                    tests=contributor["status"]["manifest_tests"], original_nodes=1059, added_passing_nodes=7,
                    original_failures=169, metrics=contributor_row["metrics"],
                    original_native_inputs=contributor_row["original_native_inputs"],
                    current_native_inputs=contributor_row["current_native_inputs"],
                    original_source_line_coverage=contributor_row["original_source_line_coverage"],
                    coverage_monotonicity=contributor["coverage_monotonicity"],
                    verification=contributor["verification"], historical_partial_run_retained=True)
            if report["feature_id"].endswith("-EXCLUSIVE-PREFIX-BYTE-WINDOWS"):
                evidence_path = path.parent / "store-prefix-byte-evidence-v1.json"
                evidence = load(evidence_path)
                assert evidence["dut"] == report["dut"] and all(evidence["verification"].values())
                row = next(item for item in prefix_rerun["rows"] if item["dut"] == report["dut"])
                closures[-1]["prefix_byte_evidence"] = dict(path=str(evidence_path.relative_to(ROOT)),
                    contract=evidence["contract"], low_window_vectors=evidence["low_window_vectors"],
                    stored_or_public_vaddr_low=evidence["stored_or_public_vaddr_low"],
                    original_source_line_coverage=evidence["original_source_line_coverage"],
                    regression15_gap_overlap=evidence["regression15_gap_overlap"], verification=evidence["verification"])
                closures[-1]["actual_complete_contributor_rerun"] = dict(path=str(prefix_rerun_path.relative_to(ROOT)),
                    run=prefix_rerun["run"], tests=prefix_rerun["status"]["manifest_tests"], original_nodes=1066,
                    current_nodes=1072, added_passing_nodes=6, original_failures=169, metrics=row["metrics"],
                    original_source_line_coverage=row["original_source_line_coverage"],
                    original_native_inputs=row["original_native_inputs"], current_native_inputs=row["current_native_inputs"],
                    coverage_monotonicity=prefix_rerun["coverage_monotonicity"], verification=prefix_rerun["verification"])
            if report["feature_id"].endswith("-PAIRED-SECOND-PAGE-LIFETIMES"):
                evidence_path = path.parent / "uq-page-pairs-evidence-v1.json"
                evidence = load(evidence_path)
                assert evidence["dut"] == report["dut"] and all(evidence["verification"].values())
                full_row = next(item for item in uq_rerun["rows"] if item["dut"] == report["dut"])
                closures[-1]["uq_page_pairs_evidence"] = dict(path=str(evidence_path.relative_to(ROOT)), contract=evidence["contract"],
                    baseline_tests=evidence["baseline_tests"], after_tests=evidence["after_tests"],
                    target_second_page_paddr_high=evidence["target_second_page_paddr_high"], functional=evidence["functional"],
                    regression15_gap_overlap=evidence["regression15_gap_overlap"],
                    original_source_line_coverage=evidence["original_source_line_coverage"], verification=evidence["verification"])
                closures[-1]["actual_complete_five_build_rerun"] = dict(path=str(uq_rerun_path.relative_to(ROOT)), run=uq_rerun["run"],
                    tests=uq_rerun["status"]["manifest_tests"], original_nodes=1113, current_nodes=1119, added_passing_nodes=6,
                    original_failures=169, metrics=full_row["metrics"], second_page_paddr_high_hit=full_row["second_page_paddr_high_hit"],
                    second_page_paddr_high_total=full_row["second_page_paddr_high_total"],
                    second_page_paddr_high_before_hit=full_row["second_page_paddr_high_before_hit"],
                    original_native_inputs=full_row["original_native_inputs"], current_native_inputs=full_row["current_native_inputs"],
                    original_source_line_coverage=full_row["original_source_line_coverage"],
                    coverage_monotonicity=uq_rerun["coverage_monotonicity"], verification=uq_rerun["verification"])
            if report["feature_id"] in ("VSQ-RELEASE-PHASE-PUBLIC-REUSE", "SQ-RELEASE-PHASE-REAL-REUSE", "LSQ-RELEASE-PHASE-REAL-REUSE"):
                evidence_path = path.parent / "vsq-release-windows-evidence-v1.json"
                evidence = load(evidence_path)
                assert evidence["dut"] == report["dut"] and all(evidence["verification"].values())
                full_row = next(item for item in release_rerun["rows"] if item["dut"] == report["dut"])
                closures[-1]["vsq_release_windows_evidence"] = dict(path=str(evidence_path.relative_to(ROOT)), contract=evidence["contract"],
                    baseline_tests=evidence["baseline_tests"], after_tests=evidence["after_tests"], branch_targets=evidence["branch_targets"],
                    state3_source_proof=evidence["state3_source_proof"], functional=evidence["functional"],
                    regression15_gap_overlap=evidence["regression15_gap_overlap"], original_source_line_coverage=evidence["original_source_line_coverage"],
                    verification=evidence["verification"])
                closures[-1]["actual_complete_six_build_rerun"] = dict(path=str(release_rerun_path.relative_to(ROOT)), run=release_rerun["run"],
                    tests=release_rerun["status"]["manifest_tests"], original_nodes=1162, current_nodes=1171, added_passing_nodes=9,
                    baseline_only_preexisting_vsq_nodes=release_rerun.get("baseline_only_preexisting_vsq_nodes", []), original_failures=171,
                    metrics=full_row["metrics"], original_native_inputs=full_row["original_native_inputs"], current_native_inputs=full_row["current_native_inputs"],
                    original_source_line_coverage=full_row["original_source_line_coverage"], branch_targets=full_row.get("branch_targets", []),
                    coverage_monotonicity=release_rerun["coverage_monotonicity"], verification=release_rerun["verification"])
            if report["feature_id"] == "VSQ-REDIRECT-DEEP-SUFFIX":
                evidence_path = path.parent / "vsq-deep-suffix-evidence-v1.json"
                evidence = load(evidence_path)
                assert evidence["dut"] == report["dut"] and all(evidence["verification"].values())
                full_row = next(item for item in deep_rerun["rows"] if item["dut"] == report["dut"])
                closures[-1]["vsq_deep_suffix_evidence"] = dict(path=str(evidence_path.relative_to(ROOT)), contract=evidence["contract"],
                    baseline_tests=evidence["baseline_tests"], after_tests=evidence["after_tests"],
                    cancel_count_high_points=evidence["cancel_count_high_points"], functional=evidence["functional"],
                    verification=evidence["verification"])
                closures[-1]["actual_complete_six_build_rerun"] = dict(path=str(deep_rerun_path.relative_to(ROOT)), run=deep_rerun["run"],
                    tests=deep_rerun["status"]["manifest_tests"], original_nodes=1171, current_nodes=1172, added_passing_nodes=1,
                    original_failures=171, metrics=full_row["metrics"], original_native_inputs=full_row["original_native_inputs"],
                    current_native_inputs=full_row["current_native_inputs"], original_source_line_coverage=full_row["original_source_line_coverage"],
                    cancel_count_high_points=full_row.get("cancel_count_high_points"), coverage_monotonicity=deep_rerun["coverage_monotonicity"],
                    verification=deep_rerun["verification"])
            if report["feature_id"] == "VSQ-RETIRE-BATCH-WIDTH":
                evidence_path = path.parent / "vsq-retire-batch-evidence-v1.json"
                evidence = load(evidence_path)
                assert evidence["dut"] == report["dut"] and all(evidence["verification"].values())
                full_row = next(item for item in batch_rerun["rows"] if item["dut"] == report["dut"])
                closures[-1]["vsq_retire_batch_evidence"] = dict(path=str(evidence_path.relative_to(ROOT)), contract=evidence["contract"],
                    baseline_tests=evidence["baseline_tests"], after_tests=evidence["after_tests"],
                    retire_req_num_points=evidence["retire_req_num_points"], functional=evidence["functional"],
                    original_source_line_coverage=evidence["original_source_line_coverage"], verification=evidence["verification"])
                closures[-1]["actual_complete_six_build_rerun"] = dict(path=str(batch_rerun_path.relative_to(ROOT)), run=batch_rerun["run"],
                    tests=batch_rerun["status"]["manifest_tests"], original_nodes=1172, current_nodes=1173, added_passing_nodes=1,
                    original_failures=171, metrics=full_row["metrics"], original_native_inputs=full_row["original_native_inputs"],
                    current_native_inputs=full_row["current_native_inputs"], original_source_line_coverage=full_row["original_source_line_coverage"],
                    retire_req_num_points=full_row.get("retire_req_num_points"), coverage_monotonicity=batch_rerun["coverage_monotonicity"],
                    verification=batch_rerun["verification"])
            if report["feature_id"].endswith("-CANCEL-CAPACITY-PUBLIC-REUSE"):
                path_evidence = path.parent / "vsq-cancel-capacity-evidence-v1.json"
                evidence = load(path_evidence)
                assert evidence["dut"] == report["dut"] and all(evidence["verification"].values())
                full_row = next(row for row in cancel["rows"] if row["dut"] == report["dut"])
                closures[-1]["cancel_capacity_evidence"] = dict(path=str(path_evidence.relative_to(ROOT)), contract=evidence["contract"],
                    baseline_tests=evidence["baseline_tests"], after_tests=evidence["after_tests"],
                    cancel_count_targets=evidence["cancel_count_targets"], public_reuse=evidence["public_reuse"],
                    functional=evidence["functional"], verification=evidence["verification"])
                closures[-1]["actual_complete_six_build_rerun"] = dict(path=str(cancel_path.relative_to(ROOT)), run=cancel["run"],
                    tests=cancel["status"]["manifest_tests"],original_nodes=1173,current_nodes=1177,added_passing_nodes=3,
                    original_failures=171,new_required_failures=cancel["required_new_functional_failures"],
                    metrics=full_row["metrics"],original_native_inputs=full_row["original_native_inputs"],current_native_inputs=full_row["current_native_inputs"],
                    original_source_line_coverage=full_row["original_source_line_coverage"],cancel_count_targets=full_row.get("cancel_count_targets"),
                    coverage_monotonicity=cancel["coverage_monotonicity"],verification=cancel["verification"])
            if report["feature_id"].endswith("-RETIRE-KNOWN-WIDTH"):
                path_evidence = path.parent / "vsq-retire-known-width-evidence-v1.json"
                evidence = load(path_evidence)
                assert evidence["dut"] == report["dut"] and all(evidence["verification"].values())
                full_row = next(row for row in known["rows"] if row["dut"] == report["dut"])
                closures[-1]["retire_known_width_evidence"] = dict(path=str(path_evidence.relative_to(ROOT)),contract=evidence["contract"],
                    baseline_tests=evidence["baseline_tests"],after_tests=evidence["after_tests"],retire_count_targets=evidence["retire_count_targets"],
                    public_lifetime=evidence["public_lifetime"],functional=evidence["functional"],verification=evidence["verification"])
                closures[-1]["actual_complete_six_build_rerun"] = dict(path=str(known_path.relative_to(ROOT)),run=known["run"],
                    tests=known["status"]["manifest_tests"],original_nodes=1177,current_nodes=1180,added_passing_nodes=3,original_failures=172,
                    required_new_functional_failures=known["required_new_functional_failures"],metrics=full_row["metrics"],
                    original_native_inputs=full_row["original_native_inputs"],current_native_inputs=full_row["current_native_inputs"],
                    original_source_line_coverage=full_row["original_source_line_coverage"],retire_count_targets=full_row["retire_count_targets"],
                    remaining_count_domain_directions=full_row["remaining_count_domain_directions"],
                    coverage_monotonicity=known["coverage_monotonicity"],verification=known["verification"])
            if report["feature_id"].endswith("-SCALAR-RESERVATION-INTERFACE"):
                evidence_path = path.parent / "sq-scalar-reservation-evidence-v1.json"
                evidence = load(evidence_path)
                assert evidence["dut"] == report["dut"] and all(evidence["verification"].values())
                assert evidence["domain"] == scalar["domain"] and not evidence["normal_full_core_producer_proven"]
                full_row = next(row for row in scalar["rows"] if row["dut"] == report["dut"])
                closures[-1]["domain"] = evidence["domain"]
                closures[-1]["normal_full_core_producer_proven"] = False
                closures[-1]["scalar_reservation_interface_evidence"] = dict(path=str(evidence_path.relative_to(ROOT)),
                    contract=evidence["contract"],source_domain_evidence=evidence["source_domain_evidence"],
                    baseline_tests=evidence["baseline_tests"],after_tests=evidence["after_tests"],cancel_count_targets=evidence["cancel_count_targets"],
                    public_lifetime=evidence["public_lifetime"],functional=evidence["functional"],verification=evidence["verification"])
                closures[-1]["actual_complete_six_build_rerun"] = dict(path=str(scalar_path.relative_to(ROOT)),run=scalar["run"],
                    tests=scalar["status"]["manifest_tests"],original_nodes=1180,current_nodes=1182,added_passing_nodes=2,original_failures=172,
                    new_supplement_domain=scalar["domain"],normal_full_core_producer_proven=False,
                    required_new_functional_failures=scalar["required_new_functional_failures"],metrics=full_row["metrics"],
                    original_native_inputs=full_row["original_native_inputs"],current_native_inputs=full_row["current_native_inputs"],
                    original_source_line_coverage=full_row["original_source_line_coverage"],cancel_count_targets=full_row["cancel_count_targets"],
                    coverage_monotonicity=scalar["coverage_monotonicity"],verification=scalar["verification"])
            if report["feature_id"].endswith("-LOAD-RESPONSE-PAYLOAD"):
                evidence_path = path.parent / "load-response-payload-evidence-v1.json"
                evidence = load(evidence_path)
                assert evidence["dut"] == report["dut"] and all(evidence["verification"].values())
                full_row = next(row for row in response["rows"] if row["dut"] == report["dut"])
                closures[-1]["load_response_payload_evidence"] = dict(path=str(evidence_path.relative_to(ROOT)),
                    contract=evidence["contract"],baseline_tests=evidence["baseline_tests"],after_tests=evidence["after_tests"],
                    response_data_targets=evidence["response_data_targets"],public_lifetime=evidence["public_lifetime"],
                    original_source_line_coverage=evidence["original_source_line_coverage"],functional=evidence["functional"],
                    verification=evidence["verification"],semantic_limit=evidence["limits"])
                closures[-1]["actual_complete_eight_build_rerun"] = dict(path=str(response_path.relative_to(ROOT)),run=response["run"],
                    tests=response["status"]["manifest_tests"],baseline_run=response["baseline_run"],original_nodes=1454,current_nodes=1457,
                    additional_preexisting_load_contributors=272,added_passing_nodes=3,original_failures=192,
                    metrics=full_row["metrics"],original_native_inputs=full_row["original_native_inputs"],current_native_inputs=full_row["current_native_inputs"],
                    original_source_line_coverage=full_row["original_source_line_coverage"],response_data_targets=full_row["response_data_targets"],
                    coverage_monotonicity=response["coverage_monotonicity"],verification=response["verification"],
                    interrupted_run_preserved=response["interrupted_run_preserved"])
            if report["feature_id"].endswith("-RAW-ORIGINAL-OWNERS"):
                evidence_path = path.parent / "load-RAW-owners-evidence-v1.json"
                evidence = load(evidence_path)
                assert evidence["dut"] == report["dut"] and all(evidence["verification"].values())
                full_row = next(row for row in raw["rows"] if row["dut"] == report["dut"])
                closures[-1]["load_RAW_original_owner_evidence"] = dict(path=str(evidence_path.relative_to(ROOT)),
                    contract=evidence["contract"],baseline_tests=evidence["baseline_tests"],after_tests=evidence["after_tests"],
                    targets=evidence["targets"],public_lifetimes=evidence["public_lifetimes"],
                    original_source_line_coverage=evidence["original_source_line_coverage"],
                    verification=evidence["verification"],semantic_limit=evidence["limits"])
                closures[-1]["actual_complete_eight_build_rerun"] = dict(path=str(raw_path.relative_to(ROOT)),run=raw["run"],
                    tests=raw["status"]["manifest_tests"],baseline_run=raw["baseline_run"],original_nodes=1457,current_nodes=1569,
                    added_passing_nodes=112,original_failures=192,metrics=full_row["metrics"],targets=full_row["targets"],
                    original_native_inputs=full_row["original_native_inputs"],current_native_inputs=full_row["current_native_inputs"],
                    original_source_line_coverage=full_row["original_source_line_coverage"],
                    coverage_monotonicity=raw["coverage_monotonicity"],verification=raw["verification"],
                    historical_pending_jump_claim_withdrawn=True,native_full_upstream_ROB_proven=False)
        else:
            assert report["format"] == "lsq-directed-gap-closure-family-v1"
            assert report["verification"]["all_native_builds_same_per_id"]
            assert report["verification"]["all_denominators_unchanged"]
            assert report["verification"]["no_new_missing_points"]
            assert report["verification"]["all_after_runs_passed"]
            closures.append(dict(
                path=str(path.relative_to(ROOT)), family=report["family"], feature_id=report["feature_id"], case_id=report["case_id"],
                before_run=report["before_run"], after_run=report["after_run"], aggregate=report["aggregate"],
                verification=report["verification"],
            ))

    report = dict(
        format="lsq-gap-closure-summary-v1", run=name,
        full_run_point_classification=dict(
            native_duts=38,
            toggle_missing_points=toggle["total_missing_toggle_points"],
            toggle_classification_counts=counter_rows(toggle["rows"], "classification_counts"),
            branch_missing_points=branch["total_missing_branch_points"],
            branch_classification_counts=counter_rows(branch["rows"], "classification_counts"),
            line_remaining=line["remaining_line_points"],
        ),
        branch_initial_boundary_evidence=dict(path="initial-branch-boundary-audit-v1.json",
            initial_process_missing_points=initial["initial_process_missing_points"],
            other_missing_branch_points=initial["other_missing_branch_points"], verification=initial["verification"]),
        vsq_recovery_boundary_evidence=dict(path="vsq-recovery-boundary-audit-v1.json",
            proven_post_reset_state3_points=3, open_release_wait_points=3, verification=recovery_boundary["verification"],
            dynamic_native_gain=0, metric_denominators_unchanged=True),
        directed_supplements=closures,
        open_required_runtime_gates=[],
        latest_complete_contributor_run=dict(path=str(raw_path.relative_to(ROOT)),
            run=raw["run"],tests=raw["status"]["manifest_tests"],native_builds=8,
            baseline_run=raw["baseline_run"],baseline_nodes=1457,current_nodes=1569,
            source_bounded_commit_projection_not_native_upstream_ROB_proof=True,
            coverage_monotonicity=raw["coverage_monotonicity"]),
        required_new_functional_failures=raw["required_new_functional_failures"],
        prior_complete_contributor_runs=[dict(path=str(contributor_path.relative_to(ROOT)), run=contributor["run"], tests=contributor["status"]["manifest_tests"]),
            dict(path=str(prefix_rerun_path.relative_to(ROOT)), run=prefix_rerun["run"], tests=prefix_rerun["status"]["manifest_tests"]),
            dict(path=str(uq_rerun_path.relative_to(ROOT)), run=uq_rerun["run"], tests=uq_rerun["status"]["manifest_tests"]),
            dict(path=str(release_rerun_path.relative_to(ROOT)), run=release_rerun["run"], tests=release_rerun["status"]["manifest_tests"]),
            dict(path=str(deep_rerun_path.relative_to(ROOT)), run=deep_rerun["run"], tests=deep_rerun["status"]["manifest_tests"]),
            dict(path=str(batch_rerun_path.relative_to(ROOT)), run=batch_rerun["run"], tests=batch_rerun["status"]["manifest_tests"]),
            dict(path=str(cancel_path.relative_to(ROOT)), run=cancel["run"], tests=cancel["status"]["manifest_tests"]),
            dict(path=str(known_path.relative_to(ROOT)), run=known["run"], tests=known["status"]["manifest_tests"]),
            dict(path=str(scalar_path.relative_to(ROOT)), run=scalar["run"], tests=scalar["status"]["manifest_tests"]),
            dict(path=str(response_path.relative_to(ROOT)), run=response["run"], tests=response["status"]["manifest_tests"])],
        corrected_RAW_owner_producer_scope=raw["calibration"],
        resolved_runtime_gates=[dict(
            historical_failed_gate=load(ROOT / "results/store-strict-directory-regression-01/store-strict-regression-evidence-v1.json")["coverage_monotonicity"],
            current_gate=contributor["coverage_monotonicity"], corrected_scope=contributor["corrected_scope"],
            evidence=str(contributor_path.relative_to(ROOT)))],
        status=f"line boundary audit is retained; full-run toggle/branch gaps remain classified; {len(closures)} directed reports have passed native before/after checks with their stated semantic limits; remaining reachable gaps and all parent semantic FAILs stay open",
        limits=f"Full-run classification is summary-retained with complete missing-set hashes and compact samples, not a copied point list. Directed supplements use their own fresh result directories and selected tests; improved counts are not merged into the 38-DUT {name} denominators. Raw line points are not LCOV source lines; checkpoint evidence reports both separately. No RTL/Chisel, denominator, skip, xfail or failure masking was used.",
    )
    output = run / "gap-closure-summary-v1.json"
    write_report(output, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
