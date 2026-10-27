#!/usr/bin/env python3
"""Classify every current non-wrapper uncovered branch point."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_coverage_points_v1 import records  # noqa: E402
from audit_foundation_gaps_v1 import classify as foundation_classify  # noqa: E402
from audit_foundation_layer_v1 import FOUNDATION  # noqa: E402
from audit_toggle_gap_classification_v1 import context as source_context, family_features  # noqa: E402
from audit_initial_branch_boundaries_v1 import initial_region  # noqa: E402
from audit_evidence_io import write_report  # noqa: E402
from audit_vsq_recovery_boundaries_v1 import state3_boundary  # noqa: E402


def classify(key: str, point: dict) -> tuple[list[str], str, str]:
    region = initial_region(point["f"], point["l"])
    if region is not None:
        features = foundation_classify(key, point)[0] if key in FOUNDATION else family_features(key, point.get("o", ""))
        return features, "tool_or_artifact_limit", (
            f"Pinned source SHA256 {region['source_SHA256']}; branch line {point['l']} lies inside initial process "
            f"{region['initial_start_line']}..{region['initial_end_line']}, guarded by ENABLE_INITIAL_REG_ at "
            f"{region['enable_ifdef_line']}..{region['enable_endif_line']}. Initial executes once at startup; "
            "clocked transactions and later resets do not re-enter it. This remains an unhit initialization-boundary point, "
             "not dynamic coverage or unreachability. Exact source-scope proof is in initial-branch-boundary-audit-v1.json.")
    boundary = state3_boundary(key, point)
    if boundary is not None:
        prefix = {"virtual_store_queue": "VSQ", "store_queue": "SQ", "lsq_wrapper": "LSQ"}[key]
        return [f"{prefix}-RECOVER"], "unreachable_or_dont_care", (
            f"Pinned source SHA256 {boundary['source_SHA256']}; the exact 15848..15857 control region and all state writes "
            "prove reset sets0 and every transition from0/1/2 stays in0/1/2. The15853 else predicate requires state3. "
            "This is post-reset state-encoding boundary evidence, not dynamic coverage or a startup/fault-injection proof. "
            "The separate15850 release-wait gap is not waived. See vsq-recovery-boundary-audit-v1.json.")
    if key in FOUNDATION:
        return foundation_classify(key, point)
    text = source_context(point)
    if key == "unalign_queue" and int(point.get("l", -1)) == 224:
        return ["UQ-RESET"], "tool_or_artifact_limit", "The uncovered else arm belongs to the generated ENABLE_INITIAL_REG_ initialization block; it is not a dynamic UnalignQueue transaction branch and is retained as a tool/initialization boundary."
    if "initial begin" in text or "RANDOMIZE_REG_INIT" in text:
        return family_features(key, point.get("o", "")), "tool_or_artifact_limit", "Branch is attached to generated initialization/randomization scaffolding; retain it as a tool/initialization boundary and do not use illegal reset sequencing to claim dynamic coverage."
    return family_features(key, point.get("o", "")), "existing_feature_missing_case", "A retained branch arm is not observed under the current legal stimulus. Add the corresponding behavior/condition case and rerun the native DUT before claiming closure."


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def audit(name: str) -> dict:
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    duts = json.loads((ROOT / "manifest/duts.json").read_text())["duts"]
    rows = []
    total = 0
    for artifact in manifest["artifacts"]:
        if artifact["kind"] != "native":
            continue
        build = artifact["build"]
        key = next(key for key, spec in duts.items() if "DUT" + spec["export_name"] == build["name"])
        path = Path(artifact["path"])
        gaps = []
        classes = Counter()
        features = Counter()
        for point in records(path):
            if point["t"] != "branch" or point["hit"] > 0 or point["f"].endswith("_top.sv"):
                continue
            fids, classification, evidence = classify(key, point)
            source = str(Path(point["f"]).relative_to(ROOT)) if str(point["f"]).startswith(str(ROOT)) else point["f"]
            gap = dict(
                dut=key, build_id=build["build_id"], metric="branch", source=source,
                source_line=int(point["l"]), source_range=point.get("S"), point=point.get("o", ""),
                hierarchy=point.get("h", ""), hit=point["hit"], source_context=source_context(point),
                feature_ids=fids, classification=classification, evidence=evidence,
                case_id=None, before_after="before_supplement_rerun",
            )
            gaps.append(gap); classes[classification] += 1; features.update(fids)
        total += len(gaps)
        canonical = "\n".join(json.dumps((g["source"], g["source_line"], g["point"], g["hierarchy"], g["hit"]), ensure_ascii=False) for g in sorted(gaps, key=lambda x: (x["source"], x["source_line"], x["point"], x["hierarchy"])))
        rows.append(dict(
            dut=key, build_id=build["build_id"], coverage_dat=str(path.relative_to(ROOT)), coverage_dat_SHA256=sha256(path),
            missing_branch_points=len(gaps), missing_point_inventory_SHA256=hashlib.sha256((canonical + "\n").encode()).hexdigest(),
            classification_counts=dict(sorted(classes.items())), feature_counts=dict(sorted(features.items())), gaps=gaps,
        ))
    assert len(rows) == 38
    report = dict(
        format="lsq-branch-gap-classification-v1", run=name, native_duts=len(rows), total_missing_branch_points=total,
        rows=sorted(rows, key=lambda row: row["dut"]),
        status="all current missing branch points retain source line/condition/hierarchy and a feature or boundary classification; no directed branch supplement rerun is claimed",
        limits="Per-DUT denominators remain independent. Generated initialization points are tool boundaries; three exact VSQ state3 arms have post-reset source/inductive proofs; other points remain feature condition gaps. No point is dynamically credited, deleted or merged across DUTs.",
    )
    output = run / "branch-gap-classification-v1.json"
    write_report(output, report)
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2, ensure_ascii=False))
    for row in report["rows"]:
        if row["missing_branch_points"]:
            print(row["dut"], row["missing_branch_points"], row["classification_counts"])
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
