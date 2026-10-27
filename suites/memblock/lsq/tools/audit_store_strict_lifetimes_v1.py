#!/usr/bin/env python3
"""Audit strict/precise public lifetimes, branch locations and retained FAILs."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from audit_checkpoint_pool_v1 import validate_run
from audit_coverage_points_v1 import records, sha256_file, summarize
from audit_expanded_regression_v1 import cases, failure_digest
from audit_failure_preservation_v1 import pytest_status
from audit_gap_closure_v1 import digest_keys, native, point_key, point_sets
from coverage_audit import lcov

ROOT = Path(__file__).resolve().parents[1]
PAIRS = (
    ("physical_store_queue", "psq-strict-lifetimes-baseline-01", "psq-strict-lifetimes-after-01", "PSQ-STRICT.lifecycle"),
    ("store_queue", "sq-strict-lifetimes-baseline-01", "sq-strict-lifetimes-after-01", "SQ-STRICT.lifecycle"),
    ("lsq_wrapper", "lsq-strict-lifetimes-baseline-01", "lsq-strict-lifetimes-after-01", "LSQ-REPLAY.strict"),
)


def load(path):
    return json.loads(path.read_text())


def strict_targets(dat):
    lines = {base + 62 * lane for base in (11330, 11340, 11342, 11344) for lane in range(3)}
    target = [p for p in records(dat) if p["t"] == "branch" and p["f"].endswith("/ForwardModule.sv")
              and int(p["l"]) in lines and p.get("o") == "cond_then"]
    assert len(target) == 12 and {int(p["l"]) for p in target} == lines
    return {point_key(p): p for p in target}


def check_witness(witness, dut):
    assert witness["dut"] == dut and len(witness["lifetimes"]) == 4
    assert witness["completed_store_uids"] == 256 and witness["checked_forward_responses"] == 36
    for gen, life in enumerate(witness["lifetimes"]):
        assert life["generation"] == gen and life["head_before"] == 64 * gen and life["head_after"] == 64 * (gen + 1)
        assert life["public_slots"] == list(range(64))
        assert life["dependency"] == {"first": bool(gen // 2), "second": bool(gen % 2), "value": 63}
        assert life["responses"] == {"strict_blocked": 3, "precise_unblocked": 3, "strict_after_STA_unblocked": 3}
        assert life["hole_STA_lane"] == gen % 2
        assert life["sbuffer_consumed_owners"] == life["normal_completions"] == 64
        if dut == "lsq_wrapper":
            assert life["matching_StoreWakeup"]
            assert life["replay_handshakes"] == life["original_feedback_completions"] == life["precise_load_completions"] == 3
            assert len(set(life["public_replay_slots"])) == 3 and all(0 <= slot < 120 for slot in life["public_replay_slots"])
    if dut == "lsq_wrapper":
        assert witness["completed_load_uids"] == 24 and witness["actual_replay_handshakes"] == 12
    assert len(witness["payload_and_completion_SHA256"]) == 64


def audit_pair(dut, before, after, scenario):
    old, new = validate_run(before, dut), validate_run(after, dut)
    assert old["source"] == new["source"] and old["meta"]["artifact"]["build"] == new["meta"]["artifact"]["build"]
    assert set(old["nodes"]) < set(new["nodes"]) and len(set(new["nodes"]) - set(old["nodes"])) == 1
    assert all(new["nodes"][node] == value for node, value in old["nodes"].items())
    closure = load(ROOT / "results" / after / f"directed-gap-closure-{dut}-v1.json")
    assert all(closure["verification"].values())
    assert closure["before_coverage_dat_SHA256"] == sha256_file(old["dat"])
    assert closure["after_coverage_dat_SHA256"] == sha256_file(new["dat"])
    reference_meta, reference_dat = native("lsq-progress-regression-15", dut)
    assert reference_meta["artifact"]["build"]["build_id"] == closure["native_build_id"]
    reference, overlap = point_sets(reference_dat), {}
    for kind in ("line", "toggle", "branch"):
        a, b = old["points"][kind], new["points"][kind]
        assert a["all"] == b["all"] == reference[kind]["all"] and a["hit"] <= b["hit"]
        assert closure["metrics"][kind]["newly_hit_SHA256"] == digest_keys(b["hit"] - a["hit"])
        hit = reference[kind]["missing"] & b["hit"]
        overlap[kind] = dict(regression15_missing_seen_in_directed_after=len(hit), point_set_SHA256=digest_keys(hit))
    assert old["line_all"] == new["line_all"] and old["line_hit"] <= new["line_hit"]
    before_targets, after_targets, regression_targets = (strict_targets(p) for p in (old["dat"], new["dat"], reference_dat))
    assert before_targets.keys() == after_targets.keys() == regression_targets.keys()
    assert all(p["hit"] > 0 for p in after_targets.values())
    expected_closed = {"physical_store_queue": 4, "store_queue": 8, "lsq_wrapper": 0}[dut]
    branch_locations = [dict(source=str(Path(p["f"]).relative_to(ROOT)), source_line=int(p["l"]),
                             point=p["o"], hierarchy=p["h"], before_hit=before_targets[key]["hit"],
                             after_hit=p["hit"], regression15_hit=regression_targets[key]["hit"])
                        for key, p in sorted(after_targets.items())]
    assert sum(p["regression15_hit"] <= 0 for p in branch_locations) == expected_closed
    assert overlap["branch"]["regression15_missing_seen_in_directed_after"] == expected_closed
    paths = list((ROOT / "results" / after / "cases").rglob("store-strict-lifetimes-witness.json"))
    assert len(paths) == 1
    witness = load(paths[0]); check_witness(witness, dut)
    for name in (before, after):
        functional = load(ROOT / "results" / name / "execution/functional-coverage.json")
        for scope in ("reached", "checked"):
            group = next(g for g in functional["groups"] if g["instance"] == f"lsq.{dut}.{scope}")
            assert group["collection_complete"]
            if dut == "lsq_wrapper":
                for bin_name in ("LSQ-FORWARD.addr_hole", "LSQ-FORWARD.sqid", "LSQ-FORWARD.wrap", "LSQ-REPLAY.strict", "LSQ-REPLAY.sq_address"):
                    if name == after:
                        assert group["points"][0]["counts"][bin_name] > 0
            else:
                assert (group["points"][0]["counts"][scenario] > 0) == (name == after)
    report = dict(format="lsq-store-strict-lifetimes-evidence-v1", dut=dut, before_run=before, after_run=after,
                  contract="docs/contracts/store-strict-wait-lifetimes.md", native_build_id=closure["native_build_id"],
                  source_aggregate=old["source"]["aggregate_SHA256"], baseline_tests=len(old["nodes"]), after_tests=len(new["nodes"]),
                  raw_nonwrapper_metrics=closure["metrics"], regression15_gap_overlap=overlap,
                  strict_branch_targets=dict(hit=12, total=12, regression15_missing_now_hit=expected_closed, locations=branch_locations),
                  original_source_line_coverage=dict(before_hit=len(old["line_hit"]), after_hit=len(new["line_hit"]), total=len(new["line_all"]),
                      newly_hit=len(new["line_hit"] - old["line_hit"]), newly_missing=0, sources=new["line_sources"]),
                  witness=str(paths[0].relative_to(ROOT)), witness_SHA256=sha256_file(paths[0]), public_witness=witness,
                  verification=dict(actual_picker_toffee_and_pinned_RTL=True, parser_matches_locked_analyzer=True,
                      same_source_build_and_point_universes=True, baseline_nodes_retained=True, no_old_hit_lost=True,
                      four_complete_dependency_identities_checked=True, precise_negative_control_and_actual_STA_release=True,
                      real_consumption_and_normal_reuse=True, wrapper_real_grant_feedback_if_applicable=True),
                  limits="This is a legal strict/precise STA-hole complement, not repair or acceptance of all strict behavior. Dependency value63/four flag generations are witnessed, not every dependency value. Wrapper uses real mixed stores/loads, Replay handshakes and same-UID feedback; it does not cover disabled-feedback/bitmap-only negatives, bus traffic or all LSQ functions. Native points and source lines stay separate, and no points/results are merged into regression15.")
    output = ROOT / "results" / after / "store-strict-lifetimes-evidence-v1.json"
    if output.exists():
        assert load(output) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: report[k] for k in ("dut", "baseline_tests", "after_tests", "raw_nonwrapper_metrics", "regression15_gap_overlap", "verification")}, indent=2))
    return report


def source_lines(meta, dat, dut):
    info = next(a for a in meta["manifest"]["artifacts"] if a["kind"] == "lcov" and Path(a["path"]) == dat.with_name("coverage.info"))
    assert sha256_file(Path(info["path"])) == info["sha256"]
    tables, all_lines, hit_lines = lcov(Path(info["path"])), set(), set()
    spec = load(ROOT / "manifest/duts.json")["duts"][dut]
    for filename, digest in load(ROOT / "rtl" / dut / "source.json")["files"].items():
        path = ROOT / "dut" / dut / (spec["export_name"] + ".v") if filename == spec["top"] + ".sv" else ROOT / "rtl" / dut / filename
        assert sha256_file(path) == digest
        table = tables.get(str(path), {})
        all_lines.update((str(path), line) for line in table)
        hit_lines.update((str(path), line) for line, count in table.items() if count > 0)
    return all_lines, hit_lines


def journal_streams(name, prefix="tests/lsq_wrapper/"):
    result = {}
    for path in (ROOT / "results" / name / "cases").rglob("*.summary.json"):
        item = load(path)
        if not item["nodeid"].startswith(prefix):
            continue
        key = (item["nodeid"], path.name)
        assert key not in result
        result[key] = (item["records"], item["serialized_bytes"], item["streamed_SHA256"])
    return result


def journal_digest(data):
    canonical = json.dumps([(key, value) for key, value in sorted(data.items())], separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def isolation_evidence():
    repeat = ("lsq-strict-lifetimes-baseline-01", "lsq-strict-baseline-repeat-01")
    preceded = ("lsq-coverage-isolation-alone-01", "lsq-coverage-isolation-preceded-01")
    result = []
    for names, expected_streams in ((repeat, 54), (preceded, 3)):
        left, right = (journal_streams(name) for name in names)
        assert len(left) == len(right) == expected_streams and left == right
        a, p = native(names[0], "lsq_wrapper")
        b, q = native(names[1], "lsq_wrapper")
        assert a["artifact"]["build"] == b["artifact"]["build"]
        for name in names:
            directory = ROOT / "results" / name
            status = pytest_status(name)
            assert status["pytest_exitstatus"] == 0 and status["state"] == "committed"
            launch, end = (load(directory / f"source-aggregate-{phase}.json") for phase in ("launch", "end"))
            assert end.pop("launch_and_end_equal") and launch == end
        assert load(ROOT / "results" / names[0] / "source-aggregate-launch.json") == load(ROOT / "results" / names[1] / "source-aggregate-launch.json")
        counts_a = {point_key(point): point["hit"] for point in records(p)}
        counts_b = {point_key(point): point["hit"] for point in records(q)}
        assert counts_a == counts_b
        result.append(dict(before=names[0], after=names[1], identical_wrapper_journal_streams=expected_streams,
                           stream_inventory_SHA256=journal_digest(left), all_native_point_counts_equal=True,
                           before_dat_SHA256=sha256_file(p), after_dat_SHA256=sha256_file(q),
                           conclusion="Controlled diagnostic did not reproduce the large directory-run coverage loss; no root cause or initialization waiver is established."))
    return result


def audit_directory_rerun():
    name = "store-strict-directory-regression-01"
    directory = ROOT / "results" / name
    status = pytest_status(name)
    assert status["state"] == "committed" and status["coverage_complete"] and status["cleanup_complete"]
    assert status["pytest_exitstatus"] == 1 and status["errors"] == status["skipped"] == 0
    reference = cases("lsq-progress-regression-15")
    prefixes = ("tests.forward.", "tests.psq.", "tests.store_queue.", "tests.lsq_wrapper.")
    original = {node: value for node, value in reference.items() if node.startswith(prefixes)}
    current = cases(name)
    assert len(original) == 1018 and len(current) == 1025
    assert all(current[node] == value for node, value in original.items())
    added = set(current) - set(original)
    assert len(added) == 7 and all(current[node]["outcome"] == "PASS" for node in added)
    expected_classes = {"tests.forward.test_pool_payload", "tests.psq.test_pool_payload", "tests.store_queue.test_pool_payload",
                        "tests.psq.test_strict_lifetimes", "tests.store_queue.test_strict_lifetimes",
                        "tests.lsq_wrapper.test_store_strict_lifetimes", "tests.lsq_wrapper.test_checkpoint_pool"}
    assert {node.split("::")[0] for node in added} == expected_classes
    assert status["manifest_tests"] == {"PASS": 868, "FAIL": 157}
    assert failure_digest(original) == failure_digest(current)
    launch, end = (load(directory / f"source-aggregate-{phase}.json") for phase in ("launch", "end"))
    assert end.pop("launch_and_end_equal") and launch == end
    for suffix in ("*.jsonl", "*.fst", "*.vcd"):
        assert not list((directory / "cases").rglob(suffix))
    rows = []
    for dut in ("forward_module", "physical_store_queue", "store_queue", "lsq_wrapper"):
        before, old_dat = native("lsq-progress-regression-15", dut)
        after, new_dat = native(name, dut)
        assert before["artifact"]["build"] == after["artifact"]["build"]
        for filename, digest in after["artifact"]["build"]["files"].items():
            assert sha256_file(Path(filename)) == digest
        summary = summarize(new_dat, after["artifact"]["build"], after["artifact"])
        assert summary["raw_parser_matches_analyzer"] and summary["coverage_artifact_matches_dat"]
        a, b, metrics = point_sets(old_dat), point_sets(new_dat), {}
        for kind in ("line", "toggle", "branch"):
            assert a[kind]["all"] == b[kind]["all"]
            gained = b[kind]["hit"] - a[kind]["hit"]
            lost = a[kind]["hit"] - b[kind]["hit"]
            metrics[kind] = dict(before_hit=len(a[kind]["hit"]), after_hit=len(b[kind]["hit"]), total=len(b[kind]["all"]),
                                 newly_hit=len(gained), newly_hit_SHA256=digest_keys(gained), newly_missing=len(lost),
                                 newly_missing_SHA256=digest_keys(lost),
                                 still_missing=len(b[kind]["missing"]))
        old_lines, new_lines = source_lines(before, old_dat, dut), source_lines(after, new_dat, dut)
        assert old_lines[0] == new_lines[0] and old_lines[1] <= new_lines[1]
        witness_path = None
        if dut != "forward_module":
            matches = [p for p in (directory / "cases").rglob("store-strict-lifetimes-witness.json") if load(p)["dut"] == dut]
            assert len(matches) == 1
            witness_path = matches[0]
            check_witness(load(witness_path), dut)
            directed = next(pair[2] for pair in PAIRS if pair[0] == dut)
            assert load(witness_path) == load(ROOT / "results" / directed / "store-strict-lifetimes-evidence-v1.json")["public_witness"]
            assert all(p["hit"] > 0 for p in strict_targets(new_dat).values())
        loss = a["toggle"]["hit"] - b["toggle"]["hit"]
        lost_points = [point for point in records(old_dat) if point_key(point) in loss]
        loss_details = None
        if loss:
            # Preserve the failed gate and point-set identity. These points are
            # NOT excused as initialization or don't-care without more proof.
            by_source = Counter(str(Path(point["f"]).relative_to(ROOT)) for point in lost_points)
            old_hit_counts = Counter(point["hit"] for point in lost_points)
            loss_details = dict(status="OPEN_UNEXPLAINED_NATIVE_TOGGLE_LOSS", count=len(loss),
                point_set_SHA256=digest_keys(loss), by_source=dict(sorted(by_source.items())),
                old_hit_count_histogram={str(key): value for key, value in sorted(old_hit_counts.items())},
                compact_samples=[dict(source=str(Path(point["f"]).relative_to(ROOT)), line=int(point["l"]),
                    point=point["o"], hierarchy=point["h"], old_hit=point["hit"], current_hit=0) for point in lost_points[:12]],
                classification="unexplained_run_context_difference; requires isolated per-case native evidence, not a feature waiver",
                full_point_list_persisted=False)
        rows.append(dict(dut=dut, native_build_id=after["artifact"]["build"]["build_id"],
                         before_coverage_dat_SHA256=sha256_file(old_dat), after_coverage_dat_SHA256=sha256_file(new_dat),
                         metrics=metrics, original_source_line_coverage=dict(before_hit=len(old_lines[1]), after_hit=len(new_lines[1]),
                             total=len(new_lines[0]), newly_hit=len(new_lines[1] - old_lines[1]), newly_missing=0),
                         strict_witness=str(witness_path.relative_to(ROOT)) if witness_path else None,
                         old_hits_retained=all(metric["newly_missing"] == 0 for metric in metrics.values()),
                         open_toggle_loss=loss_details))
    old_streams, new_streams = journal_streams("lsq-progress-regression-15"), journal_streams(name)
    assert len(old_streams) == 2067 and len({key[0] for key in old_streams}) == 689
    assert old_streams.keys() <= new_streams.keys()
    assert all(new_streams[key] == value for key, value in old_streams.items())
    matching_streams = {key: new_streams[key] for key in old_streams}
    monotonic = all(row["old_hits_retained"] for row in rows)
    gate = dict(name="all_old_native_hits_retained", passed=monotonic,
                status="PASS" if monotonic else "FAILED_OPEN",
                failed_duts=[row["dut"] for row in rows if not row["old_hits_retained"]],
                newly_missing_toggle_points=sum(row["metrics"]["toggle"]["newly_missing"] for row in rows),
                required=True, waived=False)
    report = dict(format="lsq-store-strict-directory-regression-v1", run=name, baseline="lsq-progress-regression-15", status=status,
                  original_nodes=1018, added_passing_nodes=7, added_nodes=sorted(added), original_failures=157,
                  failure_SHA256=failure_digest(current), source_aggregate=launch["aggregate_SHA256"], rows=rows,
                  coverage_monotonicity=gate,
                  wrapper_checked_stream_identity=dict(original_nodes=689, matching_journal_summaries=2067,
                      original_stream_inventory_SHA256=journal_digest(old_streams), current_stream_inventory_SHA256=journal_digest(matching_streams),
                      conclusion="All retained public/check/actor stream digests, record and byte counts match. This does not establish identical internal trajectories or explain native coverage loss."),
                  controlled_diagnostics=isolation_evidence(), root_cause="NOT_ESTABLISHED",
                  verification=dict(all_original_normalized_outcomes_and_failure_details_equal=True, actual_fresh_directory_execution=True,
                      artifacts_and_pinned_original_RTL_hashes=True, raw_parser_matches_locked_analyzer=True,
                      same_native_builds_and_point_universes=True, exact_coverage_deltas_including_old_hit_losses=True,
                      three_public_strict_witnesses_equal_directed_cases=True, source_launch_end_equal=True,
                      no_cycle_JSON_or_waveforms=True),
                  limits="Actual four-directory/four-build rerun, not all 38 builds, coverage OR or whole-LSQ acceptance. The required no-old-hit-loss gate is explicitly FAILED_OPEN when losses exist; a net increase or matching journals does not waive it or make initialization the cause. All157 FAILs stay explicit, and seven added passes do not cancel them. Regression15 dat, counts and missing inventory stay immutable. Remaining unhit points, parent semantics and full target gates remain open.")
    output = directory / "store-strict-regression-evidence-v1.json"
    if output.exists():
        assert load(output) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: report[k] for k in ("run", "status", "original_nodes", "added_passing_nodes", "rows", "coverage_monotonicity", "verification")}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dut", choices=[pair[0] for pair in PAIRS])
    parser.add_argument("--verify-historical-artifacts-only", action="store_true",
                        help="Verify immutable historical evidence, retaining its failed gate; does not certify runtime-gate passage.")
    args = parser.parse_args()
    for pair in PAIRS:
        if args.dut is None or args.dut == pair[0]:
            audit_pair(*pair)
    if args.dut is None:
        report = audit_directory_rerun()
        if not report["coverage_monotonicity"]["passed"] and not args.verify_historical_artifacts_only:
            raise SystemExit(1)
