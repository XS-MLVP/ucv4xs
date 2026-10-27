#!/usr/bin/env python3
"""Audit the foundation DUTs without merging their coverage denominators."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_coverage_points_v1 import digest_points, records  # noqa: E402


FOUNDATION = {
    "freelist_rar": ("DUTFreeListRarDut", "FreeList", "freelist-20261018.md", "freelist"),
    "freelist_raw": ("DUTFreeListRawDut", "FreeList_1", "freelist-20261018.md", "freelist"),
    "freelist_replay": ("DUTFreeListReplayDut", "FreeList_2", "freelist-20261018.md", "freelist"),
    "freelist_uncache": ("DUTFreeListUncacheDut", "FreeList_3", "freelist-20261018.md", "freelist"),
    "cam_rar": ("DUTCamRarDut", "LqPAddrModule", "cam-20261018.md", "cam"),
    "cam_raw": ("DUTCamRawDut", "LqPAddrModule_1", "cam-20261018.md", "cam"),
    "cam_mask": ("DUTCamMaskDut", "LqMaskModule", "cam-20261018.md", "cam"),
    "age_replay": ("DUTAgeReplayDut", "AgeDetector_36", "age-20261018.md", "age"),
    "virtual_load_queue": ("DUTVirtualLoadQueueDut", "VirtualLoadQueue", "vlq-20261018.md", "vlq"),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def functional_summary(path: Path, key: str) -> dict:
    data = json.loads(path.read_text())
    groups = {}
    prefix = f"lsq.{key}."
    for group in data["groups"]:
        if not group["instance"].startswith(prefix):
            continue
        point = group["points"][0]
        counts = point["counts"]
        groups[group["instance"].rsplit(".", 1)[-1]] = dict(
            hit=sum(value > 0 for value in counts.values()), total=len(counts),
            missing=[name for name, value in counts.items() if value <= 0],
            collection_complete=group["collection_complete"],
            coverage=group["coverage"],
        )
    assert set(groups) == {"reached", "checked"}, (key, groups)
    return groups


def audit(name: str) -> dict:
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution" / "manifest.json").read_text())
    line_audit = json.loads((run / "line-audit.json").read_text())
    line_rows = {row["dut"]: row for row in line_audit["native"]}
    duts = json.loads((ROOT / "manifest" / "duts.json").read_text())["duts"]
    native = {}
    for artifact in manifest["artifacts"]:
        if artifact["kind"] != "native":
            continue
        build = artifact["build"]
        key = next(key for key, spec in duts.items() if "DUT" + spec["export_name"] == build["name"])
        native[key] = (Path(artifact["path"]), artifact)

    foundation_functional = ROOT / "results" / "foundation-regression-01" / "execution" / "functional-coverage.json"
    rows = []
    for key, (export, top, report, contract_family) in FOUNDATION.items():
        assert key in native and key in line_rows
        coverage_path, artifact = native[key]
        points = records(coverage_path)
        line = line_rows[key]
        # Picker's *_top.sv is an export wrapper.  It is not part of the RTL
        # line closure and is excluded from the toggle/branch closure as well.
        native_points = [point for point in points if not point["f"].endswith("_top.sv")]
        metrics = {}
        for kind in ("toggle", "branch"):
            selected = [point for point in native_points if point["t"] == kind]
            missing = [point for point in selected if point["hit"] <= 0]
            metrics[kind] = dict(
                hit=len(selected) - len(missing), total=len(selected),
                percent=round(100 * (len(selected) - len(missing)) / len(selected), 4) if selected else 0.0,
                uncovered=len(missing), missing_point_inventory_SHA256=digest_points(missing),
            )
        dependencies = line.get("dependencies", [])
        line_gap_count = len(line.get("uncovered", [])) + sum(len(dep.get("uncovered", [])) for dep in dependencies)
        line_total = line.get("closure_line_total", line["line_total"])
        line_hit = line.get("closure_line_hit", line["line_hit"])
        metrics["line"] = dict(
            hit=line_hit, total=line_total, percent=round(100 * line_hit / line_total, 4) if line_total else 0.0,
            uncovered=line_gap_count, source_scope=line_audit["scope"],
        )
        rows.append(dict(
            dut=key, export=export, top=top, report=f"docs/reports/{report}",
            contract=f"docs/contracts/{contract_family}.md", build_id=artifact["build"]["build_id"],
            coverage_dat=str(coverage_path.relative_to(ROOT)), coverage_dat_SHA256=sha256(coverage_path),
            metrics=metrics,
            functional=functional_summary(foundation_functional, key),
            line_gap_status="complete" if line_gap_count == 0 else "gaps_present",
            toggle_branch_gap_status="inventory_only_not_yet_feature_mapped",
            wrapper_exclusion="exclude generated *_top.sv; line uses existing original-RTL LCOV closure; toggle/branch use non-wrapper native coverage points",
        ))

    assert len(rows) == 9
    assert all(row["line_gap_status"] == "complete" for row in rows)
    report = dict(
        format="lsq-foundation-layer-audit-v1", run=name, foundation_duts=9,
        historical_functional_run="foundation-regression-01", historical_functional_tests=109,
        historical_functional_groups=18, rows=sorted(rows, key=lambda row: row["dut"]),
        gap_inventory="foundation-coverage-gaps-v1.json",
        limits="Foundation semantic and original line closure are complete in their committed evidence, but this audit does not claim three-metric gap closure: toggle/branch uncovered points are retained by per-DUT hashes and still require feature/case classification and directed reruns. The nine DUTs are independent; no leaf result is substituted for a parent.",
    )
    output = run / "foundation-layer-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2, ensure_ascii=False))
    for row in report["rows"]:
        print(row["dut"], json.dumps(row["metrics"], ensure_ascii=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
