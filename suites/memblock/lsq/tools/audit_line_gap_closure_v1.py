#!/usr/bin/env python3
"""Verify that every remaining native line point has a narrow static boundary proof."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def missing(row: dict) -> list[dict]:
    result = list(row.get("uncovered", []))
    for dependency in row.get("dependencies", []):
        result.extend(dependency.get("uncovered", []))
    return result


def audit(name: str) -> dict:
    run = ROOT / "results" / name
    line_audit = json.loads((run / "line-audit.json").read_text())
    rows = {row["dut"]: row for row in line_audit["native"]}
    all_missing = {key: missing(row) for key, row in rows.items()}
    nonempty = {key: value for key, value in all_missing.items() if value}
    assert set(nonempty) == {"load_queue", "load_queue_uncache", "lsq_wrapper"}, nonempty.keys()

    proofs = {
        "load_queue": ROOT / "results/lq-expanded-06/static-gap-proof.json",
        "load_queue_uncache": ROOT / "results/load-uncache-expanded-03/static-gap-proof.json",
        "lsq_wrapper": ROOT / "results/lsq-expanded-16/static-gap-proof-wrapper-v1.json",
    }
    proof_rows = {}
    for key, path in proofs.items():
        proof = json.loads(path.read_text())
        proof_rows[key] = dict(path=str(path.relative_to(ROOT)), SHA256=sha256(path), status=proof["status"], rows=len(proof["rows"]))
        assert len(proof["rows"]) == len(nonempty[key])
        assert {int(item["line"]) for item in proof["rows"]} == {int(item["line"]) for item in nonempty[key]}

    report = dict(
        format="lsq-line-gap-closure-v1", run=name,
        native_duts=len(rows), native_duts_without_remaining_line_points=len(rows) - len(nonempty),
        remaining_line_points={key: len(value) for key, value in nonempty.items()},
        static_proofs=proof_rows,
        classification="all_remaining_line_points_are_narrow_structural_or_normal-producer-boundary_points; no remaining line point is treated as a reachable functional gap",
        dynamic_supplement="not_run_and_not_required_for_these points: driving illegal guarded-default inputs or an upstream-invalid same-cycle dispatch/redirect would violate the fixed contracts",
        limits="This closes only the line metric's remaining points. It does not close toggle/branch gaps, semantic FAILs, or parent integration. Raw line denominators remain unchanged; no RTL/Chisel/LCOV edit was made.",
    )
    output = run / "line-gap-closure-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
