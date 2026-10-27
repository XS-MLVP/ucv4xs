#!/usr/bin/env python3
"""Validate checkpoint pool witnesses against actual native/LCOV artifacts."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from audit_coverage_points_v1 import records, sha256_file, summarize
from audit_gap_closure_v1 import digest_keys, native, point_sets
from coverage_audit import lcov

ROOT = Path(__file__).resolve().parents[1]
PAIRS = (
    ("load_queue_replay", "replay-checkpoint-pool-baseline-01", "replay-checkpoint-pool-after-01",
     "test_checkpoint_high_low_lifetimes_at_every_public_replay_slot",
     ("LRQ-PAYLOAD.pool_checkpoint", "LRQ-RECYCLE.public_slots")),
    ("load_queue", "lq-checkpoint-pool-baseline-01", "lq-checkpoint-pool-after-01",
     "test_real_parent_checkpoint_high_low_pool_reuse", ("LQ-REPLAY.checkpoint_pool",)),
    ("lsq_wrapper", "lsq-checkpoint-pool-baseline-01", "lsq-checkpoint-pool-after-01",
     "test_real_wrapper_checkpoint_high_low_pool_reuse", ("LSQ-REPLAY.capacity",)),
)


def load(path):
    return json.loads(path.read_text())


def junit(path):
    result = {}
    for case in ET.parse(path).getroot().iter("testcase"):
        node = f"{case.get('classname')}::{case.get('name')}"
        assert node not in result, node
        outcome = next((tag.upper() for tag in ("failure", "error", "skipped") if case.find(tag) is not None), "PASS")
        result[node] = outcome
    return result


def validate_run(name, dut):
    directory = ROOT / "results" / name
    meta, dat = native(name, dut)
    manifest = meta["manifest"]
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    assert manifest["pytest_exitstatus"] == 0
    nodes = junit(directory / "pytest.xml")
    assert Counter(nodes.values()) == Counter(manifest["tests"]) and set(nodes.values()) == {"PASS"}
    for artifact in manifest["artifacts"]:
        assert sha256_file(Path(artifact["path"])) == artifact["sha256"], artifact["path"]
    for filename, digest in meta["artifact"]["build"]["files"].items():
        assert sha256_file(Path(filename)) == digest, filename
    launch, end = (load(directory / f"source-aggregate-{phase}.json") for phase in ("launch", "end"))
    assert end["launch_and_end_equal"] and launch["aggregate_SHA256"] == end["aggregate_SHA256"]
    assert launch["file_count"] == end["file_count"]
    assert not list((directory / "cases").rglob("*.jsonl"))
    assert not any((directory / "cases").rglob("*.fst")) and not any((directory / "cases").rglob("*.vcd"))
    # Cross-check all raw metrics, including wrapper, with the locked analyzer.
    analyzer = summarize(dat, meta["artifact"]["build"], meta["artifact"])
    assert analyzer["raw_parser_matches_analyzer"] and analyzer["coverage_artifact_matches_dat"]

    spec = load(ROOT / "manifest/duts.json")["duts"][dut]
    pinned = load(ROOT / "rtl" / dut / "source.json")["files"]
    info = next(a for a in manifest["artifacts"] if a["kind"] == "lcov")
    tables, lines, hit_lines, line_sources = lcov(Path(info["path"])), set(), set(), []
    for source, expected_hash in pinned.items():
        path = ROOT / "dut" / dut / (spec["export_name"] + ".v") if source == spec["top"] + ".sv" else ROOT / "rtl" / dut / source
        assert sha256_file(path) == expected_hash, path
        table = tables.get(str(path), {})
        keys = {(str(path.relative_to(ROOT)), number) for number in table}
        hits = {(str(path.relative_to(ROOT)), number) for number, count in table.items() if count > 0}
        lines.update(keys)
        hit_lines.update(hits)
        line_sources.append(dict(source=str(path.relative_to(ROOT)), hit=len(hits), total=len(keys), native_DA_present=bool(table)))
    return dict(meta=meta, dat=dat, nodes=nodes, source=launch, analyzer=analyzer,
                points=point_sets(dat), line_all=lines, line_hit=hit_lines, line_sources=line_sources)


def audit_pair(dut, before, after, case_id, bins):
    old, new = validate_run(before, dut), validate_run(after, dut)
    assert old["source"] == new["source"], "baseline and supplement source sets differ"
    assert old["meta"]["artifact"]["build"] == new["meta"]["artifact"]["build"]
    assert set(old["nodes"]) < set(new["nodes"])
    added = set(new["nodes"]) - set(old["nodes"])
    assert len(added) == 1 and next(iter(added)).endswith("::" + case_id)
    for node, outcome in old["nodes"].items():
        assert new["nodes"][node] == outcome
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

    # The actual registered payload has 120 * 64 * 2 checkpoint toggle points.
    target = [p for p in records(new["dat"]) if p["t"] == "toggle" and re.fullmatch(
        r"uop_\d+_perfDebugInfo_runahead_checkpoint_id\[\d+\]:(?:0->1|1->0)", p.get("o", ""))]
    identities = set()
    for p in target:
        match = re.fullmatch(r"uop_(\d+)_perfDebugInfo_runahead_checkpoint_id\[(\d+)\]:(.*)", p["o"])
        identities.add((int(match[1]), int(match[2]), match[3]))
    assert identities == {(slot, bit, direction) for slot in range(120) for bit in range(64) for direction in ("0->1", "1->0")}
    assert len(target) == 15360 and all(p["hit"] > 0 for p in target)
    paths = list((ROOT / "results" / after / "cases").rglob("checkpoint-pool-witness.json"))
    assert len(paths) == 1
    witness = load(paths[0])
    assert len(witness["lifetimes"]) == 2
    for gen, lifetime in enumerate(witness["lifetimes"]):
        assert lifetime["generation"] == gen and lifetime["checkpoint"] == ((1 << 64) - 1 if not gen else 0)
        assert lifetime["public_slots"] == list(range(120))
        if dut == "load_queue_replay":
            assert lifetime["allocated"] == lifetime["handshakes"] == lifetime["feedback_completed"] == 120
        else:
            assert lifetime["replay_handshakes"] == lifetime["feedback_and_ordered_completions"] == 120
    assert witness.get("distinct_uids", witness.get("completed_uids")) == 240
    for name in (before, after):
        coverage = load(ROOT / "results" / name / "execution/functional-coverage.json")
        checked = next(g for g in coverage["groups"] if g["instance"] == f"lsq.{dut}.checked")
        assert checked["collection_complete"]
        for scenario in bins:
            # Wrapper keeps its original 82-scenario contract: this is a new
            # payload case of existing capacity, not a deleted/new denominator.
            if dut == "lsq_wrapper":
                assert checked["points"][0]["counts"][scenario] > 0
            else:
                assert (checked["points"][0]["counts"][scenario] > 0) == (name == after)
    regression, regression_dat = native("lsq-progress-regression-15", dut)
    assert regression["artifact"]["build"]["build_id"] == new["meta"]["artifact"]["build"]["build_id"]
    reference = point_sets(regression_dat)
    gap_hits = {}
    for kind in ("line", "toggle", "branch"):
        assert reference[kind]["all"] == new["points"][kind]["all"]
        overlap = reference[kind]["missing"] & new["points"][kind]["hit"]
        gap_hits[kind] = dict(regression15_missing_seen_in_directed_after=len(overlap), point_set_SHA256=digest_keys(overlap))
    report = dict(
        format="lsq-checkpoint-pool-evidence-v1", dut=dut, before_run=before, after_run=after,
        contract="docs/contracts/replay-checkpoint-pool.md", source_aggregate=old["source"]["aggregate_SHA256"],
        native_build_id=closure["native_build_id"], baseline_tests=len(old["nodes"]), after_tests=len(new["nodes"]),
        raw_nonwrapper_metrics=closure["metrics"],
        original_source_line_coverage=dict(before_hit=len(old["line_hit"]), after_hit=len(new["line_hit"]),
            total=len(new["line_all"]), newly_hit=len(new["line_hit"] - old["line_hit"]), newly_missing=0,
            source_scope="pinned original DUT closure, not Picker wrapper", sources=new["line_sources"]),
        witness_path=str(paths[0].relative_to(ROOT)), witness_SHA256=sha256_file(paths[0]), witness=witness,
        registered_checkpoint_points=dict(hit=15360, total=15360, slots=120, bits=64, both_directions=True),
        regression15_gap_overlap=gap_hits,
        verification=dict(artifact_and_source_hashes=True, parser_matches_locked_analyzer=True,
            same_source_and_build=True, baseline_nodes_retained=True, no_new_missing=True,
            both_lifetimes_publicly_witnessed=True, semantic_bins_checked=True),
        limits="The overlap is a point-set comparison only, not a coverage merge. Full regression denominators, historical FAILs and other payload gaps remain unchanged. Raw line points and LCOV original source lines are reported separately.",
    )
    output = ROOT / "results" / after / "checkpoint-pool-evidence-v1.json"
    if output.exists():
        assert load(output) == report, "do not overwrite verified evidence"
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: report[key] for key in ("dut", "baseline_tests", "after_tests", "registered_checkpoint_points", "regression15_gap_overlap", "verification")}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dut", choices=[row[0] for row in PAIRS])
    args = parser.parse_args()
    for row in PAIRS:
        if args.dut is None or args.dut == row[0]:
            audit_pair(*row)
