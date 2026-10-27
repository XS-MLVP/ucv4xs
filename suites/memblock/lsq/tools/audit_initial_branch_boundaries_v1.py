#!/usr/bin/env python3
"""Prove generated initial-process branch scope, not dynamic unreachability."""
from __future__ import annotations

import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

from audit_coverage_points_v1 import records, sha256_file
from audit_evidence_io import write_report

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=None)
def initial_regions(source):
    path = Path(source)
    raw = path.read_bytes()
    lines = raw.decode().splitlines()
    result = []
    for index, text in enumerate(lines):
        if not re.fullmatch(r"\s*initial begin\s*", text):
            continue
        ends = [end for end in range(index + 1, len(lines)) if re.fullmatch(r"\s*end // initial\s*", lines[end])]
        assert ends, (source, index + 1)
        end = ends[0]
        guards = [start for start in range(max(0, index - 16), index) if lines[start].strip() == "`ifdef ENABLE_INITIAL_REG_"]
        guard_ends = [finish for finish in range(end + 1, min(len(lines), end + 10)) if lines[finish].strip() == "`endif // ENABLE_INITIAL_REG_"]
        assert len(guards) == len(guard_ends) == 1, (source, index + 1, guards, guard_ends)
        result.append(dict(source=str(path.relative_to(ROOT)), source_SHA256=hashlib.sha256(raw).hexdigest(),
                           enable_ifdef_line=guards[0] + 1, initial_start_line=index + 1, initial_end_line=end + 1,
                           enable_endif_line=guard_ends[0] + 1,
                           process_span_SHA256=hashlib.sha256(("\n".join(lines[index:end + 1]) + "\n").encode()).hexdigest()))
    return result


def initial_region(source, line):
    regions = [r for r in initial_regions(source) if r["initial_start_line"] <= int(line) <= r["initial_end_line"]]
    assert len(regions) <= 1
    return regions[0] if regions else None


def audit(name):
    directory = ROOT / "results" / name
    manifest = json.loads((directory / "execution/manifest.json").read_text())
    classification = json.loads((directory / "branch-gap-classification-v1.json").read_text())
    specs = json.loads((ROOT / "manifest/duts.json").read_text())["duts"]
    classified = {row["dut"]: row for row in classification["rows"]}
    proofs, native_duts, raw_missing = [], set(), 0
    for artifact in manifest["artifacts"]:
        if artifact["kind"] != "native":
            continue
        dut = next(key for key, spec in specs.items() if "DUT" + spec["export_name"] == artifact["build"]["name"])
        native_duts.add(dut)
        path = Path(artifact["path"])
        assert sha256_file(path) == artifact["sha256"]
        pinned = json.loads((ROOT / "rtl" / dut / "source.json").read_text())["files"]
        allowed = {}
        spec = specs[dut]
        for filename, digest in pinned.items():
            source = ROOT / "dut" / dut / (spec["export_name"] + ".v") if filename == spec["top"] + ".sv" else ROOT / "rtl" / dut / filename
            allowed[str(source)] = digest
        expected_points = set()
        for point in records(path):
            if point["t"] != "branch" or point["hit"] > 0 or point["f"].endswith("_top.sv"):
                continue
            raw_missing += 1
            assert point["f"] in allowed
            region = initial_region(point["f"], point["l"])
            if region is None:
                continue
            assert region["source_SHA256"] == allowed[point["f"]]
            source_line = Path(point["f"]).read_text().splitlines()[int(point["l"]) - 1].strip()
            # All observed missing generated-init branches are reset tests.
            # A different predicate requires separate review, not a keyword rule.
            assert re.fullmatch(r"if \(reset\)(?: begin)?", source_line), (dut, point, source_line)
            identity = (region["source"], int(point["l"]), point.get("o", ""), point.get("h", ""))
            expected_points.add(identity)
            proofs.append(dict(dut=dut, build_id=artifact["build"]["build_id"], coverage_dat_SHA256=artifact["sha256"],
                               **region, branch_line=int(point["l"]), point=point.get("o", ""), hierarchy=point.get("h", ""),
                               hit=point["hit"], classification="tool_or_artifact_limit",
                               reason="The reset predicate is in this exact generated ENABLE_INITIAL_REG_ initial process. Verilog initial executes once at initialization; clocked transactions and later resets cannot re-enter it. Different time-zero startup values could cover the other arm but are not a proof of a dynamic LSQ feature. The point stays missing and in its native denominator."))
        row = classified[dut]
        actual_points = {(g["source"], g["source_line"], g["point"], g["hierarchy"]) for g in row["gaps"] if g["classification"] == "tool_or_artifact_limit"}
        assert actual_points == expected_points, (dut, actual_points - expected_points, expected_points - actual_points)
    assert len(native_duts) == 38 and raw_missing == classification["total_missing_branch_points"]
    report = dict(format="lsq-initial-branch-boundary-audit-v1", run=name, native_duts=38,
                  total_missing_branch_points=raw_missing, initial_process_missing_points=len(proofs),
                  other_missing_branch_points=raw_missing - len(proofs), counts_by_dut=dict(sorted(Counter(p["dut"] for p in proofs).items())),
                  proofs=sorted(proofs, key=lambda p: (p["dut"], p["source"], p["branch_line"], p["point"], p["hierarchy"])),
                  verification=dict(exact_initial_and_ENABLE_INITIAL_REG_scope=True, pinned_original_source_hashes=True,
                      native_dat_hashes=True, all_tool_classified_branch_points_equal_proven_initial_points=True,
                      raw_missing_count_unchanged=True),
                  limits="This is a source-scope and initialization-boundary audit, not branch coverage gain, dynamic unreachability or a waiver. Both arms and every missing native point remain in the original denominator. No startup policy, RTL, DUT pins, historical FAIL or raw dat is edited. Non-initial gaps still require legal functional cases or separate concrete evidence.")
    write_report(directory / "initial-branch-boundary-audit-v1.json", report)
    print(json.dumps({key: value for key, value in report.items() if key != "proofs"}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
