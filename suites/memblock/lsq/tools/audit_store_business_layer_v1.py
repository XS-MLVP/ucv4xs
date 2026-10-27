#!/usr/bin/env python3
"""Audit Store leaf/parent DUTs with real failures and child boundaries."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_coverage_points_v1 import digest_points, records  # noqa: E402


STORE = {
    "enter_sbuffer_queue": dict(result="enter-sbuffer-expanded-01", contract="enter-sbuffer-queue.md", report="enter-sbuffer-queue-20261018.md", status="PASS_CURRENT_CONFIG", issues=["independent leaf only; does not accept Deq/PSQ/StoreQueue"], tests={"PASS": 26}),
    "virtual_store_queue": dict(result="vsq-expanded-03", contract="virtual-store-queue.md", report="virtual-store-queue-20261018.md", status="NOT_PASS", issues=["VSQ-REDIR-IF-001: same-cycle dispatch+redirect interface boundary, 2 failures"], tests={"PASS": 40, "FAIL": 2}),
    "deq_module": dict(result="deq-lifecycle-expanded-03", contract="deq-module.md", report="deq-module-20261018.md", status="NOT_PASS", issues=["DEQ-WB-001: denied/corrupt error lost at WB fire", "DEQ-SPLIT-WLINE-001: split tail wline error", "DEQ-ZERO-001 / DEQ-FINISH-ORDER-001: ownership/age credit failures"], tests={"PASS": 71, "FAIL": 18}),
    "physical_store_queue": dict(result="psq-expanded-05", contract="physical-store-queue.md", report="physical-store-queue-20261018.md", status="NOT_PASS", issues=["FWD alias/range/SQ identity", "Deq WB/split wline/zero-owner", "full-domain seeded concurrency remains failing"], tests={"PASS": 45, "FAIL": 18}),
    "store_queue": dict(result="sq-expanded-03", contract="store-queue.md", report="store-queue-20261018.md", status="NOT_PASS", issues=["inherits real FWD/Deq/PSQ failures", "SQ-CREDIT.special_order premature release", "SQ recovery/complete-domain strict failures"], tests={"PASS": 55, "FAIL": 24}),
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
    for key, metadata in STORE.items():
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
            line_gap_status="complete" if line_missing == 0 else "gaps_present",
            toggle_branch_gap_status="inventory_only_not_yet_feature_mapped",
            wrapper_exclusion="exclude generated *_top.sv; line uses original-RTL LCOV closure, toggle/branch use non-wrapper native points",
        ))

    assert len(rows) == 5
    report = dict(
        format="lsq-store-business-layer-audit-v1", run=name, dut_count=len(rows),
        rows=sorted(rows, key=lambda row: row["dut"]),
        parent_boundary="Leaf EnterSbuffer/VSQ/Deq and PSQ/StoreQueue results are independent real-DUT evidence. Passing EnterSbuffer does not accept Deq/PSQ/StoreQueue; child failures are rechecked at PSQ/StoreQueue but not silently promoted to system conclusions.",
        limits="Per-DUT line/toggle/branch denominators are retained separately. Human-readable reports classify line gaps and semantic failures; this audit records current non-wrapper toggle/branch missing-point hashes/counts, but no directed three-metric supplement rerun is claimed. Real failures, interface-only boundaries and configuration-deleted signals remain explicit.",
    )
    output = run / "store-business-layer-audit-v1.json"
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
