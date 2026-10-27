#!/usr/bin/env python3
"""Audit Verilator line/toggle/branch summaries from committed coverage.dat.

This is intentionally a compact metric audit: it retains per-build identity,
metric counts and the exact analyzer command, not annotated source copies or
per-cycle traces. It does not replace semantic or source-line audits.
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
VERILATOR_COVERAGE = str(ucv_paths.project_root() / '.tools/verilator/bin/verilator_coverage')
METRIC = re.compile(r"^\s+(line|toggle|branch|expr|fsm_state|fsm_arc)\s+:\s+([0-9.]+)%\s+\(\s*([0-9]+)\s*/\s*([0-9]+)\)")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def parse(path: Path) -> dict:
    command = [VERILATOR_COVERAGE, "--report", "summary", str(path)]
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    metrics = {}
    for line in proc.stdout.splitlines():
        match = METRIC.match(line)
        if match:
            kind, percent, hit, total = match.groups()
            metrics[kind] = dict(percent=float(percent), hit=int(hit), total=int(total))
    required = ("line", "toggle", "branch")
    assert all(kind in metrics for kind in required), (path, proc.stdout)
    return dict(metrics=metrics, analyzer=" ".join(command), coverage_dat_bytes=path.stat().st_size,
                coverage_dat_SHA256=digest(path))


def audit(name: str) -> dict:
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"]
    rows = []
    for artifact in manifest["artifacts"]:
        if artifact["kind"] != "native":
            continue
        coverage = Path(artifact["path"])
        assert coverage.name == "coverage.dat" and coverage.is_file()
        build = artifact["build"]
        row = parse(coverage)
        row.update(build_id=build["build_id"], dut_export=build["name"],
                   coverage_artifact_SHA256=artifact["sha256"],
                   coverage_artifact_matches_dat=digest(coverage) == artifact["sha256"])
        assert row["coverage_artifact_matches_dat"]
        rows.append(row)
    assert rows
    kinds = ("line", "toggle", "branch", "expr", "fsm_state", "fsm_arc")
    availability = {
        kind: {
            "native_builds_with_metric": sum(kind in row["metrics"] for row in rows),
            "native_builds_without_metric": sum(kind not in row["metrics"] for row in rows),
        }
        for kind in kinds
    }
    report = dict(format="lsq-verilator-coverage-metrics-v1", run=name, native_builds=len(rows),
                  per_build_denominators_only=True, metric_availability=availability, builds=rows,
                  source="committed native coverage.dat analyzed by locked Verilator 5.052",
                  limits="Metrics are native coverage point summaries, not semantic checks. Each native build retains its own hit/total denominator; no line/toggle/branch numerator or denominator is merged across DUTs, leaves, historical runs, or result directories. Hierarchy reports are collapsed by Verilator and are not precise per-instance source attribution. Expr/FSM may be zero when build flags disable them. Remaining line/toggle/branch points require separate source mapping and feature-gap classification.")
    output = run / "coverage-metrics-summary-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "builds"}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
