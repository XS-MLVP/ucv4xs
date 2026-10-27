#!/usr/bin/env python3
"""Audit release/walk timing witnesses and a complete six-build execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_checkpoint_pool_v1 import validate_run
from audit_coverage_points_v1 import records, sha256_file, summarize
from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases, failure_digest
from audit_failure_preservation_v1 import RELOCATED_FAILURE_NODES, normalize_known_failure_source_lines, relocated_failure_source_evidence
from audit_gap_closure_v1 import audit as audit_delta, digest_keys, native, point_sets
from audit_native_case_probe_v1 import journal_streams, stable_run, xml_node
from audit_native_contributor_scope_v1 import COMMAND_PATHS, contributors, same_summary
from audit_store_strict_lifetimes_v1 import source_lines
from audit_uq_page_pairs_v1 import functional_counts, node_summaries
from audit_vsq_recovery_boundaries_v1 import SOURCES, source_proof

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = "uq-page-contributor-regression-01"
FULL = "vsq-release-contributor-regression-01"
DEEP_FULL = "vsq-deep-suffix-contributor-regression-01"
DEEP_BEFORE = "vsq-deep-suffix-baseline-02"
DEEP_AFTER = "vsq-deep-suffix-after-02"
BATCH_FULL = "vsq-retire-batch-contributor-regression-01"
BATCH_BEFORE = "vsq-retire-batch-baseline-03"
BATCH_AFTER = "vsq-retire-batch-after-03"
FULL_PATHS = COMMAND_PATHS + ["tests/unalign/test_basic.py", "tests/unalign/test_extended.py",
                            "tests/unalign/test_page_pairs.py", "tests/vsq"]
PAIRS = (
    ("virtual_store_queue", "vsq-release-windows-baseline-01", "vsq-release-windows-after-01", "VSQ-WALK.prefix_windows", "VSQ-RELEASE-PHASE-PUBLIC-REUSE"),
    ("store_queue", "sq-release-windows-baseline-01", "sq-release-windows-after-01", "SQ-RECOVER.prefix_windows", "SQ-RELEASE-PHASE-REAL-REUSE"),
    ("lsq_wrapper", "lsq-release-windows-baseline-01", "lsq-release-windows-after-01", "LSQ-RECOVER.retired_store", "LSQ-RELEASE-PHASE-REAL-REUSE"),
)
WINDOWS = ((0, 1), (62, 8), (126, 9), (190, 59))


def load(path):
    return json.loads(path.read_text())


def branch_targets(dat, dut):
    points = [p for p in records(dat) if p["t"] == "branch" and p["f"] == str(ROOT / SOURCES[dut])
              and int(p["l"]) in (15850, 15853)]
    assert {(int(p["l"]), p["o"]) for p in points} == {(line, arm) for line in (15850, 15853) for arm in ("if", "else")}
    return [dict(source=SOURCES[dut], source_line=int(p["l"]), arm=p["o"], hierarchy=p["h"], count=p["hit"],
                 boundary=("post_reset_unreachable_state3" if int(p["l"]) == 15853 else "release_wait_not_proven_unreachable") if p["o"] == "else" else "actual_dynamic_branch")
            for p in sorted(points, key=lambda p: (int(p["l"]), p["o"]))]


def witness(path, dut):
    item = load(path)
    assert item["format"] == "lsq-vsq-release-walk-witness-v1" and item["dut"] == dut
    delay = item["redirect_extra_idle"]
    assert delay in range(3) and len(item["public_lifetimes_SHA256"]) == 64 and len(item["profiles"]) == 4
    cancelled, replacements = set(), set()
    for profile, ((base, prefix), part) in enumerate(zip(WINDOWS, item["profiles"])):
        assert part["profile"] == profile and part["base"] == base and part["retired_prefix"] == prefix
        assert part["old_store_uids"] == prefix + 5
        assert part["fillers_completed"] == base - (sum(WINDOWS[profile - 1]) + 5 if profile else 0)
        cut = (base + prefix + 2) % 256
        assert part["actual_sq_cut"] == cut
        assert len(part["cancelled_store_uids"]) == len(set(part["cancelled_store_uids"])) == 3
        assert len(part["replacement_store_uids"]) == len(set(part["replacement_store_uids"])) == 3
        assert set(part["cancelled_store_uids"]).isdisjoint(part["replacement_store_uids"])
        cancelled.update(part["cancelled_store_uids"]); replacements.update(part["replacement_store_uids"])
        assert part["retained_store_completions"] == prefix + 2 and part["new_store_completions"] == 3
        recovery = part["recovery"]
        assert recovery["actual_sq_responses"] == [cut] and recovery["cycles"] > recovery["sq_stall_cycles"] > 0
        assert len(recovery["public_recovery_SHA256"]) == 64
        if dut == "lsq_wrapper":
            assert recovery["actual_lq_responses"] == [2 * profile + 1] and recovery["lq_stall_cycles"] > 0
            assert part["query_lane"] == delay and part["original_Load_completed"] < part["reused_Load_completed"]
        else:
            assert not recovery["actual_lq_responses"] and recovery["lq_stall_cycles"] == 0
    assert len(cancelled) == len(replacements) == 12 and cancelled.isdisjoint(replacements)
    if dut == "virtual_store_queue":
        assert item["normal_virtual_completions"] == 254 and item["cancelled_virtual_uids"] == 12
    else:
        assert item["normal_store_completions"] == 254 and item["cancelled_store_uids"] == 12
        if dut == "lsq_wrapper":
            assert item["original_Load_completions"] == item["reused_Load_completions"] == item["cancelled_Load_uids"] == 4
            assert item["actual_Sbuffer_fragments"] == 254
    return item


def line_delta(old, new):
    assert old[0] == new[0] and old[1] <= new[1]
    return dict(before_hit=len(old[1]), after_hit=len(new[1]), total=len(new[0]), newly_hit=len(new[1] - old[1]), newly_missing=0)


def leaf_semantics(run, test_module, scenario, expected_uids, normal_uids):
    matches = []
    for path in (ROOT / "results" / run / "cases").rglob("vsq_semantics.json"):
        data = load(path)
        if data["nodeid"].startswith(f"tests/vsq/{test_module}.py::"):
            matches.append((path, data))
    assert len(matches) == 1
    path, data = matches[0]
    selected = [event for event in data["events"] if event["scenario"] == scenario]
    assert len(selected) == 2 and not selected[0]["checked"] and selected[1]["checked"]
    assert selected[0]["uids"] == selected[1]["uids"] == expected_uids and selected[0]["tick"] < selected[1]["tick"]
    completed = {uid for event in data["events"] if event["scenario"].startswith("VSQ-ADMIT.") and event["checked"] for uid in event["uids"]}
    assert completed == set(normal_uids)
    return dict(path=str(path.relative_to(ROOT)), SHA256=sha256_file(path), nodeid=data["nodeid"],
                scenario_events=selected, checked_normal_uids=sorted(completed))


def validate_same_leaf_full_semantics(before_run, after_run, test_module, scenario, expected_uids, normal_uids):
    before = leaf_semantics(before_run, test_module, scenario, expected_uids, normal_uids)
    after = leaf_semantics(after_run, test_module, scenario, expected_uids, normal_uids)
    assert before["SHA256"] == after["SHA256"] and before["nodeid"] == after["nodeid"]
    primary_old = node_summaries(before_run, "virtual_store_queue.summary.json")
    primary_new = node_summaries(after_run, "virtual_store_queue.summary.json")
    assert primary_old[before["nodeid"]] == primary_new[after["nodeid"]]
    return dict(directed_semantics=before, full_semantics=after, new_node_public_primary_equal=True)


def calibration_history():
    deep_initial = functional_counts("vsq-deep-suffix-after-01", "virtual_store_queue", "VSQ-REDIRECT.deep_suffix")
    assert deep_initial["reached"]["count"] > 0 and deep_initial["checked"]["count"] == 0
    batch_failed = cases("vsq-retire-batch-after-01")
    failed = {node: value for node, value in batch_failed.items() if value["outcome"] == "FAIL"}
    assert len(batch_failed) == 4 and len(failed) == 1
    assert all("116 == 32" in value["detail"] for value in failed.values())
    _, partial_dat = native("vsq-retire-batch-after-02", "virtual_store_queue")
    assert [point["hit"] for point in retire_batch_points(partial_dat)] == [1, 0]
    return dict(deep_first_after=dict(run="vsq-deep-suffix-after-01", functional=deep_initial,
                    used_as_final_evidence=False, reason="Functional bin was incorrectly attached to cancelled UIDs; completed-new-UID association corrected without changing DUT/model/checks."),
                batch_checker_failure=dict(run="vsq-retire-batch-after-01", tests={"PASS": 3, "FAIL": 1},
                    failure_SHA256=failure_digest(batch_failed), failure_nodes=sorted(failed),
                    junit_SHA256=sha256_file(ROOT / "results/vsq-retire-batch-after-01/pytest.xml"),
                    reason="Wrong dimension in test precondition: physical end minus virtual uop position was summed. Corrected to eight flows4 and final end32, keeping functional retired-tail assertions."),
                batch_first_passing=dict(run="vsq-retire-batch-after-02", used_as_two_direction_closure=False,
                    observed_target_hits=[1, 0], reason="Register retains the32 batch; a legal subsequent one-flow retirement is needed for the reverse transition, not reset or a forged state."))


def deep_cancel_points(dat):
    points = [p for p in records(dat) if p["t"] == "toggle" and p["f"] == str(ROOT / SOURCES["virtual_store_queue"])
              and p["l"] == "4597" and p["o"] in ("cancelCount[3]:0->1", "cancelCount[3]:1->0")]
    assert len(points) == 2
    return sorted((dict(source=SOURCES["virtual_store_queue"], source_line=4597, point=p["o"], hierarchy=p["h"], hit=p["hit"]) for p in points), key=lambda p: p["point"])


def audit_deep_directed():
    before, after, dut = DEEP_BEFORE, DEEP_AFTER, "virtual_store_queue"
    old_run, new_run = validate_run(before, dut), validate_run(after, dut)
    assert old_run["source"] == new_run["source"]
    old_cases, new_cases = cases(before), cases(after)
    assert len(old_cases) == 3 and len(new_cases) == 4
    assert set(old_cases) < set(new_cases) and all(new_cases[node] == value for node, value in old_cases.items())
    added = set(new_cases) - set(old_cases)
    assert len(added) == 1 and next(iter(added)).startswith("tests.vsq.test_deep_suffix::") and new_cases[next(iter(added))]["outcome"] == "PASS"
    closure = audit_delta(before, after, dut, "VSQ-REDIRECT-DEEP-SUFFIX",
                          "tests/vsq/test_deep_suffix.py::test_redirect_cancels_eight_real_younger_uids_and_reuses_exact_suffix")
    assert all(closure["verification"].values())
    old_meta, old_dat = native(before, dut); new_meta, new_dat = native(after, dut)
    assert old_meta["artifact"]["build"] == new_meta["artifact"]["build"]
    old_points, new_points = deep_cancel_points(old_dat), deep_cancel_points(new_dat)
    assert [p["hit"] for p in old_points] == [0, 0] and [p["hit"] for p in new_points] == [1, 1]
    old_sets, new_sets = point_sets(old_dat), point_sets(new_dat)
    for kind in old_sets:
        assert old_sets[kind]["all"] == new_sets[kind]["all"] and old_sets[kind]["hit"] <= new_sets[kind]["hit"]
    functions = {run: functional_counts(run, dut, "VSQ-REDIRECT.deep_suffix") for run in (before, after)}
    assert functions[before]["reached"]["count"] == functions[before]["checked"]["count"] == 0
    assert functions[after]["reached"]["count"] > 0 and functions[after]["checked"]["count"] > 0
    report = dict(format="lsq-vsq-deep-suffix-evidence-v1", dut=dut, before_run=before, after_run=after,
        feature_id="VSQ-REDIRECT-DEEP-SUFFIX", contract="docs/contracts/vsq-release-walk.md",
        baseline_tests=len(old_cases), after_tests=len(new_cases), added_nodes=sorted(added),
        native_build_id=closure["native_build_id"], raw_nonwrapper_metrics=closure["metrics"],
        source_aggregate=old_run["source"]["aggregate_SHA256"],
        cancel_count_high_points=dict(before=old_points, after=new_points), functional=functions,
        semantic_evidence=leaf_semantics(after, "test_deep_suffix", "VSQ-REDIRECT.deep_suffix", [11], [1, 2, 11]),
        original_source_line_coverage=line_delta(source_lines(old_meta, old_dat, dut), source_lines(new_meta, new_dat, dut)),
        verification=dict(actual_native_dut_and_independent_model=True, same_build_and_point_universes=True,
            no_old_hit_lost=True, both_cancelCount_bit_directions_newly_hit=True,
            eight_real_cancelled_uids_and_exact_public_tail_checked=True, new_uid_reuse_and_retirement_checked=True,
            source_aggregates_and_artifacts_and_locked_analyzer_checked=True, semantic_completion_events_checked=True,
            after_functional_run_passed=True),
        limits="Leaf VSQ-only supplement: it proves legal cancelCount high-bit width and public tail/reuse, not parent physical Store bytes. It does not claim the separate15850 release-wait else, state3 dynamic coverage, or full recovery acceptance.")
    write_report(ROOT / "results" / after / "vsq-deep-suffix-evidence-v1.json", report)
    return report


def audit_deep_full():
    status, source = stable_run(DEEP_FULL)
    assert status["total_cases"] == 1172 and status["manifest_tests"] == {"PASS": 1001, "FAIL": 171} and status["pytest_exitstatus"] == 1
    old, current = cases(FULL), cases(DEEP_FULL)
    assert len(old) == 1171 and len(current) == 1172 and set(old) < set(current)
    assert all(current[node] == value for node, value in old.items())
    added = set(current) - set(old)
    assert len(added) == 1 and next(iter(added)).startswith("tests.vsq.test_deep_suffix::") and current[next(iter(added))]["outcome"] == "PASS"
    assert failure_digest(old) == failure_digest(current)
    command = load(ROOT / "results" / DEEP_FULL / "command.json")["command"]
    assert command[command.index("--lsq-trace-max-mb") + 2:] == FULL_PATHS + ["--tb=short"]
    manifest = load(ROOT / "results" / DEEP_FULL / "execution/manifest.json")
    assert len([a for a in manifest["artifacts"] if a["kind"] == "native"]) == 6
    old_primary, new_primary = contributors(FULL), contributors(DEEP_FULL)
    assert old_primary.keys() == new_primary.keys()
    for dut in old_primary:
        assert set(old_primary[dut]) == set(new_primary[dut])
        assert all(same_summary(value, new_primary[dut][node]) for node, value in old_primary[dut].items())
    old_vsq = node_summaries(FULL, "virtual_store_queue.summary.json")
    new_vsq = node_summaries(DEEP_FULL, "virtual_store_queue.summary.json")
    assert len(old_vsq) == 46 and len(new_vsq) == 47 and old_vsq.keys() <= new_vsq.keys()
    assert all(new_vsq[node] == value for node, value in old_vsq.items())
    old_uq, new_uq = node_summaries(FULL, "unalign_queue.summary.json"), node_summaries(DEEP_FULL, "unalign_queue.summary.json")
    assert old_uq == new_uq and len(old_uq) == 42
    scope = set().union(*(set(items) for items in new_primary.values())) | {xml_node(node) for node in new_vsq} | {xml_node(node) for node in new_uq}
    assert scope == set(current)
    old_streams, new_streams = journal_streams(FULL), journal_streams(DEEP_FULL)
    assert old_streams.keys() <= new_streams.keys() and all(new_streams[key] == value for key, value in old_streams.items())
    rows = []
    for dut in ("forward_module", "physical_store_queue", "store_queue", "lsq_wrapper", "unalign_queue", "virtual_store_queue"):
        old_meta, old_dat = native(FULL, dut); new_meta, new_dat = native(DEEP_FULL, dut)
        expected_inputs = len(new_vsq) if dut == "virtual_store_queue" else len(new_uq) if dut == "unalign_queue" else len(new_primary[dut])
        assert new_meta["artifact"]["input_files"] == expected_inputs
        assert old_meta["artifact"]["build"] == new_meta["artifact"]["build"]
        for filename, digest in new_meta["artifact"]["build"]["files"].items():
            assert sha256_file(Path(filename)) == digest
        analyzed = summarize(new_dat, new_meta["artifact"]["build"], new_meta["artifact"])
        assert analyzed["raw_parser_matches_analyzer"] and analyzed["coverage_artifact_matches_dat"]
        old_sets, new_sets = point_sets(old_dat), point_sets(new_dat)
        metrics = {}
        for kind in old_sets:
            assert old_sets[kind]["all"] == new_sets[kind]["all"] and old_sets[kind]["hit"] <= new_sets[kind]["hit"]
            gained = new_sets[kind]["hit"] - old_sets[kind]["hit"]
            metrics[kind] = dict(before_hit=len(old_sets[kind]["hit"]), after_hit=len(new_sets[kind]["hit"]), total=len(new_sets[kind]["all"]),
                                 newly_hit=len(gained), newly_hit_SHA256=digest_keys(gained), newly_missing=0,
                                 still_missing=len(new_sets[kind]["missing"]))
        row = dict(dut=dut, old_run=FULL, native_build_id=new_meta["artifact"]["build"]["build_id"],
                   original_native_inputs=old_meta["artifact"]["input_files"], current_native_inputs=new_meta["artifact"]["input_files"],
                   before_coverage_dat_SHA256=sha256_file(old_dat), after_coverage_dat_SHA256=sha256_file(new_dat), metrics=metrics,
                   original_source_line_coverage=line_delta(source_lines(old_meta, old_dat, dut), source_lines(new_meta, new_dat, dut)))
        if dut == "virtual_store_queue":
            old_points, new_points = deep_cancel_points(old_dat), deep_cancel_points(new_dat)
            assert [p["hit"] for p in old_points] == [0, 0] and [p["hit"] for p in new_points] == [1, 1]
            row["cancel_count_high_points"] = dict(before=old_points, after=new_points)
        else:
            assert sha256_file(old_dat) == sha256_file(new_dat), (dut, "unchanged contributor raw dat differs")
        rows.append(row)
    report = dict(format="lsq-vsq-deep-suffix-contributor-regression-v1", run=DEEP_FULL,
        baseline_run=FULL, status=status, source_aggregate=source["aggregate_SHA256"], original_nodes=1171, current_nodes=1172,
        added_passing_nodes=1, added_nodes=sorted(added), original_failures=171, failure_SHA256=failure_digest(current),
        manifest_SHA256=sha256_file(ROOT / "results" / DEEP_FULL / "execution/manifest.json"), rows=rows,
        original_vsq_contributors=46, current_vsq_contributors=47, original_wrapper_public_check_actor_summaries_equal=len(old_streams),
        directed_full_semantics=validate_same_leaf_full_semantics(DEEP_AFTER, DEEP_FULL, "test_deep_suffix", "VSQ-REDIRECT.deep_suffix", [11], [1, 2, 11]),
        coverage_monotonicity=dict(name="all_old_native_hits_retained", passed=True, status="PASS", failed_duts=[], newly_missing_toggle_points=0, required=True, waived=False),
        verification=dict(actual_single_fresh_six_build_execution=True, original_1171_outcomes_and_failure_details_equal=True,
            one_new_deep_suffix_node_pass=True, no_old_hit_lost=True, all_original_vsq_streams_equal=True,
            wrapper_public_check_actor_streams_equal=True, cancelCount_high_bit_directions_hit_in_full_vsq_build=True,
            all_native_input_counts_match_actual_contributors=True, new_node_full_public_and_semantics_equal_directed=True,
            locked_analyzer_and_artifact_hashes_checked=True, source_launch_end_aggregates_equal=True,
            no_per_cycle_JSON_or_waveforms=True),
        limits="One legal leaf VSQ deep-suffix supplement; parent semantic domains and the separate release-wait/state3 boundaries remain as previously reported. Unified regression15 and prior six-build reports are immutable.")
    write_report(ROOT / "results" / DEEP_FULL / "vsq-deep-suffix-contributor-evidence-v1.json", report)
    return report


def retire_batch_points(dat):
    points = [p for p in records(dat) if p["t"] == "toggle" and p["f"] == str(ROOT / SOURCES["virtual_store_queue"])
              and p["l"] == "5397" and p["o"] in ("retireReqNumReg[5]:0->1", "retireReqNumReg[5]:1->0")]
    assert len(points) == 2
    return sorted((dict(source=SOURCES["virtual_store_queue"], source_line=5397, point=p["o"], hierarchy=p["h"], hit=p["hit"]) for p in points), key=lambda p: p["point"])


def audit_batch_directed():
    before, after, dut = BATCH_BEFORE, BATCH_AFTER, "virtual_store_queue"
    old_run, new_run = validate_run(before, dut), validate_run(after, dut)
    assert old_run["source"] == new_run["source"]
    old_cases, new_cases = cases(before), cases(after)
    assert len(old_cases) == 3 and len(new_cases) == 4
    assert set(old_cases) < set(new_cases) and all(new_cases[node] == value for node, value in old_cases.items())
    added = set(new_cases) - set(old_cases)
    assert len(added) == 1 and next(iter(added)).startswith("tests.vsq.test_retire_batch_width::") and new_cases[next(iter(added))]["outcome"] == "PASS"
    closure = audit_delta(before, after, dut, "VSQ-RETIRE-BATCH-WIDTH",
                          "tests/vsq/test_retire_batch_width.py::test_eight_four_flow_uops_retire_as_public_physical_batch_of_32")
    assert all(closure["verification"].values())
    old_meta, old_dat = native(before, dut); new_meta, new_dat = native(after, dut)
    assert old_meta["artifact"]["build"] == new_meta["artifact"]["build"]
    old_points, new_points = retire_batch_points(old_dat), retire_batch_points(new_dat)
    assert [p["hit"] for p in old_points] == [0, 0] and [p["hit"] for p in new_points] == [1, 1]
    old_sets, new_sets = point_sets(old_dat), point_sets(new_dat)
    for kind in old_sets:
        assert old_sets[kind]["all"] == new_sets[kind]["all"] and old_sets[kind]["hit"] <= new_sets[kind]["hit"]
    functions = {run: functional_counts(run, dut, "VSQ-RETIRE.batch_width") for run in (before, after)}
    assert functions[before]["reached"]["count"] == functions[before]["checked"]["count"] == 0
    assert functions[after]["reached"]["count"] > 0 and functions[after]["checked"]["count"] > 0
    report = dict(format="lsq-vsq-retire-batch-evidence-v1", dut=dut, before_run=before, after_run=after,
        feature_id="VSQ-RETIRE-BATCH-WIDTH", contract="docs/contracts/vsq-release-walk.md",
        baseline_tests=len(old_cases), after_tests=len(new_cases), added_nodes=sorted(added), native_build_id=closure["native_build_id"],
        source_aggregate=old_run["source"]["aggregate_SHA256"],
        raw_nonwrapper_metrics=closure["metrics"], retire_req_num_points=dict(before=old_points, after=new_points), functional=functions,
        semantic_evidence=leaf_semantics(after, "test_retire_batch_width", "VSQ-RETIRE.batch_width", list(range(1, 9)), list(range(1, 10))),
        original_source_line_coverage=line_delta(source_lines(old_meta, old_dat, dut), source_lines(new_meta, new_dat, dut)),
        calibration_history=calibration_history(),
        verification=dict(actual_native_dut_and_independent_model=True, same_build_and_point_universes=True, no_old_hit_lost=True,
            both_retireReqNumReg_bit_directions_newly_hit=True, eight_real_four_flow_uops_and_public_retired_tail_checked=True,
            source_aggregates_and_artifacts_and_locked_analyzer_checked=True, semantic_completion_events_checked=True,
            after_functional_run_passed=True),
        limits="Leaf VSQ-only supplement for legal retirement batch width; no parent physical Store claim, no internal register read, and no closure of release-wait/state3 or remaining recovery domains.")
    write_report(ROOT / "results" / after / "vsq-retire-batch-evidence-v1.json", report)
    return report


def audit_batch_full():
    status, source = stable_run(BATCH_FULL)
    assert status["total_cases"] == 1173 and status["manifest_tests"] == {"PASS": 1002, "FAIL": 171} and status["pytest_exitstatus"] == 1
    old, current = cases(DEEP_FULL), cases(BATCH_FULL)
    assert len(old) == 1172 and len(current) == 1173 and set(old) < set(current)
    assert all(current[node] == value for node, value in old.items())
    added = set(current) - set(old)
    assert len(added) == 1 and next(iter(added)).startswith("tests.vsq.test_retire_batch_width::") and current[next(iter(added))]["outcome"] == "PASS"
    assert failure_digest(old) == failure_digest(current)
    command = load(ROOT / "results" / BATCH_FULL / "command.json")["command"]
    assert command[command.index("--lsq-trace-max-mb") + 2:] == FULL_PATHS + ["--tb=short"]
    manifest = load(ROOT / "results" / BATCH_FULL / "execution/manifest.json")
    assert len([a for a in manifest["artifacts"] if a["kind"] == "native"]) == 6
    old_primary, new_primary = contributors(DEEP_FULL), contributors(BATCH_FULL)
    for dut in old_primary:
        assert set(old_primary[dut]) == set(new_primary[dut])
        assert all(same_summary(value, new_primary[dut][node]) for node, value in old_primary[dut].items())
    old_vsq, new_vsq = node_summaries(DEEP_FULL, "virtual_store_queue.summary.json"), node_summaries(BATCH_FULL, "virtual_store_queue.summary.json")
    assert len(old_vsq) == 47 and len(new_vsq) == 48 and old_vsq.keys() <= new_vsq.keys()
    assert all(new_vsq[node] == value for node, value in old_vsq.items())
    old_uq, new_uq = node_summaries(DEEP_FULL, "unalign_queue.summary.json"), node_summaries(BATCH_FULL, "unalign_queue.summary.json")
    assert old_uq == new_uq and len(new_uq) == 42
    all_nodes = set().union(*(set(items) for items in new_primary.values())) | {xml_node(node) for node in new_vsq} | {xml_node(node) for node in new_uq}
    assert all_nodes == set(current)
    old_streams, new_streams = journal_streams(DEEP_FULL), journal_streams(BATCH_FULL)
    assert old_streams == new_streams and len(new_streams) == 2223
    rows = []
    for dut in ("forward_module", "physical_store_queue", "store_queue", "lsq_wrapper", "unalign_queue", "virtual_store_queue"):
        old_meta, old_dat = native(DEEP_FULL, dut); new_meta, new_dat = native(BATCH_FULL, dut)
        expected_inputs = len(new_vsq) if dut == "virtual_store_queue" else len(new_uq) if dut == "unalign_queue" else len(new_primary[dut])
        assert new_meta["artifact"]["input_files"] == expected_inputs
        assert old_meta["artifact"]["build"] == new_meta["artifact"]["build"]
        for filename, digest in new_meta["artifact"]["build"]["files"].items():
            assert sha256_file(Path(filename)) == digest
        analyzed = summarize(new_dat, new_meta["artifact"]["build"], new_meta["artifact"])
        assert analyzed["raw_parser_matches_analyzer"] and analyzed["coverage_artifact_matches_dat"]
        old_sets, new_sets = point_sets(old_dat), point_sets(new_dat)
        metrics = {}
        for kind in old_sets:
            assert old_sets[kind]["all"] == new_sets[kind]["all"] and old_sets[kind]["hit"] <= new_sets[kind]["hit"]
            gained = new_sets[kind]["hit"] - old_sets[kind]["hit"]
            metrics[kind] = dict(before_hit=len(old_sets[kind]["hit"]), after_hit=len(new_sets[kind]["hit"]), total=len(new_sets[kind]["all"]),
                                 newly_hit=len(gained), newly_hit_SHA256=digest_keys(gained), newly_missing=0,
                                 still_missing=len(new_sets[kind]["missing"]))
        row = dict(dut=dut, old_run=DEEP_FULL, native_build_id=new_meta["artifact"]["build"]["build_id"],
                   original_native_inputs=old_meta["artifact"]["input_files"], current_native_inputs=new_meta["artifact"]["input_files"],
                   before_coverage_dat_SHA256=sha256_file(old_dat), after_coverage_dat_SHA256=sha256_file(new_dat), metrics=metrics,
                   original_source_line_coverage=line_delta(source_lines(old_meta, old_dat, dut), source_lines(new_meta, new_dat, dut)))
        if dut == "virtual_store_queue":
            old_points, new_points = retire_batch_points(old_dat), retire_batch_points(new_dat)
            assert [p["hit"] for p in old_points] == [0, 0] and [p["hit"] for p in new_points] == [1, 1]
            row["retire_req_num_points"] = dict(before=old_points, after=new_points)
        else:
            assert sha256_file(old_dat) == sha256_file(new_dat), (dut, "unchanged contributor raw dat differs")
        rows.append(row)
    report = dict(format="lsq-vsq-retire-batch-contributor-regression-v1", run=BATCH_FULL, baseline_run=DEEP_FULL,
        status=status, source_aggregate=source["aggregate_SHA256"], original_nodes=1172, current_nodes=1173,
        added_passing_nodes=1, added_nodes=sorted(added), original_failures=171, failure_SHA256=failure_digest(current),
        manifest_SHA256=sha256_file(ROOT / "results" / BATCH_FULL / "execution/manifest.json"), rows=rows,
        original_vsq_contributors=47, current_vsq_contributors=48,
        original_wrapper_public_check_actor_summaries_equal=len(old_streams),
        directed_full_semantics=validate_same_leaf_full_semantics(BATCH_AFTER, BATCH_FULL, "test_retire_batch_width", "VSQ-RETIRE.batch_width", list(range(1, 9)), list(range(1, 10))),
        calibration_history=calibration_history(),
        coverage_monotonicity=dict(name="all_old_native_hits_retained", passed=True, status="PASS", failed_duts=[], newly_missing_toggle_points=0, required=True, waived=False),
        verification=dict(actual_single_fresh_six_build_execution=True, original_1172_outcomes_and_failure_details_equal=True,
            one_new_retire_batch_node_pass=True, no_old_hit_lost=True, all_original_vsq_streams_equal=True,
            wrapper_public_check_actor_streams_equal=True, all_native_input_counts_match_actual_contributors=True,
            new_node_full_public_and_semantics_equal_directed=True, actual_earlier_checker_failure_retained=True,
            retireReqNumReg_high_bit_directions_hit_in_full_vsq_build=True, locked_analyzer_and_artifact_hashes_checked=True,
            source_launch_end_aggregates_equal=True, no_per_cycle_JSON_or_waveforms=True),
        limits="One legal leaf VSQ retirement-batch supplement; parent semantic domains and recovery boundaries remain open. Unified regression15 and prior reports are immutable.")
    write_report(ROOT / "results" / BATCH_FULL / "vsq-retire-batch-contributor-evidence-v1.json", report)
    return report


def audit_pair(dut, before, after, scenario, feature):
    old_run, new_run = validate_run(before, dut), validate_run(after, dut)
    assert old_run["source"] == new_run["source"]
    original, current = cases(before), cases(after)
    assert set(original) < set(current) and all(current[node] == value for node, value in original.items())
    added = set(current) - set(original)
    assert len(added) == 3 and all(value["outcome"] == "PASS" for value in current.values())
    assert all("test_release_windows::" in node for node in added)
    closure = audit_delta(before, after, dut, feature, "tests/" + next(iter(added)).split("::")[0].removeprefix("tests.").replace(".", "/") + ".py (three actual redirect phases)")
    assert all(closure["verification"].values())
    old_meta, old_dat = native(before, dut); new_meta, new_dat = native(after, dut)
    old, new = point_sets(old_dat), point_sets(new_dat)
    assert old_meta["artifact"]["build"] == new_meta["artifact"]["build"]
    for kind in old:
        assert old[kind]["all"] == new[kind]["all"] and old[kind]["hit"] <= new[kind]["hit"]
    targets = dict(before=branch_targets(old_dat, dut), after=branch_targets(new_dat, dut))
    assert all(row["count"] == 0 for row in targets["after"] if row["arm"] == "else")
    assert all(row["count"] > 0 for row in targets["after"] if row["arm"] == "if")
    paths = sorted((ROOT / "results" / after / "cases").rglob("vsq-release-walk-witness.json"))
    assert len(paths) == 3
    public = [witness(path, dut) for path in paths]
    assert {w["redirect_extra_idle"] for w in public} == {0, 1, 2}
    assert len({tuple(p["recovery"]["sq_stall_cycles"] for p in w["profiles"]) for w in public}) == 3
    functions = {run: functional_counts(run, dut, scenario) for run in (before, after)}
    assert functions[after]["checked"]["count"] > functions[before]["checked"]["count"]
    if dut != "lsq_wrapper":
        assert functions[before]["checked"]["count"] == 0
    overlap = {}
    _, reference_dat = native("lsq-progress-regression-15", dut)
    reference = point_sets(reference_dat)
    for kind in reference:
        assert reference[kind]["all"] == new[kind]["all"]
        delta = reference[kind]["missing"] & new[kind]["hit"]
        overlap[kind] = dict(regression15_missing_seen_in_directed_after=len(delta), point_set_SHA256=digest_keys(delta))
    before_primary, after_primary = contributors(before).get(dut, {}), contributors(after).get(dut, {})
    if dut == "virtual_store_queue":
        before_primary, after_primary = (node_summaries(name, "virtual_store_queue.summary.json") for name in (before, after))
    assert len(before_primary) == len(original) and len(after_primary) == len(current)
    assert all(same_summary(value, after_primary[node]) for node, value in before_primary.items())
    if dut == "lsq_wrapper":
        old_streams, new_streams = journal_streams(before), journal_streams(after)
        assert all(new_streams[key] == value for key, value in old_streams.items())
    report = dict(format="lsq-vsq-release-windows-evidence-v1", dut=dut, before_run=before, after_run=after, feature_id=feature,
        contract="docs/contracts/vsq-release-walk.md", baseline_tests=len(original), after_tests=len(current), added_nodes=sorted(added),
        source_aggregate=old_run["source"]["aggregate_SHA256"], native_build_id=new_meta["artifact"]["build"]["build_id"],
        raw_nonwrapper_metrics=closure["metrics"], branch_targets=targets, regression15_gap_overlap=overlap,
        state3_source_proof=source_proof(dut), functional=functions,
        original_source_line_coverage=line_delta(source_lines(old_meta, old_dat, dut), source_lines(new_meta, new_dat, dut)),
        witness_paths=[str(path.relative_to(ROOT)) for path in paths], witness_SHA256s=[sha256_file(path) for path in paths], witnesses=public,
        verification=dict(actual_native_dut_toffee_and_reference_checks=True, same_build_and_three_point_universes=True,
            no_old_hit_lost=True, old_nodes_and_public_primary_streams_equal=True, all_three_extra_idle_phases_witnessed=True,
            distinct_public_stall_windows_witnessed=True, retained_and_new_UIDs_normally_complete=True,
            exact_retained_tail_and_cancelled_suffix_checked=True, source_launch_end_aggregates_equal=True,
            artifact_and_locked_analyzer_checked=True, state3_boundary_not_dynamic_gain=True, separate_release_wait_not_waived=True),
        limits="Legal retirement/redirect-phase complement, not complete recovery acceptance. Both15850 and15853 else remain unhit; only15853 has a post-reset state3 source induction proof. No classification/coverage credit for the release-wait arm. Each parent keeps actual children and real bytes/consumption; leaf proves only virtual/public timing. No per-cycle JSON/waves or source copies, no shared actor/model/RTL edits.")
    write_report(ROOT / "results" / after / "vsq-release-windows-evidence-v1.json", report)
    return report


def audit_full():
    status, source = stable_run(FULL)
    assert status["total_cases"] == 1171 and status["manifest_tests"] == {"PASS": 1000, "FAIL": 171} and status["pytest_exitstatus"] == 1
    original, current = cases(PREVIOUS), cases(FULL)
    leaf_old = {node: value for node, value in cases("lsq-progress-regression-15").items() if node.startswith("tests.vsq.")}
    baseline_cases = cases("vsq-release-windows-baseline-01")
    baseline_only = set(baseline_cases) - set(leaf_old)
    assert len(baseline_only) == 1 and all(baseline_cases[node]["outcome"] == "PASS" for node in baseline_only)
    assert len(original) == 1119 and len(leaf_old) == 42
    original.update(leaf_old)
    original.update({node: baseline_cases[node] for node in baseline_only})
    assert len(original) == 1162 and set(original) < set(current)
    baseline_vsq = node_summaries("vsq-release-windows-baseline-01", "virtual_store_queue.summary.json")
    current_vsq = node_summaries(FULL, "virtual_store_queue.summary.json")
    extra_primary = {node: value for node, value in baseline_vsq.items() if xml_node(node) in baseline_only}
    assert len(extra_primary) == 1 and all(current_vsq[node] == value for node, value in extra_primary.items())
    for node, value in original.items():
        if node in RELOCATED_FAILURE_NODES:
            assert current[node]["outcome"] == value["outcome"]
            assert normalize_known_failure_source_lines({node: current[node]})[node] == normalize_known_failure_source_lines({node: value})[node]
        else:
            assert current[node] == value
    original_failure_sha = failure_digest(original)
    current_failure_sha = failure_digest(current)
    normalized_original_failure_sha = failure_digest(normalize_known_failure_source_lines(original))
    normalized_current_failure_sha = failure_digest(normalize_known_failure_source_lines(current))
    assert normalized_original_failure_sha == normalized_current_failure_sha
    assert set(RELOCATED_FAILURE_NODES) <= set(original) and set(RELOCATED_FAILURE_NODES) <= set(current)
    for node in RELOCATED_FAILURE_NODES:
        assert "tests/vsq/test_extended.py:196:" in original[node]["detail"]
        assert "tests/vsq/test_extended.py:226:" in current[node]["detail"]
    added = set(current) - set(original)
    expected = set().union(*(set(cases(after)) - set(cases(before)) for _, before, after, _, _ in PAIRS))
    assert len(added) == 9 and added == expected and all(current[node]["outcome"] == "PASS" for node in added)
    command = load(ROOT / "results" / FULL / "command.json")["command"]
    assert command[command.index("--lsq-trace-max-mb") + 2:] == FULL_PATHS + ["--tb=short"]
    manifest = load(ROOT / "results" / FULL / "execution/manifest.json")
    assert len([a for a in manifest["artifacts"] if a["kind"] == "native"]) == 6
    before_primary, after_primary = contributors(PREVIOUS), contributors(FULL)
    assert {dut: len(nodes) for dut, nodes in before_primary.items()} == dict(forward_module=186, physical_store_queue=70, store_queue=83, lsq_wrapper=738)
    assert {dut: len(nodes) for dut, nodes in after_primary.items()} == dict(forward_module=186, physical_store_queue=70, store_queue=86, lsq_wrapper=741)
    for dut, nodes in before_primary.items():
        assert all(same_summary(value, after_primary[dut][node]) for node, value in nodes.items())
    extra_streams = {}
    nodes = set().union(*(set(items) for items in after_primary.values()))
    for dut, old_run, filename, n in (("virtual_store_queue", "lsq-progress-regression-15", "virtual_store_queue.summary.json", 42),
                                      ("unalign_queue", PREVIOUS, "unalign_queue.summary.json", 42)):
        old, new = node_summaries(old_run, filename), node_summaries(FULL, filename)
        assert len(old) == n and len(new) == n + (4 if dut == "virtual_store_queue" else 0)
        assert all(new[node] == value for node, value in old.items())
        meta, _ = native(FULL, dut)
        assert meta["artifact"]["input_files"] == len(new)
        nodes |= {xml_node(node) for node in new}
        extra_streams[dut] = n
    assert nodes == set(current)
    old_streams, new_streams = journal_streams(PREVIOUS), journal_streams(FULL)
    assert len(old_streams) == 2214 and len(new_streams) == 2223
    assert all(new_streams[key] == value for key, value in old_streams.items())
    rows, all_witnesses = [], []
    for dut, old_run in [(dut, PREVIOUS) for dut in ("forward_module", "physical_store_queue", "store_queue", "lsq_wrapper", "unalign_queue")] + [("virtual_store_queue", "lsq-progress-regression-15")]:
        old_meta, old_dat = native(old_run, dut); new_meta, new_dat = native(FULL, dut)
        assert old_meta["artifact"]["build"] == new_meta["artifact"]["build"]
        for filename, digest in new_meta["artifact"]["build"]["files"].items():
            assert sha256_file(Path(filename)) == digest
        analyzed = summarize(new_dat, new_meta["artifact"]["build"], new_meta["artifact"])
        assert analyzed["raw_parser_matches_analyzer"] and analyzed["coverage_artifact_matches_dat"]
        old, new = point_sets(old_dat), point_sets(new_dat)
        metrics = {}
        for kind in old:
            assert old[kind]["all"] == new[kind]["all"] and old[kind]["hit"] <= new[kind]["hit"]
            delta = new[kind]["hit"] - old[kind]["hit"]
            metrics[kind] = dict(before_hit=len(old[kind]["hit"]), after_hit=len(new[kind]["hit"]), total=len(new[kind]["all"]),
                                 newly_hit=len(delta), newly_hit_SHA256=digest_keys(delta), newly_missing=0, still_missing=len(new[kind]["missing"]))
        row = dict(dut=dut, old_run=old_run, native_build_id=new_meta["artifact"]["build"]["build_id"],
            original_native_inputs=old_meta["artifact"]["input_files"], current_native_inputs=new_meta["artifact"]["input_files"],
            before_coverage_dat_SHA256=sha256_file(old_dat), after_coverage_dat_SHA256=sha256_file(new_dat), metrics=metrics,
            original_source_line_coverage=line_delta(source_lines(old_meta, old_dat, dut), source_lines(new_meta, new_dat, dut)))
        if dut in SOURCES:
            directed_run = next(after for key, _, after, _, _ in PAIRS if key == dut)
            directed = load(ROOT / "results" / directed_run / "vsq-release-windows-evidence-v1.json")
            paths = [path for path in (ROOT / "results" / FULL / "cases").rglob("vsq-release-walk-witness.json") if load(path)["dut"] == dut]
            assert len(paths) == 3
            witnesses = [witness(path, dut) for path in paths]
            assert sorted(json.dumps(w, sort_keys=True) for w in witnesses) == sorted(json.dumps(w, sort_keys=True) for w in directed["witnesses"])
            all_witnesses.extend(witnesses)
            row["branch_targets"] = branch_targets(new_dat, dut)
            assert all(point["count"] == 0 for point in row["branch_targets"] if point["arm"] == "else")
        rows.append(row)
    assert len(all_witnesses) == 9
    actor_hashes = load(ROOT / "results" / PREVIOUS / "uq-page-contributor-regression-evidence-v1.json")["unchanged_generic_actor_SHA256"]
    assert all(sha256_file(ROOT / name) == digest for name, digest in actor_hashes.items())
    gate = dict(name="all_old_native_hits_retained", passed=True, status="PASS", failed_duts=[], newly_missing_toggle_points=0, required=True, waived=False)
    report = dict(format="lsq-vsq-release-contributor-regression-v1", run=FULL, baseline_runs=[PREVIOUS, "lsq-progress-regression-15"],
        status=status, source_aggregate=source["aggregate_SHA256"], original_nodes=1162, current_nodes=1171,
        added_passing_nodes=9, added_nodes=sorted(added), baseline_only_preexisting_vsq_nodes=sorted(baseline_only), original_failures=171,
        original_failure_SHA256=original_failure_sha, current_failure_SHA256=current_failure_sha,
        normalized_failure_SHA256=normalized_current_failure_sha,
        known_source_line_relocations=[dict(node=node, before_line=196, after_line=226,
                                             reason="A pre-existing30-line release-test insertion moves the frame; exact old/current source diff and all pre-existing function ASTs are checked. Assertion, actual result and failure outcome are unchanged.")
                                       for node in RELOCATED_FAILURE_NODES],
        source_line_relocation_evidence=relocated_failure_source_evidence(),
        manifest_SHA256=sha256_file(ROOT / "results" / FULL / "execution/manifest.json"), rows=rows,
        original_four_build_primary_summaries_equal=1077, original_wrapper_public_check_actor_summaries_equal=2214,
        preexisting_vsq_contributor_summaries_equal=1,
        original_extra_primary_summaries_equal=extra_streams, full_witnesses_equal_directed=9,
        unchanged_generic_actor_SHA256=actor_hashes, coverage_monotonicity=gate,
        verification=dict(actual_single_fresh_six_build_execution=True, all_1162_original_outcomes_and_failure_details_equal_after_explicit_known_source_line_normalization=True,
            nine_new_nodes_pass=True, one_preexisting_vsq_contributor_explicitly_retained=True, same_builds_and_three_point_universes=True, no_old_hit_lost=True,
            every_native_contributor_matches_manifest=True, original_primary_and_wrapper_streams_equal=True,
            nine_witnesses_equal_directed=True, original_actor_hashes_equal=True, locked_analyzer_and_artifact_hashes_checked=True,
            source_launch_end_aggregates_equal=True, separate_release_wait_gap_not_waived=True, no_per_cycle_JSON_or_waveforms=True),
        limits="Complete selected six-build contribution scope, not all38-build signoff. All171 failures remain; post-reset state3 proof is a static classification correction only, not branch gain.15850 release-wait else remains open in all three layers. Unified regression15 data/denominators/227failures are not replaced.")
    write_report(ROOT / "results" / FULL / "vsq-release-contributor-regression-evidence-v1.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--batch", action="store_true")
    args = parser.parse_args()
    if not args.deep and not args.batch:
        for pair in PAIRS:
            result = audit_pair(*pair)
            print(json.dumps({key: result[key] for key in ("dut", "baseline_tests", "after_tests", "raw_nonwrapper_metrics", "branch_targets", "verification")}, indent=2))
    if args.full:
        print(json.dumps(audit_full(), indent=2))
    if args.deep:
        print(json.dumps(audit_deep_directed(), indent=2))
        print(json.dumps(audit_deep_full(), indent=2))
    if args.batch:
        print(json.dumps(audit_batch_directed(), indent=2))
        print(json.dumps(audit_batch_full(), indent=2))
