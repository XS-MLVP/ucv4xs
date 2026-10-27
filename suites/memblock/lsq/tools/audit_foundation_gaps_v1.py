#!/usr/bin/env python3
"""Classify foundation line/toggle/branch gaps without changing RTL.

Line gaps are taken from the original-RTL line audit.  Toggle and branch gaps
are expanded from the current native coverage.dat after excluding Picker's
generated *_top.sv wrapper.  This is a classification inventory, not a claim
that directed补例 have already been rerun.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_coverage_points_v1 import digest_points, records  # noqa: E402
from audit_foundation_layer_v1 import FOUNDATION  # noqa: E402

CAPACITY = {"freelist_rar": 96, "freelist_raw": 56, "freelist_replay": 120, "freelist_uncache": 16}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_context(point: dict) -> str:
    path = Path(point["f"])
    try:
        line = int(point["l"])
        rows = path.read_text(errors="replace").splitlines()
        return rows[line - 1].strip()[:300] if 0 < line <= len(rows) else "<source line unavailable>"
    except (OSError, ValueError):
        return "<source line unavailable>"


def is_generated_initial_branch(point: dict) -> bool:
    try:
        path = Path(point["f"])
        line = int(point["l"])
        rows = path.read_text(errors="replace").splitlines()
        # Generated random-initializer blocks can contain hundreds of register
        # assignments before the reset conditional; retain enough context to
        # identify that same block without treating ordinary clocked logic as
        # initialization.
        window = rows[max(0, line - 2001):line]
        return any("initial begin" in row for row in window) and any("ENABLE_INITIAL_REG_" in row for row in window)
    except (OSError, ValueError):
        return False


def classify(key: str, point: dict) -> tuple[list[str], str, str]:
    name = point.get("o", "")
    context = source_context(point)
    if key in {"cam_raw", "cam_mask"} and point["t"] == "toggle":
        if re.search(r"writeAddrDec_[0-2]\[(?:5[6-9]|6[0-3])\]", name):
            return ["CAM-WRITE", "CAM-SCOPE"], "unreachable_or_dont_care", "56-entry CAM legal address domain is 0..55; decoder bits 56..63 require an illegal out-of-range write and must not be driven merely to toggle coverage."
    if key.startswith("freelist") and point["t"] == "toggle":
        if name.startswith("deqPtr_reverse_flag") and key == "freelist_rar":
            return ["FL-WRAP", "FL-CAPACITY"], "unreachable_or_dont_care", "The RAR 96-entry implementation normalizes headPtr_value back into 0..95 on every allocated advance; this pre-normalization reverse predicate has no legal steady-state transition in the pinned configuration. It is retained as a structural non-power-of-two boundary, not driven with an invalid pointer."
        vector = re.search(r"(?:freeSlotOH_next_nextVec|remFreeSelIndexOHVec)_(\d+)(?:_r)?\[(\d+)\]", name)
        if vector and int(vector.group(2)) % 4 != int(vector.group(1)):
            return ["FL-RETURN", "FL-CONGESTION", "FL-ORDER"], "unreachable_or_dont_care", "The four return/selection vectors are channel-partitioned: channel c can carry only slot indices with slot modulo 4 equal to c. This bit is outside the legal vector domain; driving it would require an invalid cross-channel slot notification."
        pointer = re.search(r"(?:Ptr|Window).*\[(\d+)\]", name)
        if pointer and int(pointer.group(1)) >= (CAPACITY[key] - 1).bit_length():
            return ["FL-ALLOC", "FL-CAPACITY", "FL-WRAP", "FL-PREFETCH"], "unreachable_or_dont_care", f"The {CAPACITY[key]}-entry variant's legal pointer/window value range is 0..{CAPACITY[key] - 1}; this encoded high bit is outside that non-power-of-two domain and cannot be reached by legal allocation or return traffic."
    if is_generated_initial_branch(point):
        if key.startswith("freelist"):
            feature = "FL-RESET"
        elif key == "age_replay":
            feature = "AGE-RESET"
        elif key == "virtual_load_queue":
            feature = "VLQ-RESET"
        else:
            feature = "RESET"
        return [feature], "tool_or_artifact_limit", "The uncovered branch is in the generated ENABLE_INITIAL_REG_ random-initialization block rather than the clocked microarchitectural state update; the current point stream does not record the alternate initial branch, so it is retained as a tool/initialization boundary, not removed from the denominator."
    if key.startswith("freelist"):
        if any(token in name for token in ("freeSlot", "remFree", "freeReq", "freeList")):
            return ["FL-RETURN", "FL-CONGESTION", "FL-ORDER", "FL-WRAP"], "existing_feature_missing_case", "A valid free-slot/return-selection bit or branch did not observe both values; complete legal return-channel walks, variable batches, contention and full-pool wrap, then reallocate the returned IDs."
        if any(token in name for token in ("Ptr", "ptr", "allocate")):
            return ["FL-ALLOC", "FL-CAPACITY", "FL-OVERLAP", "FL-PREFETCH", "FL-WRAP"], "existing_feature_missing_case", "A valid allocation/pointer transition was not exercised at a legal capacity, overlap, prefetch or wrap boundary; supplement with independent ownership accounting and actual reuse."
        return ["FL-ALLOC", "FL-CAPACITY"], "existing_feature_missing_case", "The point belongs to an existing FreeList allocation/capacity contract but lacks a legal input/state case; supplement and check the public offer/ownership relation."
    if key.startswith("cam"):
        return ["CAM-WRITE", "CAM-TIMING", "CAM-REUSE"], "existing_feature_missing_case", "The CAM point is in a legal write/visibility/rewrite path; add the missing slot, bank, port or timing case and verify it through an independent query model."
    if key == "age_replay":
        return ["AGE-ORDER", "AGE-READY", "AGE-REMOVE", "AGE-REUSE", "AGE-POOL"], "existing_feature_missing_case", "The point belongs to the legal age/order lifecycle; add a ready-subset, high-index, delete/reinsert or same-edge timing case and compare the actual oldest selection."
    if key == "virtual_load_queue":
        if any(token in name for token in ("reverse", "redirect", "Cancel", "flipped", "lastEnq")):
            features = ["VLQ-REDIRECT", "VLQ-RECOVER", "VLQ-RACE", "VLQ-REUSE"]
        elif any(token in name for token in ("deq", "commit", "Ptr")):
            features = ["VLQ-ORDER", "VLQ-TIMING", "VLQ-REUSE"]
        elif "robIdx" in name:
            features = ["VLQ-INTERVAL", "VLQ-REDIRECT", "VLQ-REUSE"]
        else:
            features = ["VLQ-INTERVAL", "VLQ-COMPLETE", "VLQ-REUSE"]
        return features, "existing_feature_missing_case", "A legal VLQ pointer/tag/interval point lacks a transition under the current stimulus; supplement the corresponding full-capacity, non-power-of-two wrap, redirect/recovery or ROB-tag case and require real release/reuse."
    return ["UNMAPPED"], "missing_feature_point", "No foundation mapping rule matched this point; it requires manual microarchitectural review before any reachability or supplement decision."


def gap_record(key: str, build_id: str, point: dict) -> dict:
    features, classification, evidence = classify(key, point)
    source = Path(point["f"])
    try:
        source = source.relative_to(ROOT)
    except ValueError:
        pass
    return dict(
        build_id=build_id, dut=key, metric=point["t"], source=str(source),
        source_line=int(point["l"]), source_range=point.get("S"), point=point.get("o", ""),
        hierarchy=point.get("h", ""), hit=point["hit"], source_context=source_context(point),
        feature_ids=features, classification=classification, evidence=evidence,
        case_id=None, before_after="before_supplement_rerun",
        reproducer="results/lsq-progress-regression-13/execution/native/" + build_id + "/coverage.dat",
    )


def audit(name: str) -> dict:
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution" / "manifest.json").read_text())
    line_audit = json.loads((run / "line-audit.json").read_text())
    line_rows = {row["dut"]: row for row in line_audit["native"]}
    duts = json.loads((ROOT / "manifest" / "duts.json").read_text())["duts"]
    gaps = []
    rows = []
    for artifact in manifest["artifacts"]:
        if artifact["kind"] != "native":
            continue
        build = artifact["build"]
        key = next(key for key, spec in duts.items() if "DUT" + spec["export_name"] == build["name"])
        if key not in FOUNDATION:
            continue
        path = Path(artifact["path"])
        points = [point for point in records(path) if not point["f"].endswith("_top.sv") and point["hit"] <= 0 and point["t"] in ("toggle", "branch")]
        current = [gap_record(key, build["build_id"], point) for point in points]
        gaps.extend(current)
        line = line_rows[key]
        line_gaps = len(line.get("uncovered", [])) + sum(len(dep.get("uncovered", [])) for dep in line.get("dependencies", []))
        rows.append(dict(
            dut=key, build_id=build["build_id"], line_uncovered=line_gaps,
            toggle_uncovered=sum(g["metric"] == "toggle" for g in current),
            branch_uncovered=sum(g["metric"] == "branch" for g in current),
            toggle_branch_inventory_SHA256=hashlib.sha256(json.dumps(current, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        ))
    assert len(rows) == 9
    report = dict(
        format="lsq-foundation-coverage-gaps-v1", run=name, dut_count=len(rows),
        rows=sorted(rows, key=lambda row: row["dut"]), gaps=gaps,
        classification_status="line gaps already closed in original-RTL audit; every current non-wrapper toggle/branch gap has a rule-based feature/reachability classification, but no directed supplement rerun is claimed",
        limits="CAM decoder bits 56..63 are retained as unreachable legal-domain boundaries, not driven with illegal inputs. Generated initial-reset branch points are retained as tool/initialization limits. All other listed gaps are reachable-feature scenario gaps pending real directed tests and before/after native comparison. No denominator or RTL was edited.",
    )
    output = run / "foundation-coverage-gaps-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("rows", "gaps")}, indent=2, ensure_ascii=False))
    for row in report["rows"]:
        print(row)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
