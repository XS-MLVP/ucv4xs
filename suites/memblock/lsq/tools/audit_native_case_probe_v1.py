#!/usr/bin/env python3
"""Independently verify compact per-case native exports and managed merging."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from audit_coverage_points_v1 import records, sha256_file, summarize
from audit_expanded_regression_v1 import cases
from audit_failure_preservation_v1 import pytest_status
from audit_gap_closure_v1 import digest_keys, native, point_key, point_sets


def load(path):
    return json.loads(path.read_text())


def stable_run(name):
    directory = ROOT / "results" / name
    status = pytest_status(name)
    assert status["state"] == "committed" and status["coverage_complete"] and status["cleanup_complete"]
    assert status["errors"] == status["skipped"] == 0
    launch, end = (load(directory / f"source-aggregate-{phase}.json") for phase in ("launch", "end"))
    assert end.pop("launch_and_end_equal") and launch == end
    for pattern in ("*.jsonl", "*.fst", "*.vcd"):
        assert not list((directory / "cases").rglob(pattern))
    assert not (directory / "verification-source").exists()
    return status, launch


def target_keys():
    old_meta, old = native("lsq-progress-regression-15", "lsq_wrapper")
    new_meta, new = native("store-strict-directory-regression-01", "lsq_wrapper")
    assert old_meta["artifact"]["build"] == new_meta["artifact"]["build"]
    assert sha256_file(old) == old_meta["artifact"]["sha256"] and sha256_file(new) == new_meta["artifact"]["sha256"]
    a, b = point_sets(old), point_sets(new)
    keys = tuple(sorted(a["toggle"]["hit"] - b["toggle"]["hit"]))
    assert len(keys) == 2125 and digest_keys(set(keys)) == "02745152ec8d03a8b3fc0fe1bd36d8db6a3de8adc33705aae55dda486b2bf03d"
    return keys, old_meta["artifact"]["build"]


def journal_streams(name):
    result = {}
    filenames = {"lsq_wrapper.summary.json", "lsq_checks.summary.json", "lsq_actor.summary.json",
                 "lsq_probe.summary.json", "lsq_probe_checks.summary.json", "lsq_probe_actor.summary.json"}
    for path in (ROOT / "results" / name / "cases").rglob("*.summary.json"):
        item = load(path)
        if path.name in filenames:
            result[(item["nodeid"], path.name)] = (item["records"], item["serialized_bytes"], item["streamed_SHA256"])
    return result


def xml_node(node):
    path, suffix = node.split("::", 1)
    assert path.endswith(".py")
    return path[:-3].replace("/", ".") + "::" + suffix


def independent_metrics(points):
    result = {scope: {kind: dict(hit=0, total=0, count_sum=0) for kind in ("line", "toggle", "branch")}
              for scope in ("raw_all", "original_nonwrapper")}
    for point in points:
        scopes = ("raw_all",) if point["f"].endswith("_top.sv") else ("raw_all", "original_nonwrapper")
        for scope in scopes:
            item = result[scope][point["t"]]
            item["hit"] += int(point["hit"] > 0)
            item["total"] += 1
            item["count_sum"] += point["hit"]
    return result


def audit(name):
    status, source = stable_run(name)
    meta, dat = native(name, "lsq_wrapper")
    assert sha256_file(dat) == meta["artifact"]["sha256"]
    keys, build = target_keys()
    assert meta["artifact"]["build"] == build
    for path, digest in build["files"].items():
        assert sha256_file(Path(path)) == digest
    summary = summarize(dat, build, meta["artifact"])
    assert summary["raw_parser_matches_analyzer"] and summary["coverage_artifact_matches_dat"]
    points, origin = records(dat), None
    metrics = independent_metrics(points)
    index = {key: bit for bit, key in enumerate(keys)}
    actual_bitmap = actual_sum = 0
    for point in points:
        bit = index.get(point_key(point))
        if bit is not None:
            actual_sum += point["hit"]
            if point["hit"] > 0:
                actual_bitmap |= 1 << bit
    current, original = cases(name), cases("lsq-progress-regression-15")
    assert set(current) <= set(original) and all(current[node] == original[node] for node in current)
    new_streams = journal_streams(name)
    wrapper_nodes = {xml_node(node) for node, filename in new_streams
                     if filename in ("lsq_wrapper.summary.json", "lsq_probe.summary.json")}
    paths = sorted((ROOT / "results" / name / "cases").rglob("native-case-coverage-summary.json"))
    assert paths and len(paths) == len(wrapper_nodes)
    observed_nodes, union, total_counts, rows = set(), 0, 0, []
    sums = {scope: Counter() for scope in metrics}
    implementation = None
    for path in paths:
        case = load(path)
        node = xml_node(case["nodeid"])
        assert node in wrapper_nodes and node not in observed_nodes
        observed_nodes.add(node)
        assert case["format"] == "lsq-native-case-coverage-probe-v1"
        assert case["phase"] == "after fixture Finish, before original NativeCollector.end_case/merge/cleanup"
        if origin is None:
            origin, implementation = case["target_origin"], case["implementation_SHA256"]
        assert origin == case["target_origin"] and implementation == case["implementation_SHA256"]
        assert origin["target_count"] == len(keys) and origin["target_set_SHA256"] == digest_keys(set(keys))
        assert implementation["observer"] == sha256_file(ROOT / "native_case_probe.py")
        assert len(case["native_exports"]) == 1
        export = case["native_exports"][0]
        assert export["native_build_id"] == build["build_id"]
        bitmap = int(export["target_hit_bitmap_hex"], 16)
        assert bitmap < 1 << len(keys) and bitmap.bit_count() == export["target_hit_count"]
        union |= bitmap
        total_counts += export["target_counter_sum"]
        for scope, by_kind in export["metrics"].items():
            for kind, metric in by_kind.items():
                assert metric["total"] == metrics[scope][kind]["total"]
                assert 0 <= metric["hit"] <= metric["total"]
                sums[scope][kind] += metric["count_sum"]
        rows.append(dict(node=node, outcome=current[node]["outcome"], target_hit_count=bitmap.bit_count(),
                         target_counter_sum=export["target_counter_sum"],
                         summary=str(path.relative_to(ROOT)), summary_SHA256=sha256_file(path)))
    assert observed_nodes == wrapper_nodes and union == actual_bitmap and total_counts == actual_sum
    for scope, by_kind in metrics.items():
        for kind, metric in by_kind.items():
            assert sums[scope][kind] == metric["count_sum"], (scope, kind, sums[scope][kind], metric)
    old_streams = journal_streams("lsq-progress-regression-15")
    assert new_streams.keys() <= old_streams.keys()
    assert all(old_streams[key] == value for key, value in new_streams.items())
    hit_keys = {keys[bit] for bit in range(len(keys)) if union >> bit & 1}
    report = dict(format="lsq-native-case-probe-audit-v1", run=name, status=status, source_aggregate=source["aggregate_SHA256"],
                  native_build_id=build["build_id"], coverage_dat_SHA256=sha256_file(dat), wrapper_nodes=len(wrapper_nodes), rows=rows,
                  target_origin=origin, observed_target_hit_count=union.bit_count(), target_total=len(keys),
                  observed_target_point_set_SHA256=digest_keys(hit_keys), target_counter_sum=total_counts,
                  observed_target_by_source=dict(sorted(Counter(str(Path(key[0]).relative_to(ROOT)) for key in hit_keys).items())),
                  original_public_journal_summaries_equal=len(new_streams),
                  verification=dict(original_node_outcomes_and_failure_details_equal=True, source_launch_end_equal=True,
                      pinned_native_build_and_artifact_hashes=True, independent_parser_matches_locked_analyzer=True,
                      one_summary_per_original_wrapper_node=True, target_case_union_equals_actual_native_union=True,
                      all_three_metric_counter_sums_conserved=True, original_public_check_actor_streams_equal=True),
                  limits="Read-only native-export localization, not a new feature test, original full-regression coverage merge or initialization waiver. Unobserved/changed internal trajectories and the original failed monotonicity gate remain open until specifically proven.")
    output = ROOT / "results" / name / "native-case-probe-audit-v1.json"
    if output.exists():
        assert load(output) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: report[key] for key in ("run", "wrapper_nodes", "observed_target_hit_count", "target_total", "observed_target_by_source", "verification")}, indent=2))
    return report


def control():
    before, after = "lsq-native-case-control-off-01", "lsq-native-case-control-on-01"
    a, source_a = stable_run(before); b, source_b = stable_run(after)
    assert cases(before) == cases(after) and source_a == source_b
    a_meta, p = native(before, "lsq_wrapper"); b_meta, q = native(after, "lsq_wrapper")
    assert a_meta["artifact"]["build"] == b_meta["artifact"]["build"]
    assert {point_key(x): x["hit"] for x in records(p)} == {point_key(x): x["hit"] for x in records(q)}
    assert journal_streams(before) == journal_streams(after)
    diagnostic = audit(after)
    report = dict(format="lsq-native-case-probe-control-v1", before_run=before, after_run=after,
                  before_tests=a["manifest_tests"], after_tests=b["manifest_tests"],
                  source_aggregate=source_a["aggregate_SHA256"], native_build_id=diagnostic["native_build_id"],
                  before_dat_SHA256=sha256_file(p), after_dat_SHA256=sha256_file(q),
                  verification=dict(same_source_build_and_original_node=True, all_native_point_counts_equal=True,
                      all_public_check_actor_streams_equal=True, observer_does_not_replace_export_or_merge=True),
                  limits="The observer is nonperturbing for this concrete control only; this is not a blanket guarantee or an explanation of the 2125-point loss.")
    output = ROOT / "results" / after / "native-case-probe-control-v1.json"
    if output.exists():
        assert load(output) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*")
    parser.add_argument("--control", action="store_true")
    args = parser.parse_args()
    if args.control:
        control()
    for name in args.names:
        audit(name)
