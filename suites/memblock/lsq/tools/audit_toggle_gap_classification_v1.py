#!/usr/bin/env python3
"""Classify all current non-wrapper toggle gaps without duplicating raw point streams."""
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


CAPACITY = {"freelist_rar": 96, "freelist_raw": 56, "freelist_replay": 120, "freelist_uncache": 16}
SOURCE_CACHE: dict[str, list[str]] = {}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def context(point: dict) -> str:
    try:
        source = point["f"]
        rows = SOURCE_CACHE.get(source)
        if rows is None:
            rows = Path(source).read_text(errors="replace").splitlines()
            SOURCE_CACHE[source] = rows
        line = int(point["l"])
        return rows[line - 1].strip()[:300] if 0 < line <= len(rows) else ""
    except (OSError, ValueError):
        return ""


def family_features(key: str, name: str) -> list[str]:
    prefix = {
        "load_queue": "LQ", "lsq_wrapper": "LSQ", "store_queue": "SQ",
        "physical_store_queue": "PSQ", "load_queue_uncache": "LQU",
        "load_queue_replay": "LRQ", "load_queue_raw": "RAW", "load_queue_rar": "RAR",
        "forward_module": "FWD", "unalign_queue": "UQ", "deq_module": "DEQ",
        "enter_sbuffer_queue": "ESB", "virtual_store_queue": "VSQ",
    }.get(key)
    if key.startswith("uncache_entry_"):
        prefix = "UE"
    if not prefix:
        prefix = key.upper()
    name_lower = name.lower()
    suffix = []
    if any(word in name_lower for word in ("reset", "flush", "cancel", "redirect", "recover")):
        suffix += [f"{prefix}-RESET", f"{prefix}-RECOVER"]
    if any(word in name_lower for word in ("ptr", "rob", "sqidx", "lqidx", "slot", "head", "tail")):
        suffix += [f"{prefix}-ORDER", f"{prefix}-IDENTITY"]
    if any(word in name_lower for word in ("valid", "ready", "req", "resp", "wakeup", "fire", "select")):
        suffix += [f"{prefix}-PIPE", f"{prefix}-HANDSHAKE"]
    if any(word in name_lower for word in ("data", "mask", "paddr", "vaddr", "addr", "byte")):
        suffix += [f"{prefix}-DATA", f"{prefix}-ADDRESS"]
    if any(word in name_lower for word in ("error", "fault", "exception", "nderr", "denied", "corrupt")):
        suffix += [f"{prefix}-ERROR"]
    if any(word in name_lower for word in ("free", "alloc", "recycle", "reuse", "window")):
        suffix += [f"{prefix}-CAPACITY", f"{prefix}-REUSE"]
    return list(dict.fromkeys(suffix or [f"{prefix}-BEHAVIOR"]))


def classify(key: str, point: dict) -> tuple[list[str], str, str]:
    name = point.get("o", "")
    text = context(point)
    if key in FOUNDATION:
        return foundation_classify(key, point)
    if key == "unalign_queue" and re.match(r"io_(?:toDeqModule_bits|forwardEntries_[01])_paddr\[", name):
        match = re.search(r"\[(\d+)\]", name)
        if match and int(match.group(1)) < 12:
            return ["UQ-PAGE", "UQ-ADDRESS"], "unreachable_or_dont_care", "The UnalignQueue contract stores only paddr[47:12] and reconstructs the public address as {paddrHigh, 12'h0}; output bits 0..11 are structurally zero. An illegal non-zero low page offset cannot be used as a legal toggle supplement."
    # Generated initialization blocks are not a legal dynamic transaction
    # domain; retain their points as a tool/initialization boundary.
    if "initial begin" in text or "RANDOMIZE_REG_INIT" in text:
        return family_features(key, name), "tool_or_artifact_limit", "Point is attached to generated initialization/randomization scaffolding; dynamic transaction tests cannot be used as a functional proof of that initialization branch."
    # Explicit constants and optimized-away controls are configuration limits,
    # not a license to drive an otherwise deleted port.
    if re.search(r"(?:=|<=)\s*(?:1['h'b][01]|1'h0|1'h1|false|true)\s*;?$", text):
        return family_features(key, name), "configuration_not_retained", "Source context is a constant/optimized control in the pinned generated configuration; retain the point and configuration evidence rather than inventing a deleted input stimulus."
    return family_features(key, name), "existing_feature_missing_case", "A retained signal transition is not observed under the current legal stimulus. Map it to the listed behavior family and add a legal case/feature-specific directed stimulus before claiming closure."


