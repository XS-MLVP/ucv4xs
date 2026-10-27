#!/usr/bin/env python3
"""Audit LoadQueue, StoreQueue and LsqWrapper as real parent combinations."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_coverage_points_v1 import digest_points, records  # noqa: E402


PARENTS = {
    "load_queue": dict(result="lq-expanded-06", contract="load-queue.md", report="load-queue-20261018.md", status="NOT_PASS", tests={"PASS": 187, "FAIL": 12}, issues=["RAR-REL-001 previous-release failure", "LRQ-STRICT-001 strict dependency early replay", "LQU-SID-001 legal SID reuse pollution"]),
    "store_queue": dict(result="sq-expanded-03", contract="store-queue.md", report="store-queue-20261018.md", status="NOT_PASS", tests={"PASS": 55, "FAIL": 24}, issues=["FWD alias/range/SQID", "DEQ WB/split wline/zero owner", "DEQ-FINISH-ORDER-001 premature SQ release", "full-domain seeded concurrency not closed"]),
    "lsq_wrapper": dict(result="lsq-expanded-16", contract="lsq-wrapper.md", report="lsq-wrapper-20261019.md", status="NOT_PASS", tests={"PASS": 269, "FAIL": 48}, issues=["full 82-function contract only 76 checked", "historical RAR/Replay/Uncache/Store cross-layer failures retained", "normal mixed strict FAILs and upstream admission boundaries remain"]),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def functional_summary(data: dict, key: str) -> dict:
    prefix = f"lsq.{key}."
    result = {}
    for group in data["groups"]:
        if not group["instance"].startswith(prefix):
            continue
        point = group["points"][0]
        counts = point["counts"]
        result[group["instance"].rsplit(".", 1)[-1]] = dict(
            hit=sum(value > 0 for value in counts.values()), total=len(counts),
            missing=[name for name, value in counts.items() if value <= 0],
            collection_complete=group["collection_complete"], coverage=group["coverage"],
        )
    assert set(result) == {"reached", "checked"}, (key, result)
    return result


def audit(name: str) -> dict:
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution" / "manifest.json").read_text())
    line_audit = json.loads((run / "line-audit.json").read_text())
    line_rows = {row["dut"]: row for row in line_audit["native"]}
    functional = json.loads((run / "execution" / "functional-coverage.json").read_text())
    duts = json.loads((ROOT / "manifest" / "duts.json").read_text())["duts"]
    native = {}
    for artifact in manifest["artifacts"]:
        if artifact["kind"] != "native":
            continue
        key = next(key for key, spec in duts.items() if "DUT" + spec["export_name"] == artifact["build"]["name"])
        native[key] = (Path(artifact["path"]), artifact)

    rows = []
    for key, metadata in PARENTS.items():
        assert key in native and key in line_rows
        coverage_path, artifact = native[key]
        points = [point for point in records(coverage_path) if not point["f"].endswith("_top.sv")]
        metrics = {}
        for kind in ("toggle", "branch"):
            selected = [point for point in points if point["t"] == kind]
            missing = [point for point in selected if point["hit"] <= 0]
            metrics[kind] = dict(
                hit=len(selected) - len(missing), total=len(selected),
                percent=round(100 * (len(selected) - len(missing)) / len(selected), 4) if selected else 0.0,
                uncovered=len(missing), missing_point_inventory_SHA256=digest_points(missing),
            )
        line = line_rows[key]
        dependencies = line.get("dependencies", [])
        line_missing = len(line.get("uncovered", [])) + sum(len(dep.get("uncovered", [])) for dep in dependencies)
        line_hit = line.get("closure_line_hit", line["line_hit"])
        line_total = line.get("closure_line_total", line["line_total"])
        metrics["line"] = dict(
            hit=line_hit, total=line_total,
            percent=round(100 * line_hit / line_total, 4) if line_total else 0.0,
            uncovered=line_missing, source_scope=line_audit["scope"],
        )
        result_manifest = json.loads((ROOT / "results" / metadata["result"] / "execution" / "manifest.json").read_text())
        assert result_manifest["state"] == "committed" and result_manifest["coverage_complete"] and result_manifest["cleanup_complete"]
        assert result_manifest["tests"] == metadata["tests"], (key, result_manifest["tests"], metadata["tests"])
        rows.append(dict(
            dut=key, result=metadata["result"], status=metadata["status"], issues=metadata["issues"],
            contract=f"docs/contracts/{metadata['contract']}", report=f"docs/reports/{metadata['report']}",
            committed_tests=result_manifest["tests"], committed_functional_groups=result_manifest["functional_groups"],
            build_id=artifact["build"]["build_id"], coverage_dat=str(coverage_path.relative_to(ROOT)),
            coverage_dat_SHA256=sha256(coverage_path), metrics=metrics,
            current_regression_functional=functional_summary(functional, key),
            line_gap_status="complete" if line_missing == 0 else "remaining_points_require_classification",
            toggle_branch_gap_status="inventory_only_not_yet_feature_mapped",
            wrapper_exclusion="exclude generated *_top.sv; line uses original-RTL LCOV closure, toggle/branch use non-wrapper native points",
        ))

    assert len(rows) == 3
    unified_manifest = json.loads((run / "execution" / "manifest.json").read_text())
    report = dict(
        format="lsq-parent-combinations-audit-v1", run=name, parent_duts=3,
        unified_regression=dict(state=unified_manifest["state"], tests=unified_manifest["tests"], functional_groups=unified_manifest["functional_groups"], coverage_complete=unified_manifest["coverage_complete"], cleanup_complete=unified_manifest["cleanup_complete"]),
        rows=sorted(rows, key=lambda row: row["dut"]),
        connection_boundary="Each row is the real parent DUT with its real children, not a merge of independent leaf coverage. LoadQueue and StoreQueue remain separate parent combinations; LsqWrapper retains both and all 53-file closure. No external hidden ready/full/response ports are fabricated.",
        limits="All parent metrics retain independent native denominators; no leaf/history numerator is added. Historical parent FAILs and interface/configuration boundaries remain ordinary evidence. Current line/toggle/branch gap hashes are inventory evidence only; the final request-to-feature-to-gap-to-directed-rerun audit is not complete.",
    )
    output = run / "parent-combinations-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2, ensure_ascii=False))
    for row in report["rows"]:
        print(row["dut"], row["status"], json.dumps(row["committed_tests"], ensure_ascii=False), json.dumps(row["metrics"], ensure_ascii=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
