#!/usr/bin/env python3
"""Rebuild native metrics, full-width pool targets and compact public witnesses."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from audit_checkpoint_pool_v1 import validate_run
from audit_coverage_points_v1 import records, sha256_file, summarize
from audit_expanded_regression_v1 import cases, failure_digest
from audit_failure_preservation_v1 import pytest_status
from audit_gap_closure_v1 import digest_keys, native, point_sets
from coverage_audit import lcov

ROOT = Path(__file__).resolve().parents[1]
CASE = "test_all_slots_full_width_high_low_payload_lifetimes"
PAIRS = (
    ("forward_module", "forward-payload-pool-baseline-02", "forward-payload-pool-after-02", "FWD-PAYLOAD.pool"),
    ("physical_store_queue", "psq-payload-pool-baseline-02", "psq-payload-pool-after-02", "PSQ-PAYLOAD.pool"),
    ("store_queue", "sq-payload-pool-baseline-02", "sq-payload-pool-after-02", "SQ-PAYLOAD.pool"),
)


def load(path):
    return json.loads(path.read_text())


def expected_payload(generation, slot):
    # Independent reconstruction, not imported from the stimulus/oracle helper.
    high = generation in (0, 2)
    va = ((1 << 50) - 1048576 if high else 2097152) + 16 * slot
    pa = ((1 << 48) - 1048576 if high else 16777216) + 16 * slot
    pattern = sum(((19 * slot + 31 * byte) % 256) << (8 * byte) for byte in range(16))
    return [va, pa, [(1 << 128) - 1, pattern, ((1 << 128) - 1) ^ pattern, 0][generation]]


def audit_target(old_dat, new_dat, dut, field, bits):
    prefix = "io_dataEntriesIn" if dut == "forward_module" else "dataEntries"
    regex = re.compile(rf"{prefix}_(\d+)_{field}\[(\d+)\]:(0->1|1->0)")
    inventories = []
    for dat in (old_dat, new_dat):
        target, identities = [], []
        for point in records(dat):
            if point["t"] != "toggle" or point["f"].endswith("_top.sv"):
                continue
            match = regex.fullmatch(point.get("o", ""))
            if match and int(match[2]) in bits:
                target.append(point)
                identities.append((int(match[1]), int(match[2]), match[3]))
        expected = {(slot, bit, direction) for slot in range(64) for bit in bits for direction in ("0->1", "1->0")}
        assert len(target) == len(expected) and set(identities) == expected
        inventories.append(target)
    old, new = inventories
    assert all(p["hit"] > 0 for p in new), (dut, field)
    assert len({p["f"] for p in new}) == 1
    return dict(field=f"{prefix}_<slot>_{field}", bits=list(bits), slots=64,
                before_hit=sum(p["hit"] > 0 for p in old), after_hit=len(new), total=len(new),
                both_directions=True, source=str(Path(new[0]["f"]).relative_to(ROOT)),
                declaration_line_min=min(int(p["l"]) for p in new), declaration_line_max=max(int(p["l"]) for p in new),
                storage_scope="public input only, not persistent storage" if dut == "forward_module" else "actual retained PSQ dataEntries registers")


def audit_pair(dut, before, after, scenario):
    old, new = validate_run(before, dut), validate_run(after, dut)
    assert old["source"] == new["source"]
    assert old["meta"]["artifact"]["build"] == new["meta"]["artifact"]["build"]
    assert set(old["nodes"]) < set(new["nodes"])
    added = set(new["nodes"]) - set(old["nodes"])
    assert len(added) == 1 and ("::" + CASE) in next(iter(added))
    assert all(new["nodes"][node] == outcome for node, outcome in old["nodes"].items())
    closure_path = ROOT / "results" / after / f"directed-gap-closure-{dut}-v1.json"
    closure = load(closure_path)
    assert all(closure["verification"].values())
    assert closure["before_coverage_dat_SHA256"] == sha256_file(old["dat"])
    assert closure["after_coverage_dat_SHA256"] == sha256_file(new["dat"])
    for kind in ("line", "toggle", "branch"):
        a, b, metric = old["points"][kind], new["points"][kind], closure["metrics"][kind]
        assert a["all"] == b["all"] and a["hit"] <= b["hit"]
        assert metric["before_hit"] == len(a["hit"]) and metric["after_hit"] == len(b["hit"])
        assert metric["newly_hit_SHA256"] == digest_keys(b["hit"] - a["hit"])
    assert old["line_all"] == new["line_all"] and old["line_hit"] <= new["line_hit"]
    paths = list((ROOT / "results" / after / "cases").rglob("store-payload-pool-witness.json"))
    assert len(paths) == 1
    witness = load(paths[0])
    assert witness["dut"] == dut and len(witness["lifetimes"]) == 4
    for generation, life in enumerate(witness["lifetimes"]):
        assert life["generation"] == generation and life["public_slots"] == list(range(64))
        assert life["head_before"] == generation * 64 and life["head_after"] == (generation + 1) * 64
        assert life["checked_three_lane_responses"] == 192
        assert life["first_payload"] == expected_payload(generation, 0)
        assert life["last_payload"] == expected_payload(generation, 63)
        if dut != "forward_module":
            assert life["written_owners"] == life["sbuffer_consumed_owners"] == life["normal_completions"] == 64
    assert witness["checked_three_lane_responses"] == 768
    expected_uids = 768 if dut == "forward_module" else 256
    assert witness["distinct_uids"] == witness["completed_owners"] == expected_uids
    if dut != "forward_module":
        assert witness["sbuffer_consumed_owners"] == 256
    assert len(witness["payload_and_consumption_SHA256"]) == 64
    targets = dict(
        full_128bit_data=audit_target(old["dat"], new["dat"], dut, "data", range(128)),
        virtual_address_high=audit_target(old["dat"], new["dat"], dut, "vaddr", range(25, 50)),
        physical_page_high=audit_target(old["dat"], new["dat"], dut, "paddrHigh", range(13, 36)),
    )
    for name in (before, after):
        functional = load(ROOT / "results" / name / "execution/functional-coverage.json")
        for scope in ("reached", "checked"):
            group = next(g for g in functional["groups"] if g["instance"] == f"lsq.{dut}.{scope}")
            assert group["collection_complete"]
            assert (group["points"][0]["counts"][scenario] > 0) == (name == after)
    reference_meta, reference_dat = native("lsq-progress-regression-15", dut)
    assert reference_meta["artifact"]["build"]["build_id"] == closure["native_build_id"]
    reference, overlap = point_sets(reference_dat), {}
    for kind in ("line", "toggle", "branch"):
        assert reference[kind]["all"] == new["points"][kind]["all"]
        hit = reference[kind]["missing"] & new["points"][kind]["hit"]
        overlap[kind] = dict(regression15_missing_seen_in_directed_after=len(hit), point_set_SHA256=digest_keys(hit))
    report = dict(format="lsq-store-payload-pool-evidence-v1", dut=dut, before_run=before, after_run=after,
                  contract="docs/contracts/store-payload-pool.md", source_aggregate=old["source"]["aggregate_SHA256"],
                  native_build_id=closure["native_build_id"], baseline_tests=len(old["nodes"]), after_tests=len(new["nodes"]),
                  raw_nonwrapper_metrics=closure["metrics"], target_domains=targets,
                  original_source_line_coverage=dict(before_hit=len(old["line_hit"]), after_hit=len(new["line_hit"]),
                      total=len(new["line_all"]), newly_hit=len(new["line_hit"] - old["line_hit"]), newly_missing=0,
                      source_scope="pinned original DUT closure, not Picker wrapper", sources=new["line_sources"]),
                  witness_path=str(paths[0].relative_to(ROOT)), witness_SHA256=sha256_file(paths[0]), witness=witness,
                  regression15_gap_overlap=overlap,
                  verification=dict(artifact_and_pinned_source_hashes=True, parser_matches_locked_analyzer=True,
                      same_source_and_build=True, baseline_nodes_retained=True, no_new_missing=True,
                      four_normal_lifetimes_publicly_checked=True, full_data_and_high_address_target_points_hit=True,
                      semantic_bins_checked=True),
                  limits="Directed complements stay separate from regression15 and other builds. Forward target data points are public inputs, not registers. Parent targets are real retained registers with real STA/STD, S2 and Sbuffer/dequeue witnesses. High address stimulus is legal at the retained LSQ boundary, not a claim of integrated PMP/translation/fabric acceptance. Other payload fields, alias/cross-word/special/exception/cancel semantics and whole Wrapper remain open; raw line points are distinct from LCOV source lines.")
    output = ROOT / "results" / after / "store-payload-pool-evidence-v1.json"
    if output.exists():
        assert load(output) == report, "immutable pool evidence differs"
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: report[key] for key in ("dut", "baseline_tests", "after_tests", "target_domains", "original_source_line_coverage", "regression15_gap_overlap", "verification")}, indent=2))
    return report


def audit_directory_rerun():
    """Actual whole-directory execution, not an OR/merge of directed datasets."""
    name = "store-payload-failure-retention-01"
    directory = ROOT / "results" / name
    status = pytest_status(name)
    assert status["state"] == "committed" and status["coverage_complete"] and status["cleanup_complete"]
    assert status["manifest_tests"] == {"PASS": 268, "FAIL": 64} and status["pytest_exitstatus"] == 1
    assert status["errors"] == status["skipped"] == 0
    old_cases, new_cases = cases("lsq-progress-regression-15"), cases(name)
    original = {node: value for node, value in old_cases.items() if node.startswith(("tests.forward.", "tests.psq.", "tests.store_queue."))}
    assert len(original) == 329 and len(new_cases) == 332
    assert all(new_cases[node] == value for node, value in original.items())
    assert failure_digest(original) == failure_digest(new_cases)
    assert len(set(new_cases) - set(original)) == 3
    launch, end = (load(directory / f"source-aggregate-{phase}.json") for phase in ("launch", "end"))
    assert end.pop("launch_and_end_equal") and launch == end
    policy = load(directory / "trace-policy.json")
    assert not policy["per_cycle_JSON"] and not policy["waveforms"]
    for suffix in ("*.jsonl", "*.fst", "*.vcd"):
        assert not list((directory / "cases").rglob(suffix))
    rows = []
    for dut, before, after, scenario in PAIRS:
        old_meta, old_dat = native("lsq-progress-regression-15", dut)
        new_meta, new_dat = native(name, dut)
        assert old_meta["artifact"]["build"] == new_meta["artifact"]["build"]
        for filename, digest in new_meta["artifact"]["build"]["files"].items():
            assert sha256_file(Path(filename)) == digest
        analyzer = summarize(new_dat, new_meta["artifact"]["build"], new_meta["artifact"])
        assert analyzer["raw_parser_matches_analyzer"] and analyzer["coverage_artifact_matches_dat"]
        a, b, metrics = point_sets(old_dat), point_sets(new_dat), {}
        for kind in ("line", "toggle", "branch"):
            assert a[kind]["all"] == b[kind]["all"] and a[kind]["hit"] <= b[kind]["hit"]
            gained = b[kind]["hit"] - a[kind]["hit"]
            metrics[kind] = dict(before_hit=len(a[kind]["hit"]), after_hit=len(b[kind]["hit"]),
                                 total=len(b[kind]["all"]), newly_hit=len(gained), newly_hit_SHA256=digest_keys(gained),
                                 newly_missing=0, still_missing=len(b[kind]["missing"]))
        directed = load(ROOT / "results" / after / "store-payload-pool-evidence-v1.json")
        witnesses = [path for path in (directory / "cases").rglob("store-payload-pool-witness.json") if load(path)["dut"] == dut]
        assert len(witnesses) == 1 and load(witnesses[0]) == directed["witness"]
        # Keep LCOV source-line domains separate from raw line point domains.
        spec = load(ROOT / "manifest/duts.json")["duts"][dut]
        pinned = load(ROOT / "rtl" / dut / "source.json")["files"]
        old_info = next(x for x in old_meta["manifest"]["artifacts"] if x["kind"] == "lcov" and Path(x["path"]) == old_dat.with_name("coverage.info"))
        new_info = next(x for x in new_meta["manifest"]["artifacts"] if x["kind"] == "lcov" and Path(x["path"]) == new_dat.with_name("coverage.info"))
        line_sets = []
        for info in (old_info, new_info):
            assert sha256_file(Path(info["path"])) == info["sha256"]
            tables, all_lines, hit_lines = lcov(Path(info["path"])), set(), set()
            for filename, digest in pinned.items():
                path = ROOT / "dut" / dut / (spec["export_name"] + ".v") if filename == spec["top"] + ".sv" else ROOT / "rtl" / dut / filename
                assert sha256_file(path) == digest
                table = tables.get(str(path), {})
                all_lines.update((str(path), line) for line in table)
                hit_lines.update((str(path), line) for line, count in table.items() if count > 0)
            line_sets.append((all_lines, hit_lines))
        assert line_sets[0][0] == line_sets[1][0] and line_sets[0][1] <= line_sets[1][1]
        rows.append(dict(dut=dut, native_build_id=new_meta["artifact"]["build"]["build_id"],
                         before_coverage_dat_SHA256=sha256_file(old_dat), after_coverage_dat_SHA256=sha256_file(new_dat),
                         metrics=metrics, original_source_line_coverage=dict(before_hit=len(line_sets[0][1]), after_hit=len(line_sets[1][1]),
                             total=len(line_sets[1][0]), newly_hit=len(line_sets[1][1] - line_sets[0][1]), newly_missing=0),
                         target_data_points=audit_target(old_dat, new_dat, dut, "data", range(128)),
                         witness=str(witnesses[0].relative_to(ROOT)), witness_SHA256=sha256_file(witnesses[0])))
    report = dict(format="lsq-store-payload-directory-regression-v1", run=name, baseline="lsq-progress-regression-15",
                  status=status, original_nodes=329, added_passing_nodes=3, original_failures=64,
                  failure_SHA256=failure_digest(new_cases), source_aggregate=launch["aggregate_SHA256"], rows=rows,
                  verification=dict(all_original_outcomes_and_normalized_failure_details_equal=True,
                      actual_fresh_execution_not_coverage_merge=True, artifact_and_pinned_RTL_hashes=True,
                      raw_parser_matches_locked_analyzer=True, same_native_builds_and_point_universes=True,
                      no_old_hit_lost=True, three_pool_witnesses_equal_directed_executions=True,
                      source_launch_end_equal=True, no_cycle_JSON_or_waveforms=True),
                  limits="This is an actual three-directory/three-build rerun with 64 FAILs, not whole LSQ acceptance. Native totals stay per DUT; metrics are not merged into regression15. No regression15 missing branch point was hit. Other DUTs/parents and the complete 38-build regression retain their original results and open work.")
    output = directory / "store-payload-regression-evidence-v1.json"
    if output.exists():
        assert load(output) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(dict(run=name, original_nodes=329, added_passing_nodes=3, tests=status["manifest_tests"],
                         rows=[dict(dut=r["dut"], metrics=r["metrics"], source_lines=r["original_source_line_coverage"]) for r in rows],
                         verification=report["verification"]), indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dut", choices=[pair[0] for pair in PAIRS])
    args = parser.parse_args()
    for pair in PAIRS:
        if args.dut is None or args.dut == pair[0]:
            audit_pair(*pair)
    if args.dut is None:
        audit_directory_rerun()
