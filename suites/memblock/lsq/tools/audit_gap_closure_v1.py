#!/usr/bin/env python3
"""Compare two native runs for one DUT after a directed coverage supplement."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_coverage_points_v1 import records  # noqa: E402


def digest_keys(keys: set[tuple]) -> str:
    text = "\n".join(json.dumps(key, ensure_ascii=False, separators=(",", ":")) for key in sorted(keys)) + "\n"
    return hashlib.sha256(text.encode()).hexdigest()


def native(run: str, dut: str) -> tuple[dict, Path]:
    manifest_path = ROOT / "results" / run / "execution" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    specs = json.loads((ROOT / "manifest" / "duts.json").read_text())["duts"]
    export = "DUT" + specs[dut]["export_name"]
    matches = [artifact for artifact in manifest["artifacts"] if artifact.get("kind") == "native" and artifact["build"]["name"] == export]
    assert len(matches) == 1, (run, dut, export, len(matches))
    path = Path(matches[0]["path"])
    assert path.is_file() and path.name == "coverage.dat"
    return dict(manifest=manifest, artifact=matches[0]), path


def point_key(point: dict) -> tuple:
    return tuple(point.get(key, "") for key in ("f", "l", "n", "t", "o", "S", "h"))


def point_sets(path: Path) -> dict:
    result = {}
    for kind in ("line", "toggle", "branch"):
        points = [point for point in records(path) if point["t"] == kind and not point["f"].endswith("_top.sv")]
        result[kind] = {
            "all": {point_key(point) for point in points},
            "missing": {point_key(point) for point in points if point["hit"] <= 0},
            "hit": {point_key(point) for point in points if point["hit"] > 0},
        }
    return result


def functional(run: str, dut: str) -> list[dict]:
    path = ROOT / "results" / run / "execution" / "functional-coverage.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    result = []
    for group in data.get("groups", []):
        instance = group.get("instance", "")
        if instance not in {f"lsq.{dut}.reached", f"lsq.{dut}.checked"}:
            continue
        point = group["points"][0]
        counts = point["counts"]
        result.append(dict(
            instance=instance, hit=sum(value > 0 for value in counts.values()), total=len(counts),
            missing=[name for name, value in counts.items() if value <= 0],
            coverage=group["coverage"], collection_complete=group["collection_complete"],
        ))
    return result


def audit(before: str, after: str, dut: str, feature: str, case_id: str) -> dict:
    old_meta, old_path = native(before, dut)
    new_meta, new_path = native(after, dut)
    old_artifact, new_artifact = old_meta["artifact"], new_meta["artifact"]
    assert old_artifact["build"]["build_id"] == new_artifact["build"]["build_id"], (old_artifact["build"], new_artifact["build"])
    old_sets, new_sets = point_sets(old_path), point_sets(new_path)
    metrics = {}
    for kind in ("line", "toggle", "branch"):
        assert old_sets[kind]["all"] == new_sets[kind]["all"], (kind, len(old_sets[kind]["all"]), len(new_sets[kind]["all"]))
        newly_hit = old_sets[kind]["missing"] - new_sets[kind]["missing"]
        newly_missing = new_sets[kind]["missing"] - old_sets[kind]["missing"]
        metrics[kind] = dict(
            before_hit=len(old_sets[kind]["hit"]), before_total=len(old_sets[kind]["all"]),
            after_hit=len(new_sets[kind]["hit"]), after_total=len(new_sets[kind]["all"]),
            denominator_unchanged=len(old_sets[kind]["all"]) == len(new_sets[kind]["all"]),
            newly_hit=len(newly_hit), newly_hit_SHA256=digest_keys(newly_hit),
            still_missing=len(new_sets[kind]["missing"]), still_missing_SHA256=digest_keys(new_sets[kind]["missing"]),
            newly_missing=len(newly_missing), newly_missing_SHA256=digest_keys(newly_missing),
        )
    old_manifest, new_manifest = old_meta["manifest"], new_meta["manifest"]
    report = dict(
        format="lsq-directed-gap-closure-v1", dut=dut, before_run=before, after_run=after,
        feature_id=feature, case_id=case_id,
        native_build_id=old_artifact["build"]["build_id"],
        before_coverage_dat=str(old_path.relative_to(ROOT)), after_coverage_dat=str(new_path.relative_to(ROOT)),
        before_coverage_dat_SHA256=old_artifact["sha256"], after_coverage_dat_SHA256=new_artifact["sha256"],
        before_status=dict(state=old_manifest["state"], pytest_exitstatus=old_manifest["pytest_exitstatus"], tests=old_manifest["tests"], coverage_complete=old_manifest["coverage_complete"]),
        after_status=dict(state=new_manifest["state"], pytest_exitstatus=new_manifest["pytest_exitstatus"], tests=new_manifest["tests"], coverage_complete=new_manifest["coverage_complete"]),
        functional_before=functional(before, dut), functional_after=functional(after, dut),
        metrics=metrics,
        verification=dict(
            same_native_build=True, all_denominators_unchanged=True,
            no_new_missing_points=all(value["newly_missing"] == 0 for value in metrics.values()),
            after_functional_run_passed=new_manifest["pytest_exitstatus"] == 0,
            actual_native_rerun=True,
        ),
        limits="This is a directed before/after result for one DUT and selected cases. It does not close other DUTs, parent semantic FAILs, or the remaining point inventory; points that stay missing require separate legal-case, unreachable, configuration, or tool-boundary evidence.",
    )
    output = ROOT / "results" / after / f"directed-gap-closure-{dut}-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("dut")
    parser.add_argument("--feature", required=True)
    parser.add_argument("--case", required=True, dest="case_id")
    args = parser.parse_args()
    audit(args.before, args.after, args.dut, args.feature, args.case_id)
