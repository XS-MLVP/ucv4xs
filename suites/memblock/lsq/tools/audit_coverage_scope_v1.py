#!/usr/bin/env python3
"""Separate original DUT and Picker-wrapper points without editing raw data."""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
import json
from pathlib import Path

from audit_coverage_points_v1 import analyzer_summary, digest_points, records, sha256_file

ROOT = Path(__file__).resolve().parents[1]


def counts(points):
    hit = sum(p["hit"] > 0 for p in points)
    missing = [p for p in points if p["hit"] <= 0]
    return dict(hit=hit, total=len(points), missing=len(missing),
                percent=round(100 * hit / len(points), 4) if points else None,
                missing_point_inventory_SHA256=digest_points(missing))


def audit(name):
    directory = ROOT / "results" / name
    manifest = json.loads((directory / "execution/manifest.json").read_text())
    specs = json.loads((ROOT / "manifest/duts.json").read_text())["duts"]
    assert manifest["state"] == "committed" and manifest["coverage_complete"]
    rows = []
    for artifact in manifest["artifacts"]:
        if artifact["kind"] != "native":
            continue
        build = artifact["build"]
        dut = next(key for key, spec in specs.items() if "DUT" + spec["export_name"] == build["name"])
        spec = specs[dut]
        path = Path(artifact["path"])
        assert sha256_file(path) == artifact["sha256"]
        pinned = json.loads((ROOT / "rtl" / dut / "source.json").read_text())["files"]
        allowed = set()
        for filename, digest in pinned.items():
            source = ROOT / "dut" / dut / (spec["export_name"] + ".v") if filename == spec["top"] + ".sv" else ROOT / "rtl" / dut / filename
            assert sha256_file(source) == digest, source
            allowed.add(str(source))
        parsed = records(path)
        analyzer, stdout = analyzer_summary(path)
        metrics = {}
        for kind in ("line", "toggle", "branch"):
            full = [p for p in parsed if p["t"] == kind]
            wrapper = [p for p in full if p["f"].endswith("_top.sv")]
            original = [p for p in full if not p["f"].endswith("_top.sv")]
            assert all(p["f"] in allowed for p in original), (dut, kind, sorted({p["f"] for p in original} - allowed))
            a, w, o = counts(full), counts(wrapper), counts(original)
            assert a["hit"] == analyzer[kind]["hit"] and a["total"] == analyzer[kind]["total"]
            for field in ("hit", "total", "missing"):
                assert a[field] == w[field] + o[field]
            assert o["hit"] + o["missing"] == o["total"]
            metrics[kind] = dict(raw_all=a, picker_wrapper=w, original_nonwrapper=o)
        rows.append(dict(dut=dut, dut_export=build["name"], build_id=build["build_id"],
                         coverage_dat=str(path.relative_to(ROOT)), coverage_dat_SHA256=artifact["sha256"],
                         analyzer=f"str(ucv_paths.project_root() / '.tools/verilator/bin/verilator_coverage --report summary '){path}",
                         metrics=metrics))
    rows.sort(key=lambda r: r["dut"])
    assert len({r["dut"] for r in rows}) == len(rows)
    classification_checks = {}
    for kind in ("toggle", "branch"):
        classification_path = directory / f"{kind}-gap-classification-v1.json"
        if not classification_path.exists():
            continue
        classification = json.loads(classification_path.read_text())
        classified = {r["dut"]: r for r in classification["rows"]}
        assert set(classified) == {r["dut"] for r in rows}
        for row in rows:
            old = classified[row["dut"]]
            assert old["build_id"] == row["build_id"]
            assert old["coverage_dat_SHA256"] == row["coverage_dat_SHA256"]
            assert old[f"missing_{kind}_points"] == row["metrics"][kind]["original_nonwrapper"]["missing"]
        classification_checks[kind] = True
    report = dict(format="lsq-coverage-scope-audit-v1", run=name, native_builds=len(rows), rows=rows,
        scope="raw-all = pinned original nonwrapper + Picker *_top.sv, each within one native build",
        classification_missing_counts_match=classification_checks,
        verification=dict(raw_parser_matches_locked_analyzer=True, all_points_accounted_once=True,
                          original_sources_match_pinned_hashes=True, each_scope_hit_plus_missing_equals_total=True),
        limits="This separates presentation scopes only; raw dat, DUT RTL, point identities, native build and historical results are unchanged. Raw line points are not LCOV expanded source lines. Wrapper exclusion is not a coverage gain, and results are never combined across builds or runs.")
    output = directory / "coverage-scope-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report, "immutable scope audit differs"
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
