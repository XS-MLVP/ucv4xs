#!/usr/bin/env python3
"""Audit paired second-page lifetimes and the complete five-build rerun."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from audit_checkpoint_pool_v1 import validate_run
from audit_coverage_points_v1 import records, sha256_file, summarize
from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases, failure_digest
from audit_gap_closure_v1 import audit as audit_delta, digest_keys, native, point_key, point_sets
from audit_native_case_probe_v1 import journal_streams, stable_run, xml_node
from audit_native_contributor_scope_v1 import COMMAND_PATHS, contributors, same_summary
from audit_store_strict_lifetimes_v1 import source_lines

ROOT = Path(__file__).resolve().parents[1]
FULL = "uq-page-contributor-regression-01"
PREFIX_FULL = "store-prefix-contributor-regression-01"
PAIRS = (
    ("unalign_queue", "uq-page-pairs-baseline-02", "uq-page-pairs-after-02", "UQ-PAGE.paired_lifetimes", "UQ-PAIRED-SECOND-PAGE-LIFETIMES"),
    ("physical_store_queue", "psq-page-pairs-baseline-01", "psq-page-pairs-after-01", "PSQ-PAGE.paired_lifetimes", "PSQ-PAIRED-SECOND-PAGE-LIFETIMES"),
    ("store_queue", "sq-page-pairs-baseline-02", "sq-page-pairs-after-01", "SQ-PAGE.paired_lifetimes", "SQ-PAIRED-SECOND-PAGE-LIFETIMES"),
    ("lsq_wrapper", "lsq-page-pairs-baseline-01", "lsq-page-pairs-after-01", "LSQ-FORWARD.page", "LSQ-PAIRED-SECOND-PAGE-LIFETIMES"),
)
BASES = (0, 62, 64, 126, 128, 190, 192, 254)


def load(path):
    return json.loads(path.read_text())


def second_pa(profile, owner):
    return (((1 << 36) - 1 - owner) if profile % 2 == 0 else owner) << 12


def target_points(dat):
    regex = re.compile(r"entries_(0|1)_paddrHigh\[(\d+)\]:(0->1|1->0)")
    points = {}
    for point in records(dat):
        if point["t"] != "toggle" or point["f"].endswith("_top.sv"):
            continue
        match = regex.fullmatch(point["o"])
        if not match:
            continue
        key = (int(match[1]), int(match[2]), match[3])
        assert key not in points
        points[key] = point
    expected = {(lane, bit, direction) for lane in range(2) for bit in range(36) for direction in ("0->1", "1->0")}
    assert set(points) == expected and len(points) == 144
    return points


def page_witness(path, dut):
    witness = load(path)
    assert witness["format"] == "lsq-uq-page-pairs-witness-v1" and witness["dut"] == dut
    assert len(witness["profiles"]) == 8 and len(witness["public_trace_SHA256"]) == 64
    for profile, base, item in zip(range(8), BASES, witness["profiles"]):
        assert item["profile"] == profile
        if dut == "unalign_queue":
            assert item["pair_SQ"] == [base, base + 1] and item["third_SQ"] == base + 2
            assert item["pair_PA"] == [second_pa(profile, 0), second_pa(profile, 1)]
            assert item["third_PA"] == (2 if profile % 2 == 0 else (1 << 36) - 3) << 12
            assert item["pair_public_slots"] == [3 * profile % 2, (3 * profile + 1) % 2]
            assert item["third_slot"] == (3 * profile + 2) % 2
            assert item["actual_page_completions"] == 3 and item["held_full_cycles"] == 3
        else:
            assert item["head_before"] == base and item["head_after"] == base + 2
            assert item["fillers_completed"] == base - (BASES[profile - 1] + 2 if profile else 0)
            expected_handshakes = []
            for index in range(2):
                expected = {"position": base + index, "lane": index,
                            "sq": {"first": bool((base + index) // 128),
                                   "second": bool(((base + index) % 128) // 64),
                                   "value": (base + index) % 64},
                            "paddr": second_pa(profile, index)}
                if dut != "lsq_wrapper":
                    expected["uid"] = item["page_handshakes"][index]["uid"]
                expected_handshakes.append(expected)
            assert item["page_handshakes"] == expected_handshakes
            assert item["no_Sbuffer_consumption_before_permission"]
            assert item["cross_page_store_completions"] == 2 and item["actual_Sbuffer_fragments"] == 4
            if dut == "lsq_wrapper":
                assert item["actual_Load_completions"] == 2 and item["query_lane"] == witness["query_lane"]
    if dut == "unalign_queue":
        assert witness["completed_page_uids"] == 24
    else:
        assert witness["completed_store_uids"] == 256 and witness["cross_page_store_uids"] == 16
        assert witness["actual_Sbuffer_fragments"] == 272
        if dut == "lsq_wrapper":
            assert witness["completed_Load_uids"] == 16 and witness["query_lane"] in range(3)
        else:
            uids = [event["uid"] for item in witness["profiles"] for event in item["page_handshakes"]]
            assert len(uids) == len(set(uids)) == 16 and all(uid > 0 for uid in uids)
    return witness


def functional_counts(run, dut, scenario):
    data = load(ROOT / "results" / run / "execution/functional-coverage.json")
    result = {}
    for scope in ("reached", "checked"):
        group = next(g for g in data["groups"] if g["instance"] == f"lsq.{dut}.{scope}")
        assert group["collection_complete"]
        result[scope] = dict(count=group["points"][0]["counts"].get(scenario, 0),
                             coverage=group["coverage"], collection_complete=group["collection_complete"])
    return result


def audit_pair(dut, before, after, scenario, feature):
    old_run, new_run = validate_run(before, dut), validate_run(after, dut)
    assert old_run["source"] == new_run["source"]
    old_cases, new_cases = cases(before), cases(after)
    assert set(old_cases) < set(new_cases)
    added_nodes = set(new_cases) - set(old_cases)
    assert len(added_nodes) == (3 if dut == "lsq_wrapper" else 1)
    assert all(new_cases[node] == value for node, value in old_cases.items())
    if dut == "unalign_queue":
        case = "tests/unalign/test_page_pairs.py::test_two_pages_hold_full_third_waits_then_real_slot_reuse"
    elif dut == "physical_store_queue":
        case = "tests/psq/test_uq_page_pairs.py::test_actual_paired_second_pages_full_PA_bits_and_normal_reuse"
    elif dut == "store_queue":
        case = "tests/store_queue/test_uq_page_pairs.py::test_actual_paired_second_pages_full_PA_bits_and_normal_reuse[True]"
    else:
        case = "tests/lsq_wrapper/test_uq_page_pairs.py::test_real_cross_page_pair_high_low_PA_original_Loads_and_Store_fragments"
    closure = audit_delta(before, after, dut, feature, case)
    assert all(closure["verification"].values())
    old_meta, old_dat = native(before, dut); new_meta, new_dat = native(after, dut)
    assert old_meta["artifact"]["build"] == new_meta["artifact"]["build"]
    old, new = point_sets(old_dat), point_sets(new_dat)
    for kind in old:
        assert old[kind]["all"] == new[kind]["all"] and old[kind]["hit"] <= new[kind]["hit"]
    old_target, new_target = target_points(old_dat), target_points(new_dat)
    assert {point_key(p) for p in old_target.values()} == {point_key(p) for p in new_target.values()}
    assert len({point["f"] for point in new_target.values()}) == 1
    assert all(point["hit"] > 0 for point in new_target.values())
    witnesses = sorted((ROOT / "results" / after / "cases").rglob("uq-page-pairs-witness.json"))
    expected_witnesses = 1 if dut != "lsq_wrapper" else 3
    assert len(witnesses) == expected_witnesses
    public = [page_witness(path, dut) for path in witnesses]
    if dut == "lsq_wrapper":
        assert {w["query_lane"] for w in public} == {0, 1, 2}
    functional = {name: functional_counts(name, dut, scenario) for name in (before, after)}
    assert functional[after]["checked"]["count"] > 0
    if dut != "lsq_wrapper":
        assert functional[before]["checked"]["count"] == functional[before]["reached"]["count"] == 0
    assert functional[after]["checked"]["count"] > functional[before]["checked"]["count"]
    line_old, line_new = source_lines(old_meta, old_dat, dut), source_lines(new_meta, new_dat, dut)
    assert line_old[0] == line_new[0] and line_old[1] <= line_new[1]
    reference_meta, reference_dat = native("lsq-progress-regression-15", dut)
    assert reference_meta["artifact"]["build"] == new_meta["artifact"]["build"]
    reference = point_sets(reference_dat)
    overlap = {}
    for kind in reference:
        assert reference[kind]["all"] == new[kind]["all"]
        hits = reference[kind]["missing"] & new[kind]["hit"]
        overlap[kind] = dict(regression15_missing_seen_in_directed_after=len(hits), point_set_SHA256=digest_keys(hits))
    report = dict(format="lsq-uq-page-pairs-evidence-v1", dut=dut, before_run=before, after_run=after,
        contract="docs/contracts/uq-second-page-pairs.md", feature_id=feature, native_build_id=closure["native_build_id"],
        baseline_tests=len(old_cases), after_tests=len(new_cases), added_nodes=sorted(added_nodes),
        source_aggregate=old_run["source"]["aggregate_SHA256"], raw_nonwrapper_metrics=closure["metrics"],
        target_second_page_paddr_high=dict(before_hit=sum(p["hit"] > 0 for p in old_target.values()), after_hit=sum(p["hit"] > 0 for p in new_target.values()), total=144,
            newly_hit=len({point_key(p) for p in new_target.values() if p["hit"] > 0} - {point_key(p) for p in old_target.values() if p["hit"] > 0}),
            point_set_SHA256=digest_keys({point_key(p) for p in new_target.values()}),
            semantic_identity_set_SHA256=digest_keys(set(new_target)),
            source_samples=sorted({str(Path(p["f"]).relative_to(ROOT)) for p in new_target.values()}),
            declaration_lines=sorted({int(p["l"]) for p in new_target.values()})),
        regression15_gap_overlap=overlap,
        functional=functional,
        original_source_line_coverage=dict(before_hit=len(line_old[1]), after_hit=len(line_new[1]), total=len(line_new[0]),
            newly_hit=len(line_new[1] - line_old[1]), newly_missing=0),
        witness_paths=[str(path.relative_to(ROOT)) for path in witnesses], witness_SHA256=[sha256_file(path) for path in witnesses], witnesses=public,
        verification=dict(actual_picker_toffee_and_fixed_rtl=True, same_native_build_and_point_universes=True,
            no_old_hit_lost=True, complete_high36_second_page_target_checked=True, two_lane_or_three_wrapper_lane_real_trace=True,
            real_page_fire_and_normal_completion_checked=True, functional_bin_checked=True,
            both_source_launch_end_aggregates_equal=True, locked_analyzer_matches_raw_dat=True,
            artifact_and_build_hashes_verified=True, all_baseline_nodes_retained=True),
        limits="The legal paired second-page complement checks high36 page PA, two-slot retention and normal parent consumption. It does not close all UQ/PSQ/SQ/Wrapper recovery, exception, bus, cross-page Load or disabled-feedback domains; low12 page-aligned zeros and invalid payload are not treated as dynamic coverage. Results stay separate from regression15.")
    output = ROOT / "results" / after / "uq-page-pairs-evidence-v1.json"
    write_report(output, report)
    return report


def node_summaries(run, filename):
    result = {}
    for path in (ROOT / "results" / run / "cases").rglob("*.summary.json"):
        if path.name != filename:
            continue
        item = load(path)
        node = item["nodeid"]
        assert node not in result
        result[node] = dict(records=item["records"], serialized_bytes=item["serialized_bytes"], streamed_SHA256=item["streamed_SHA256"])
    return result


def excluded_startup_runs():
    contaminated = "uq-page-pairs-baseline-01"
    old_manifest = load(ROOT / "results" / contaminated / "execution/manifest.json")
    old_nodes = cases(contaminated)
    formal_old, formal_new = cases("uq-page-pairs-baseline-02"), cases("uq-page-pairs-after-02")
    assert len(old_nodes) == 42 and old_manifest["tests"] == {"PASS": 42}
    assert set(old_nodes) == set(formal_new) and len(set(old_nodes) - set(formal_old)) == 1
    invalid_node = next(iter(set(old_nodes) - set(formal_old)))
    assert invalid_node.startswith("tests.unalign.test_page_pairs::")
    empty = "sq-page-pairs-baseline-01"
    empty_manifest = load(ROOT / "results" / empty / "execution/manifest.json")
    assert empty_manifest["state"] == "incomplete" and empty_manifest["pytest_exitstatus"] == 5
    assert not empty_manifest.get("tests")
    return [dict(run=contaminated, state=old_manifest["state"], tests=old_manifest["tests"],
                 original_manifest_SHA256=sha256_file(ROOT / "results" / contaminated / "execution/manifest.json"),
                 used_as_baseline=False, reason="Directory selector already included the new page-pair node.",
                 replacement="uq-page-pairs-baseline-02"),
            dict(run=empty, state=empty_manifest["state"], pytest_exitstatus=5,
                 original_manifest_SHA256=sha256_file(ROOT / "results" / empty / "execution/manifest.json"),
                 used_as_baseline=False, reason="Incomplete fixture parameter ID selected no tests.",
                 replacement="sq-page-pairs-baseline-02")]


def audit_full():
    name = FULL
    status, source_launch = stable_run(name)
    assert status["manifest_tests"] == {"PASS": 950, "FAIL": 169} and status["pytest_exitstatus"] == 1
    assert status["total_cases"] == 1119
    old_prefix, current = cases(PREFIX_FULL), cases(name)
    old_uq = cases("lsq-progress-regression-15")
    uq_nodes = {node: value for node, value in old_uq.items() if node.startswith("tests.unalign.")}
    assert len(uq_nodes) == 41
    baseline_union = dict(old_prefix)
    baseline_union.update(uq_nodes)
    assert len(baseline_union) == 1113 and len(current) == 1119
    assert all(current[node] == value for node, value in baseline_union.items())
    added = set(current) - set(baseline_union)
    assert len(added) == 6 and all(current[node]["outcome"] == "PASS" for node in added)
    expected_added = set().union(*(set(cases(after)) - set(cases(before)) for _, before, after, _, _ in PAIRS))
    assert added == expected_added
    assert failure_digest(baseline_union) == failure_digest(current)
    command = load(ROOT / "results" / name / "command.json")["command"]
    expected_paths = COMMAND_PATHS + ["tests/unalign/test_basic.py", "tests/unalign/test_extended.py", "tests/unalign/test_page_pairs.py"]
    assert command[command.index("--lsq-trace-max-mb") + 2:] == expected_paths + ["--tb=short"]
    manifest = load(ROOT / "results" / name / "execution/manifest.json")
    assert len([a for a in manifest["artifacts"] if a["kind"] == "native"]) == 5
    old_contributors, new_contributors = contributors(PREFIX_FULL), contributors(name)
    assert {dut: len(items) for dut, items in old_contributors.items()} == dict(forward_module=186, physical_store_queue=69, store_queue=82, lsq_wrapper=735)
    assert {dut: len(items) for dut, items in new_contributors.items()} == dict(forward_module=186, physical_store_queue=70, store_queue=83, lsq_wrapper=738)
    for dut, original in old_contributors.items():
        assert set(original) <= set(new_contributors[dut])
        assert all(same_summary(value, new_contributors[dut][node]) for node, value in original.items())
    rows = []
    for dut, old_run in (("forward_module", PREFIX_FULL), ("physical_store_queue", PREFIX_FULL), ("store_queue", PREFIX_FULL), ("lsq_wrapper", PREFIX_FULL), ("unalign_queue", "lsq-progress-regression-15")):
        old_meta, old_dat = native(old_run, dut); new_meta, new_dat = native(name, dut)
        assert old_meta["artifact"]["build"] == new_meta["artifact"]["build"]
        for filename, digest in new_meta["artifact"]["build"]["files"].items():
            assert sha256_file(Path(filename)) == digest
        summary = summarize(new_dat, new_meta["artifact"]["build"], new_meta["artifact"])
        assert summary["raw_parser_matches_analyzer"] and summary["coverage_artifact_matches_dat"]
        old, new = point_sets(old_dat), point_sets(new_dat)
        metrics = {}
        for kind in old:
            assert old[kind]["all"] == new[kind]["all"] and old[kind]["hit"] <= new[kind]["hit"]
            gained = new[kind]["hit"] - old[kind]["hit"]
            metrics[kind] = dict(before_hit=len(old[kind]["hit"]), after_hit=len(new[kind]["hit"]), total=len(new[kind]["all"]),
                newly_hit=len(gained), newly_hit_SHA256=digest_keys(gained), newly_missing=0, still_missing=len(new[kind]["missing"]))
        old_lines, new_lines = source_lines(old_meta, old_dat, dut), source_lines(new_meta, new_dat, dut)
        assert old_lines[0] == new_lines[0] and old_lines[1] <= new_lines[1]
        targets = target_points(new_dat) if dut != "forward_module" else {}
        assert not targets or all(p["hit"] > 0 for p in targets.values())
        previous_targets = target_points(old_dat) if targets else {}
        if targets:
            directed = next(load(ROOT / "results" / after / "uq-page-pairs-evidence-v1.json") for key, _, after, _, _ in PAIRS if key == dut)
            paths = [path for path in (ROOT / "results" / name / "cases").rglob("uq-page-pairs-witness.json") if load(path)["dut"] == dut]
            assert len(paths) == (3 if dut == "lsq_wrapper" else 1)
            witnessed = [page_witness(path, dut) for path in paths]
            assert sorted(json.dumps(w, sort_keys=True) for w in witnessed) == sorted(json.dumps(w, sort_keys=True) for w in directed["witnesses"])
        rows.append(dict(dut=dut, old_run=old_run, native_build_id=new_meta["artifact"]["build"]["build_id"],
            original_native_inputs=old_meta["artifact"]["input_files"], current_native_inputs=new_meta["artifact"]["input_files"],
            before_coverage_dat_SHA256=sha256_file(old_dat), after_coverage_dat_SHA256=sha256_file(new_dat), metrics=metrics,
            second_page_paddr_high_hit=len(targets) if targets else None, second_page_paddr_high_total=144 if targets else None,
            second_page_paddr_high_before_hit=sum(p["hit"] > 0 for p in previous_targets.values()) if targets else None,
            second_page_paddr_high_point_set_SHA256=digest_keys({point_key(p) for p in targets.values()}) if targets else None,
            original_source_line_coverage=dict(before_hit=len(old_lines[1]), after_hit=len(new_lines[1]), total=len(new_lines[0]), newly_missing=0)))
    old_uq_streams = node_summaries("lsq-progress-regression-15", "unalign_queue.summary.json")
    new_uq_streams = node_summaries(name, "unalign_queue.summary.json")
    assert len(old_uq_streams) == 41 and len(new_uq_streams) == 42
    assert old_uq_streams.keys() <= new_uq_streams.keys() and all(new_uq_streams[k] == v for k, v in old_uq_streams.items())
    uq_meta, _ = native(name, "unalign_queue")
    assert uq_meta["artifact"]["input_files"] == len(new_uq_streams)
    all_contributors = set().union(*(set(items) for items in new_contributors.values())) | {xml_node(node) for node in new_uq_streams}
    assert all_contributors == set(current)
    old_streams, new_streams = journal_streams(PREFIX_FULL), journal_streams(name)
    assert len(old_streams) == 2205 and len(new_streams) == 2214
    assert old_streams.keys() <= new_streams.keys()
    assert all(new_streams[key] == value for key, value in old_streams.items())
    actor_hashes = load(ROOT / "results" / PREFIX_FULL / "store-prefix-contributor-regression-evidence-v1.json")["first_probe_checker_failures_retained"]["unchanged_generic_actor_SHA256"]
    assert all(sha256_file(ROOT / path) == digest for path, digest in actor_hashes.items())
    gate = dict(name="all_old_native_hits_retained", passed=True, status="PASS", failed_duts=[], newly_missing_toggle_points=0, required=True, waived=False)
    report = dict(format="lsq-uq-page-contributor-regression-v1", run=name, baseline_runs=[PREFIX_FULL, "lsq-progress-regression-15"],
        status=status,
        original_nodes=1113, current_nodes=1119, added_passing_nodes=6, added_nodes=sorted(added), original_failures=169,
        failure_SHA256=failure_digest(current), source_aggregate=source_launch["aggregate_SHA256"],
        manifest_SHA256=sha256_file(ROOT / "results" / name / "execution/manifest.json"),
        rows=rows, unalign_original_inputs=41, unalign_current_inputs=42,
        original_unalign_public_streams_equal=41, original_wrapper_public_check_actor_summaries_equal=2205,
        original_four_build_primary_summaries_equal=1072, page_witnesses_equal_directed=6,
        unchanged_generic_actor_SHA256=actor_hashes, excluded_startup_runs=excluded_startup_runs(),
        coverage_monotonicity=gate,
        verification=dict(actual_single_fresh_five_build_execution=True, all_original_1113_outcomes_and_failure_details_equal=True,
            six_new_page_nodes_pass=True, same_native_builds_and_three_point_universes=True, no_old_hit_lost=True,
            all_original_unalign_streams_equal=True, second_page_high36_targets_hit_in_all_four_related_builds=True,
            full_original_native_contributors_retained=True, all_original_wrapper_check_actor_streams_equal=True,
            six_full_run_witnesses_equal_directed=True, locked_analyzer_matches_raw_dat=True, artifact_and_build_hashes_verified=True,
            source_launch_end_equal=True, no_cycle_JSON_or_waveforms=True),
        limits="This is the complete selected five-build contributor scope, not all38-build acceptance. The UQ old nodes are the 41 original unalign contributors, while the four parent scopes retain their prior complete contributors. All169 old failures remain explicit; regression15 raw dat, 227 failures and unified denominators stay immutable.")
    write_report(ROOT / "results" / name / "uq-page-contributor-regression-evidence-v1.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dut", choices=[p[0] for p in PAIRS])
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    for pair in PAIRS:
        if args.dut is None or args.dut == pair[0]:
            result = audit_pair(*pair)
            print(json.dumps({k: result[k] for k in ("dut", "raw_nonwrapper_metrics", "target_second_page_paddr_high", "functional", "verification")}, indent=2, ensure_ascii=False))
    if args.full:
        result = audit_full()
        print(json.dumps(result, indent=2, ensure_ascii=False))