def audit(name: str) -> dict:
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution" / "manifest.json").read_text())
    duts = json.loads((ROOT / "manifest" / "duts.json").read_text())["duts"]
    rows = []
    total_points = 0
    for artifact in manifest["artifacts"]:
        if artifact["kind"] != "native":
            continue
        build = artifact["build"]
        key = next(key for key, spec in duts.items() if "DUT" + spec["export_name"] == build["name"])
        path = Path(artifact["path"])
        missing = [point for point in records(path) if point["t"] == "toggle" and point["hit"] <= 0 and not point["f"].endswith("_top.sv")]
        canonical = []
        groups = Counter()
        classes = Counter()
        features = Counter()
        source_counts = Counter()
        samples = defaultdict(list)
        for point in missing:
            point_features, classification, evidence = classify(key, point)
            source = str(Path(point["f"]).relative_to(ROOT)) if str(point["f"]).startswith(str(ROOT)) else point["f"]
            base = point.get("o", "").rsplit(":", 1)[0]
            group_key = (source, int(point["l"]), base, point.get("h", ""))
            groups[group_key] += 1
            classes[classification] += 1
            features.update(point_features)
            source_counts[source] += 1
            canonical.append("|".join((source, str(point["l"]), point.get("o", ""), point.get("h", ""), str(point["hit"]))))
            if len(samples[classification]) < 12:
                samples[classification].append(dict(source=source, source_line=int(point["l"]), point=point.get("o", ""), hierarchy=point.get("h", ""), feature_ids=point_features, evidence=evidence))
        canonical.sort()
        inventory = hashlib.sha256(("\n".join(canonical) + "\n").encode()).hexdigest()
        total_points += len(missing)
        rows.append(dict(
            dut=key, build_id=build["build_id"], coverage_dat=str(path.relative_to(ROOT)), coverage_dat_SHA256=sha256(path),
            missing_toggle_points=len(missing), signal_source_groups=len(groups), missing_point_inventory_SHA256=inventory,
            classification_counts=dict(sorted(classes.items())), feature_counts=dict(sorted(features.items())),
            top_source_counts=dict(source_counts.most_common(20)),
            samples=dict(samples), full_point_inventory_persisted=False,
            reproducible_from="coverage_dat_SHA256 + locked raw SystemC::Coverage-3 point parser; no cycle trace or copied source list",
        ))
    assert len(rows) == 38
    report = dict(
        format="lsq-toggle-gap-classification-v1", run=name, native_duts=len(rows), total_missing_toggle_points=total_points,
        rows=sorted(rows, key=lambda row: row["dut"]),
        status="point inventories are fully hashed and source/line/signal-group classified; only compact samples are persisted under summary-only retention; no directed supplement rerun is claimed",
        limits="Classification is per native DUT and excludes Picker *_top.sv. Existing-feature groups require real legal stimuli and before/after reruns; unreachable/configuration/tool groups retain evidence and are not driven with illegal or deleted inputs. No metric denominator or RTL was edited, and no toggle result is merged across DUTs.",
    )
    output = run / "toggle-gap-classification-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2, ensure_ascii=False))
    for row in report["rows"]:
        print(row["dut"], row["missing_toggle_points"], row["classification_counts"])
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
