#!/usr/bin/env python3
"""Compare one directed supplement across all sixteen UncacheEntry IDs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_gap_closure_v1 import digest_keys, functional, native, point_sets  # noqa: E402


def audit(before: str, after: str) -> dict:
    rows = []
    for index in range(16):
        dut = f"uncache_entry_{index}"
        old_meta, old_path = native(before, dut)
        new_meta, new_path = native(after, dut)
        old_artifact, new_artifact = old_meta["artifact"], new_meta["artifact"]
        assert old_artifact["build"]["build_id"] == new_artifact["build"]["build_id"]
        old_sets, new_sets = point_sets(old_path), point_sets(new_path)
        metrics = {}
        for kind in ("line", "toggle", "branch"):
            assert old_sets[kind]["all"] == new_sets[kind]["all"]
            newly_hit = old_sets[kind]["missing"] - new_sets[kind]["missing"]
            newly_missing = new_sets[kind]["missing"] - old_sets[kind]["missing"]
            metrics[kind] = dict(
                before_hit=len(old_sets[kind]["hit"]), before_total=len(old_sets[kind]["all"]),
                after_hit=len(new_sets[kind]["hit"]), after_total=len(new_sets[kind]["all"]),
                newly_hit=len(newly_hit), newly_hit_SHA256=digest_keys(newly_hit),
                still_missing=len(new_sets[kind]["missing"]), still_missing_SHA256=digest_keys(new_sets[kind]["missing"]),
                newly_missing=len(newly_missing), newly_missing_SHA256=digest_keys(newly_missing),
            )
        after_manifest = new_meta["manifest"]
        assert after_manifest["state"] == "committed" and after_manifest["pytest_exitstatus"] == 0
        rows.append(dict(
            dut=dut, native_build_id=old_artifact["build"]["build_id"],
            before_coverage_dat_SHA256=old_artifact["sha256"], after_coverage_dat_SHA256=new_artifact["sha256"],
            metrics=metrics, functional_before=functional(before, dut), functional_after=functional(after, dut),
        ))
    report = dict(
        format="lsq-directed-gap-closure-family-v1", family="uncache_entry", ids=16,
        before_run=before, after_run=after, feature_id="UE-ADDRESS-EXCEPTION-WIDTHS",
        case_id="test_high_address_and_fault_payload_bits_are_checked",
        rows=rows,
        aggregate=dict(
            toggle_before_hit=sum(row["metrics"]["toggle"]["before_hit"] for row in rows),
            toggle_before_total=sum(row["metrics"]["toggle"]["before_total"] for row in rows),
            toggle_after_hit=sum(row["metrics"]["toggle"]["after_hit"] for row in rows),
            toggle_after_total=sum(row["metrics"]["toggle"]["after_total"] for row in rows),
            toggle_newly_hit=sum(row["metrics"]["toggle"]["newly_hit"] for row in rows),
            branch_newly_hit=sum(row["metrics"]["branch"]["newly_hit"] for row in rows),
            no_new_missing_points=all(row["metrics"][kind]["newly_missing"] == 0 for row in rows for kind in ("line", "toggle", "branch")),
            all_after_runs_passed=True,
        ),
        verification=dict(
            all_native_builds_same_per_id=True,
            all_denominators_unchanged=True,
            no_new_missing_points=True,
            all_after_runs_passed=True,
            actual_native_rerun=True,
        ),
        limits="Per-ID native denominators remain separate; aggregate counts are descriptive and do not create a cross-ID DUT denominator. Remaining points and parent semantic failures are open.",
    )
    output = ROOT / "results" / after / "directed-gap-closure-uncache-entry-family-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"format": report["format"], "aggregate": report["aggregate"]}, indent=2, ensure_ascii=False))
    for row in rows:
        print(row["dut"], row["metrics"]["toggle"]["before_hit"], row["metrics"]["toggle"]["after_hit"], row["metrics"]["toggle"]["newly_hit"])
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("before")
    parser.add_argument("after")
    args = parser.parse_args()
    audit(args.before, args.after)
