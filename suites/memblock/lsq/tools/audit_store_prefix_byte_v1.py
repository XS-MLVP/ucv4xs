#!/usr/bin/env python3
"""Audit legal SQ-prefix byte witnesses, exact coverage deltas and full scope."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from audit_checkpoint_pool_v1 import validate_run
from audit_coverage_points_v1 import records, sha256_file, summarize
from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases, failure_digest
from audit_gap_closure_v1 import audit as audit_delta, digest_keys, native, point_key, point_sets
from audit_native_case_probe_v1 import journal_streams, stable_run
from audit_native_contributor_scope_v1 import COMMAND_PATHS, FULL as PREVIOUS, PRIMARY, contributors, same_summary
from audit_store_payload_pool_v1 import audit_target
from audit_store_strict_lifetimes_v1 import source_lines

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ((0, 63), (63, 127), (127, 191), (191, 254), (254, 256))
FULL = "store-prefix-contributor-regression-01"
PAIRS = (
    ("forward_module", "forward", "FWD-WINDOW.prefix_byte", "FWD-EXCLUSIVE-PREFIX-BYTE-WINDOWS"),
    ("physical_store_queue", "psq", "PSQ-WINDOW.prefix_byte", "PSQ-EXCLUSIVE-PREFIX-BYTE-WINDOWS"),
    ("store_queue", "sq", "SQ-WINDOW.prefix_byte", "SQ-EXCLUSIVE-PREFIX-BYTE-WINDOWS"),
    ("lsq_wrapper", "lsq", "LSQ-FORWARD.sqid", "LSQ-EXCLUSIVE-PREFIX-BYTE-WINDOWS"),
)


def load(path):
    return json.loads(path.read_text())


def check_witness(w, dut):
    assert w["format"] == "lsq-store-prefix-byte-witness-v1" and w["dut"] == dut
    assert len(w["lifetimes"]) == 5 and len(w["payload_and_completion_SHA256"]) == 64
    assert w["checked_forward_responses"] == (256 if dut == "lsq_wrapper" else 768)
    for gen, ((start, end), life) in enumerate(zip(WINDOWS, w["lifetimes"])):
        assert life["generation"] == gen and (life["head_before"], life["head_after"]) == (start, end)
        assert life["public_slots"] == [position % 64 for position in range(start, end)]
        offsets = {((0 if pos == end - 1 else pos - start) + gen * 5) % 16 for pos in range(start, end)}
        assert life["offsets"] == sorted(offsets)
        assert (life["exclusive_upper_first"], life["exclusive_upper_last"]) == (start + 1, end)
        assert life["alias_first_byte"] == (37 * start + 53 * gen + 35) % 256
        assert life["alias_last_byte"] == (37 * (end - 1) + 53 * gen + 35) % 256
        assert life["alias_first_byte"] != life["alias_last_byte"]
        assert life["alias_vaddr"] == 0x200000 + gen * 65536 + gen * 5 % 16
        assert life["alias_paddr"] == 0xA000000 + gen * 65536 + gen * 5 % 16
        assert life["younger_alias_written_before_first_query"]
        assert life["checked_forward_responses"] == (end - start) * (1 if dut == "lsq_wrapper" else 3)
        if dut != "forward_module":
            assert life["normal_store_completions"] == life["sbuffer_consumed_owners"] == end - start
        if dut == "lsq_wrapper":
            assert life["normal_load_completions"] == end - start and life["query_lane"] == w["query_lane"]
    if dut == "forward_module":
        assert w["completed_query_uids"] == 768
    else:
        assert w["completed_store_uids"] == 256
    if dut == "lsq_wrapper":
        assert w["completed_load_uids"] == 256 and w["query_lane"] in range(3)


def low_vectors(dat):
    regex = re.compile(r"(s1CanForwardLow|s1SelectLowOH)(?:_([12]))?\[(\d+)\]:(0->1|1->0)")
    points, boundary = {}, []
    for p in records(dat):
        if p["t"] != "toggle" or p["f"].endswith("_top.sv"):
            continue
        match = regex.fullmatch(p["o"])
        if match:
            name, lane, bit, direction = match[1], int(match[2] or 0), int(match[3]), match[4]
            if bit == (63 if name == "s1CanForwardLow" else 0):
                boundary.append(p)
            else:
                identity = (name, lane, bit, direction)
                assert identity not in points
                points[identity] = p
    expected = {(name, lane, bit, direction) for name in ("s1CanForwardLow", "s1SelectLowOH")
                for lane in range(3) for bit in (range(63) if name == "s1CanForwardLow" else range(1, 64))
                for direction in ("0->1", "1->0")}
    assert set(points) == expected and len(boundary) == 12
    return points, boundary


def audit_pair(dut, prefix, scenario, feature):
    before, after = f"{prefix}-prefix-byte-baseline-01", f"{prefix}-prefix-byte-after-01"
    old, new = validate_run(before, dut), validate_run(after, dut)
    assert old["source"] == new["source"] and old["meta"]["artifact"]["build"] == new["meta"]["artifact"]["build"]
    added = set(new["nodes"]) - set(old["nodes"])
    assert len(added) == (3 if dut == "lsq_wrapper" else 1)
    assert all(new["nodes"][node] == value for node, value in old["nodes"].items())
    assert all("test_prefix_byte_windows::" in node for node in added)
    case = "tests/lsq_wrapper/test_prefix_byte_windows.py::test_real_interleaved_Load_prefix_excludes_younger_alias_and_completes" if dut == "lsq_wrapper" else f"tests/{dict(forward_module='forward',physical_store_queue='psq',store_queue='store_queue')[dut]}/test_prefix_byte_windows.py::test_nonfull_wrapped_exclusive_prefix_and_byte_offsets"
    closure = audit_delta(before, after, dut, feature, case)
    assert all(closure["verification"].values())
    for kind in ("line", "toggle", "branch"):
        assert old["points"][kind]["hit"] <= new["points"][kind]["hit"]
    old_low, _ = low_vectors(old["dat"]); new_low, boundary = low_vectors(new["dat"])
    assert all(p["hit"] > 0 for p in new_low.values())
    addresses = audit_target(old["dat"], new["dat"], dut, "vaddr", range(4))
    witnesses = sorted((ROOT / "results" / after / "cases").rglob("store-prefix-byte-witness.json"))
    assert len(witnesses) == (3 if dut == "lsq_wrapper" else 1)
    public = [load(path) for path in witnesses]
    for w in public:
        check_witness(w, dut)
    if dut == "lsq_wrapper":
        assert {w["query_lane"] for w in public} == {0, 1, 2}
    for name in (before, after):
        functional = load(ROOT / "results" / name / "execution/functional-coverage.json")
        for scope in ("reached", "checked"):
            group = next(g for g in functional["groups"] if g["instance"] == f"lsq.{dut}.{scope}")
            assert group["collection_complete"]
            if dut == "lsq_wrapper":
                for bin_name in ("LSQ-FORWARD.aligned", "LSQ-FORWARD.youngest", "LSQ-FORWARD.sqid", "LSQ-FORWARD.wrap"):
                    if name == after:
                        assert group["points"][0]["counts"][bin_name] > 0
            else:
                assert (group["points"][0]["counts"][scenario] > 0) == (name == after)
    _, original_dat = native("lsq-progress-regression-15", dut)
    original = point_sets(original_dat)
    overlap = {kind: dict(regression15_missing_seen_in_directed_after=len(original[kind]["missing"] & new["points"][kind]["hit"]),
                         point_set_SHA256=digest_keys(original[kind]["missing"] & new["points"][kind]["hit"])) for kind in original}
    assert old["line_all"] == new["line_all"] and old["line_hit"] <= new["line_hit"]
    report = dict(format="lsq-store-prefix-byte-evidence-v1", dut=dut, before_run=before, after_run=after,
        contract="docs/contracts/store-prefix-byte-windows.md", baseline_tests=len(old["nodes"]), after_tests=len(new["nodes"]),
        source_aggregate=old["source"]["aggregate_SHA256"], native_build_id=closure["native_build_id"], raw_nonwrapper_metrics=closure["metrics"],
        low_window_vectors=dict(before_hit=sum(p["hit"] > 0 for p in old_low.values()), after_hit=756, total=756,
            target_point_set_SHA256=digest_keys({point_key(p) for p in new_low.values()}),
            additional_vector_points_not_removed=dict(total=12, missing=sum(p["hit"] == 0 for p in boundary),
                point_set_SHA256=digest_keys({point_key(p) for p in boundary}),
                points=[dict(source=str(Path(p["f"]).relative_to(ROOT)), line=int(p["l"]), point=p["o"], hit=p["hit"]) for p in boundary],
                note="These12 native points stay in original denominators/missing inventory. No initialization or global unreachability waiver is granted by this directed check.")),
        stored_or_public_vaddr_low=addresses, regression15_gap_overlap=overlap,
        original_source_line_coverage=dict(before_hit=len(old["line_hit"]), after_hit=len(new["line_hit"]), total=len(new["line_all"]),
            newly_hit=len(new["line_hit"] - old["line_hit"]), newly_missing=0),
        witness_paths=[str(p.relative_to(ROOT)) for p in witnesses], witness_SHA256=[sha256_file(p) for p in witnesses], witnesses=public,
        verification=dict(same_source_build_and_three_point_universes=True, baseline_nodes_retained=True, no_old_hit_lost=True,
            locked_analyzer_and_fixed_original_sources=True, valid_prefix_and_byte_negative_controls_checked=True,
            real_parent_consumption_and_completion_if_applicable=True, actual_wrapper_original_UID_S3_completion_if_applicable=True,
            all_756_selected_low_vector_directions_and_512_address_bits_hit=True),
        limits="Nonfull and shifted-full legal prefix/byte complement, not all sizes/alias/cross-page/special/recovery/bus verification. Leaf bank is public input, not persistent storage; parents retain real submodules and all staged reference checks.12 vector-boundary points and all other misses stay in denominators. No directed OR or result is merged into regression15, and existing failures remain explicit.")
    write_report(ROOT / "results" / after / "store-prefix-byte-evidence-v1.json", report)
    return report


def audit_full():
    status, source = stable_run(FULL)
    assert status["manifest_tests"] == {"PASS": 903, "FAIL": 169} and status["pytest_exitstatus"] == 1
    old_cases, current = cases(PREVIOUS), cases(FULL)
    assert len(old_cases) == 1066 and len(current) == 1072
    assert all(current[node] == value for node, value in old_cases.items())
    added = set(current) - set(old_cases)
    assert len(added) == 6 and all("test_prefix_byte_windows::" in node and current[node]["outcome"] == "PASS" for node in added)
    assert failure_digest(old_cases) == failure_digest(current)
    old, new = contributors(PREVIOUS), contributors(FULL)
    assert {dut: len(nodes) for dut, nodes in new.items()} == dict(forward_module=186, physical_store_queue=69, store_queue=82, lsq_wrapper=735)
    command = load(ROOT / "results" / FULL / "command.json")["command"]
    assert command[command.index("--lsq-trace-max-mb") + 2:] == COMMAND_PATHS + ["--tb=short"]
    rows = []
    for dut in PRIMARY:
        assert set(old[dut]) <= set(new[dut])
        assert all(same_summary(item, new[dut][node]) for node, item in old[dut].items())
        before, a_dat = native(PREVIOUS, dut); after, b_dat = native(FULL, dut)
        assert before["artifact"]["build"] == after["artifact"]["build"]
        for filename, digest in after["artifact"]["build"]["files"].items():
            assert sha256_file(Path(filename)) == digest
        summary = summarize(b_dat, after["artifact"]["build"], after["artifact"])
        assert summary["raw_parser_matches_analyzer"] and summary["coverage_artifact_matches_dat"]
        a, b, metrics = point_sets(a_dat), point_sets(b_dat), {}
        for kind in a:
            assert a[kind]["all"] == b[kind]["all"] and a[kind]["hit"] <= b[kind]["hit"]
            gained = b[kind]["hit"] - a[kind]["hit"]
            metrics[kind] = dict(before_hit=len(a[kind]["hit"]), after_hit=len(b[kind]["hit"]), total=len(b[kind]["all"]),
                newly_hit=len(gained), newly_hit_SHA256=digest_keys(gained), newly_missing=0, still_missing=len(b[kind]["missing"]))
        old_lines, new_lines = source_lines(before, a_dat, dut), source_lines(after, b_dat, dut)
        assert old_lines[0] == new_lines[0] and old_lines[1] <= new_lines[1]
        vectors, boundary = low_vectors(b_dat)
        assert all(p["hit"] > 0 for p in vectors.values())
        address_target = audit_target(a_dat, b_dat, dut, "vaddr", range(4))
        paths = [p for p in (ROOT / "results" / FULL / "cases").rglob("store-prefix-byte-witness.json") if load(p)["dut"] == dut]
        assert len(paths) == (3 if dut == "lsq_wrapper" else 1)
        directed = next(load(ROOT / "results" / f"{prefix}-prefix-byte-after-01/store-prefix-byte-evidence-v1.json") for key, prefix, _, _ in PAIRS if key == dut)
        for path in paths:
            w = load(path); check_witness(w, dut)
            assert w in directed["witnesses"]
        rows.append(dict(dut=dut, original_native_inputs=len(old[dut]), current_native_inputs=len(new[dut]), metrics=metrics,
            native_build_id=after["artifact"]["build"]["build_id"], before_dat_SHA256=sha256_file(a_dat), after_dat_SHA256=sha256_file(b_dat),
            low_vectors_hit=756, low_vectors_total=756,
            stored_or_public_vaddr_low=address_target,
            original_source_line_coverage=dict(before_hit=len(old_lines[1]), after_hit=len(new_lines[1]), total=len(new_lines[0]), newly_missing=0)))
    original_actors = [ROOT / name / "actor.py" for name in ("psq", "store_queue")]
    old_streams, new_streams = journal_streams(PREVIOUS), journal_streams(FULL)
    assert len(old_streams) == 2196 and len(new_streams) == 2205
    assert old_streams.keys() <= new_streams.keys()
    assert all(new_streams[key] == value for key, value in old_streams.items())
    probe = load(ROOT / "results/store-prefix-byte-probe-01/execution/manifest.json")
    assert probe["tests"] == {"PASS": 4, "FAIL": 2} and probe["state"] == "committed"
    gate = dict(name="all_old_native_hits_retained", passed=True, status="PASS", failed_duts=[], newly_missing_toggle_points=0, required=True, waived=False)
    report = dict(format="lsq-store-prefix-contributor-regression-v1", run=FULL, baseline=PREVIOUS, status=status,
        original_nodes=1066, current_nodes=1072, added_passing_nodes=6, original_failures=169,
        failure_SHA256=failure_digest(current), source_aggregate=source["aggregate_SHA256"], rows=rows,
        coverage_monotonicity=gate, wrapper_contributors_before=732, wrapper_contributors_after=735,
        original_wrapper_public_check_actor_summaries_equal=2196,
        first_probe_checker_failures_retained=dict(run="store-prefix-byte-probe-01", tests=probe["tests"],
            reason="Generic actor assigned repeated VA consumption to the first UID; directed ordered consumer checks exact original UID bytes/fire/dequeue, without altering actors or models.",
            unchanged_generic_actor_SHA256={str(p.relative_to(ROOT)):sha256_file(p) for p in original_actors}),
        verification=dict(actual_full_same_build_contributor_execution=True, all_1066_old_nodes_and_169_failure_details_equal=True,
            all_old_primary_journal_streams_equal=True, three_point_universes_unchanged_and_old_hits_retained=True,
            all_original_wrapper_public_check_actor_streams_equal=True,
            locked_analyzer_and_artifact_hashes=True, six_real_public_witnesses_match_directed_cases=True,
            source_launch_end_equal=True, historical_probe_failures_not_deleted=True, no_cycle_JSON_or_waveforms=True),
        limits="Actual1072-node/four-build contributor rerun, not38-build acceptance or OR of datasets. All169 old failures stay explicit; regression15 raw data, counts and missing classification stay unchanged. The first probe is a retained consumer-identity checker limitation, not an RTL failure or a waived valid alias case.")
    write_report(ROOT / "results" / FULL / "store-prefix-contributor-regression-evidence-v1.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dut", choices=[p[0] for p in PAIRS])
    parser.add_argument("--directed-only", action="store_true")
    args = parser.parse_args()
    for pair in PAIRS:
        if args.dut is None or pair[0] == args.dut:
            result = audit_pair(*pair)
            print(json.dumps({k: result[k] for k in ("dut", "baseline_tests", "after_tests", "raw_nonwrapper_metrics", "regression15_gap_overlap", "verification")}, indent=2))
    if args.dut is None and not args.directed_only:
        result = audit_full()
        print(json.dumps({k: result[k] for k in ("run", "status", "rows", "verification")}, indent=2))
