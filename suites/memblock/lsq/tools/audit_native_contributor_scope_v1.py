#!/usr/bin/env python3
"""Check actual native contributor sets, omitted cases, and a fresh full rerun."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from audit_evidence_io import write_report
from audit_coverage_points_v1 import records, sha256_file, summarize
from audit_expanded_regression_v1 import cases, failure_digest
from audit_gap_closure_v1 import digest_keys, native, point_key, point_sets
from audit_native_case_probe_v1 import audit as audit_cases, journal_streams, stable_run, target_keys, xml_node
from audit_store_strict_lifetimes_v1 import PAIRS, check_witness, source_lines, strict_targets

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "lsq-progress-regression-15"
PARTIAL = "store-strict-directory-regression-01"
OMITTED = "lsq-native-case-omitted-contributors-01"
FULL = "store-strict-contributor-regression-02"
PRIMARY = {
    "forward_module": {"forward_module.summary.json"},
    "physical_store_queue": {"physical_store_queue.summary.json", "psq_full.summary.json"},
    "store_queue": {"store_queue.summary.json"},
    "lsq_wrapper": {"lsq_wrapper.summary.json", "lsq_probe.summary.json"},
}
EXPECTED = {"forward_module": 184, "physical_store_queue": 66, "store_queue": 79, "lsq_wrapper": 730}
COMMAND_PATHS = ["tests/forward", "tests/psq", "tests/store_queue", "tests/lsq_wrapper",
                 "tests/local_reset", "tests/normal_mixed/test_original_seeds.py", "tests/sq_endpoint/test_ldu_joint_phases.py",
                 "tests/sq_endpoint/test_wrapper_raw_boundary.py"]


def load(path):
    return json.loads(path.read_text())


def contributors(name):
    nodes = {dut: {} for dut in PRIMARY}
    lookup = {filename: dut for dut, names in PRIMARY.items() for filename in names}
    for path in (ROOT / "results" / name / "cases").rglob("*.summary.json"):
        if path.name not in lookup:
            continue
        item = load(path)
        dut, node = lookup[path.name], xml_node(item["nodeid"])
        assert node not in nodes[dut], (name, dut, node)
        nodes[dut][node] = dict(summary=str(path.relative_to(ROOT)), records=item["records"],
                               serialized_bytes=item["serialized_bytes"], streamed_SHA256=item["streamed_SHA256"])
    for dut, items in nodes.items():
        if items:
            meta, _ = native(name, dut)
            assert len(items) == meta["artifact"]["input_files"], (name, dut, len(items), meta["artifact"]["input_files"])
    return nodes


def same_summary(left, right):
    return all(left[key] == right[key] for key in ("records", "serialized_bytes", "streamed_SHA256"))


def nodes_digest(items):
    return digest_keys(set((node,) for node in items))


def scope_diagnosis():
    original, partial = contributors(BASELINE), contributors(PARTIAL)
    assert {dut: len(nodes) for dut, nodes in original.items()} == EXPECTED
    assert {dut: len(nodes) for dut, nodes in partial.items()} == dict(
        forward_module=185, physical_store_queue=68, store_queue=81, lsq_wrapper=691)
    omitted_nodes = set(original["lsq_wrapper"]) - set(partial["lsq_wrapper"])
    assert len(omitted_nodes) == 41 and omitted_nodes < set(cases(OMITTED))
    software_only = set(cases(OMITTED)) - omitted_nodes
    assert len(software_only) == 2 and all(node.startswith("tests.normal_mixed.test_source_ledger::") for node in software_only)
    diagnostic = audit_cases(OMITTED)
    assert diagnostic["status"]["manifest_tests"] == {"PASS": 31, "FAIL": 12}
    assert Counter(cases(OMITTED)[node]["outcome"] for node in omitted_nodes) == {"PASS": 29, "FAIL": 12}
    assert diagnostic["observed_target_hit_count"] == diagnostic["target_total"] == 2125
    assert all(diagnostic["verification"].values())
    fresh_omitted = contributors(OMITTED)["lsq_wrapper"]
    assert set(fresh_omitted) == omitted_nodes
    assert all(same_summary(original["lsq_wrapper"][node], item) for node, item in fresh_omitted.items())
    keys, _ = target_keys()
    key_set = set(keys)
    _, before_dat = native(BASELINE, "lsq_wrapper"); _, missing_dat = native(OMITTED, "lsq_wrapper")
    left = {point_key(p): p["hit"] for p in records(before_dat) if point_key(p) in key_set}
    right = {point_key(p): p["hit"] for p in records(missing_dat) if point_key(p) in key_set}
    assert left == right and sum(left.values()) == 15591
    groups = defaultdict(lambda: dict(nodes=0, hits=0, counter_sum=0, outcomes=Counter()))
    for path in (ROOT / "results" / OMITTED / "cases").rglob("native-case-coverage-summary.json"):
        item = load(path); node = xml_node(item["nodeid"]); export = item["native_exports"][0]
        group = groups[node.split("::")[0]]
        group["nodes"] += 1
        group["hits"] |= int(export["target_hit_bitmap_hex"], 16)
        group["counter_sum"] += export["target_counter_sum"]
        group["outcomes"][cases(OMITTED)[node]["outcome"]] += 1
    rows = [dict(test_module=module, nodes=value["nodes"], outcomes=dict(value["outcomes"]),
                 target_hit_count=value["hits"].bit_count(), target_counter_sum=value["counter_sum"],
                 note="Point counts overlap across modules; do not add hit counts as a unique-point total.")
            for module, value in sorted(groups.items())]
    report = dict(format="lsq-native-contributor-scope-diagnosis-v1", baseline=BASELINE, partial_run=PARTIAL,
        diagnostic_run=OMITTED, native_build_id=diagnostic["native_build_id"],
        baseline_native_wrapper_inputs=730, partial_native_wrapper_inputs=691,
        baseline_main_wrapper_directory_nodes=689, added_main_wrapper_nodes=2,
        omitted_original_contributor_nodes=41, omitted_node_set_SHA256=nodes_digest(omitted_nodes),
        diagnostic_total_nodes=43, diagnostic_tests={"PASS": 31, "FAIL": 12},
        diagnostic_native_contributor_tests={"PASS": 29, "FAIL": 12},
        additional_python_only_nodes=sorted(software_only),
        omitted_nodes=sorted(omitted_nodes), module_attribution=rows,
        observed_original_loss_points=2125, original_loss_point_set_SHA256=digest_keys(set(keys)),
        original_loss_counter_sum=15591, rerun_loss_counter_sum=15591,
        diagnostic_evidence=f"results/{OMITTED}/native-case-probe-audit-v1.json",
        historical_failed_gate=f"results/{PARTIAL}/store-strict-regression-evidence-v1.json",
        root_cause="OMITTED_SAME_NATIVE_BUILD_CONTRIBUTORS_IN_DIRECTORY_SELECTION",
        verification=dict(actual_native_input_counts_match_primary_journal_contributors=True,
            every_omitted_node_reexecuted_with_original_outcome_and_failure_detail=True,
            all_2125_original_lost_point_counts_exactly_reproduced=True,
            original_public_check_actor_streams_equal=True, per_case_to_merged_counter_conservation=True,
            historical_partial_run_failure_not_rewritten=True),
        limits="The 1025-node partial run remains a failed comparison against the complete build scope. This diagnoses that failure, not a coverage waiver. A fresh complete-contributor execution is still required; an OR of old and diagnostic dat is not accepted, and no original dat or feature classification is changed.")
    output = ROOT / "results" / BASELINE / "native-contributor-scope-diagnosis-v1.json"
    write_report(output, report)
    return report


def audit_full():
    diagnosis = scope_diagnosis()
    status, source = stable_run(FULL)
    assert status["manifest_tests"] == {"PASS": 897, "FAIL": 169} and status["pytest_exitstatus"] == 1
    original, fresh = contributors(BASELINE), contributors(FULL)
    before_cases, after_cases = cases(BASELINE), cases(FULL)
    original_nodes = set().union(*(set(nodes) for nodes in original.values()))
    fresh_nodes = set().union(*(set(nodes) for nodes in fresh.values()))
    assert len(original_nodes) == 1059 and len(fresh_nodes) == 1066
    assert fresh_nodes == set(after_cases) and original_nodes <= fresh_nodes
    assert all(before_cases[node] == after_cases[node] for node in original_nodes)
    original_cases = {node: before_cases[node] for node in original_nodes}
    assert failure_digest(original_cases) == failure_digest(after_cases)
    added = fresh_nodes - original_nodes
    assert len(added) == 7 and added == set(cases(PARTIAL)) - set(before_cases)
    assert all(after_cases[node]["outcome"] == "PASS" for node in added)
    command = load(ROOT / "results" / FULL / "command.json")["command"]
    assert command[command.index("--lsq-trace-max-mb") + 2:] == COMMAND_PATHS + ["--tb=short"]
    manifest = load(ROOT / "results" / FULL / "execution/manifest.json")
    assert len([a for a in manifest["artifacts"] if a["kind"] == "native"]) == 4
    rows = []
    for dut in PRIMARY:
        before, old_dat = native(BASELINE, dut); after, new_dat = native(FULL, dut)
        assert before["artifact"]["build"] == after["artifact"]["build"]
        for filename, digest in after["artifact"]["build"]["files"].items():
            assert sha256_file(Path(filename)) == digest
        assert set(original[dut]) <= set(fresh[dut])
        assert all(same_summary(item, fresh[dut][node]) for node, item in original[dut].items())
        summary = summarize(new_dat, after["artifact"]["build"], after["artifact"])
        assert summary["raw_parser_matches_analyzer"] and summary["coverage_artifact_matches_dat"]
        a, b, metrics = point_sets(old_dat), point_sets(new_dat), {}
        for kind in ("line", "toggle", "branch"):
            assert a[kind]["all"] == b[kind]["all"] and a[kind]["hit"] <= b[kind]["hit"]
            gained = b[kind]["hit"] - a[kind]["hit"]
            metrics[kind] = dict(before_hit=len(a[kind]["hit"]), after_hit=len(b[kind]["hit"]), total=len(b[kind]["all"]),
                newly_hit=len(gained), newly_hit_SHA256=digest_keys(gained), newly_missing=0,
                still_missing=len(b[kind]["missing"]), still_missing_SHA256=digest_keys(b[kind]["missing"]))
        old_lines, new_lines = source_lines(before, old_dat, dut), source_lines(after, new_dat, dut)
        assert old_lines[0] == new_lines[0] and old_lines[1] <= new_lines[1]
        if dut != "forward_module":
            paths = [p for p in (ROOT / "results" / FULL / "cases").rglob("store-strict-lifetimes-witness.json") if load(p)["dut"] == dut]
            assert len(paths) == 1
            check_witness(load(paths[0]), dut)
            directed = next(pair[2] for pair in PAIRS if pair[0] == dut)
            assert load(paths[0]) == load(ROOT / "results" / directed / "store-strict-lifetimes-evidence-v1.json")["public_witness"]
            assert all(p["hit"] > 0 for p in strict_targets(new_dat).values())
        rows.append(dict(dut=dut, native_build_id=after["artifact"]["build"]["build_id"],
            original_native_inputs=len(original[dut]), current_native_inputs=len(fresh[dut]),
            all_original_contributors_retained=True, original_contributor_set_SHA256=nodes_digest(original[dut]),
            current_contributor_set_SHA256=nodes_digest(fresh[dut]),
            before_coverage_dat_SHA256=sha256_file(old_dat), after_coverage_dat_SHA256=sha256_file(new_dat), metrics=metrics,
            original_source_line_coverage=dict(before_hit=len(old_lines[1]), after_hit=len(new_lines[1]), total=len(new_lines[0]),
                newly_hit=len(new_lines[1] - old_lines[1]), newly_missing=0)))
    old_streams, new_streams = journal_streams(BASELINE), journal_streams(FULL)
    assert len(old_streams) == 2190 and old_streams.keys() <= new_streams.keys()
    assert all(new_streams[key] == value for key, value in old_streams.items())
    keys, _ = target_keys()
    key_set = set(keys)
    _, dat = native(FULL, "lsq_wrapper")
    restored = {point_key(p) for p in records(dat) if p["hit"] > 0 and point_key(p) in key_set}
    assert restored == set(keys)
    gate = dict(name="all_old_native_hits_retained", passed=True, status="PASS", failed_duts=[],
                newly_missing_toggle_points=0, required=True, waived=False)
    report = dict(format="lsq-store-strict-contributor-regression-v1", run=FULL, baseline=BASELINE, status=status,
        original_nodes=1059, current_nodes=1066, original_failures=169, added_passing_nodes=7, added_nodes=sorted(added),
        failure_SHA256=failure_digest(after_cases), source_aggregate=source["aggregate_SHA256"], rows=rows,
        wrapper_original_contributors=730, wrapper_current_contributors=732,
        wrapper_original_public_journal_summaries_equal=2190, coverage_monotonicity=gate,
        corrected_scope=dict(diagnosis="native-contributor-scope-diagnosis-v1.json", root_cause=diagnosis["root_cause"],
            missing_original_nodes_reexecuted=41, all_original_lost_points_restored=2125,
            historical_failed_partial_run=PARTIAL, historical_failed_gate_kept=True, actual_single_fresh_run_not_coverage_OR=True),
        verification=dict(all_original_same_build_contributors_retained=True,
            all_original_normalized_outcomes_and_failure_details_equal=True, seven_new_passes_do_not_cancel_169_old_failures=True,
            actual_single_fresh_complete_contributor_execution=True, source_launch_end_equal=True,
            native_artifact_and_pinned_RTL_hashes=True, independent_parser_matches_locked_analyzer=True,
            same_native_builds_and_three_point_universes=True, no_old_hit_lost=True,
            original_primary_journal_streams_equal=True, all_original_wrapper_check_actor_streams_equal=True,
            three_strict_public_witnesses_equal_directed_cases=True, no_cycle_JSON_or_waveforms=True),
        limits="This is the complete original contributor scope for four native builds, not all38 builds or whole-LSQ acceptance. The failed1025-node run remains unchanged; this fresh1066-node result resolves its scope omission without data merging or waiving any old point. Regression15 counts/dat/gaps and all169 old failures remain explicit; all other required feature/coverage work stays open.")
    write_report(ROOT / "results" / FULL / "store-strict-contributor-regression-evidence-v1.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnosis-only", action="store_true")
    args = parser.parse_args()
    result = scope_diagnosis() if args.diagnosis_only else audit_full()
    print(json.dumps({k: result[k] for k in result if k not in ("omitted_nodes", "rows")}, indent=2, ensure_ascii=False))
