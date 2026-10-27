#!/usr/bin/env python3
"""Keep actual remaining sets and exact VA50-to-fullva64 constant boundaries."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from audit_coverage_points_v1 import records, sha256_file
from audit_evidence_io import write_report
from audit_gap_closure_v1 import native, point_key, digest_keys
from audit_normal_replay_metadata_v1 import FULL

ROOT = Path(__file__).resolve().parents[1]
BASE = "lsq-progress-regression-15"


def family(signal):
    signal = re.sub(r":(?:0->1|1->0)$", "", signal)
    signal = re.sub(r"\[\d+\]$", "", signal)
    return re.sub(r"_\d+(?=_|$)", "_*", signal)


def audit():
    full = json.loads((ROOT / "results" / FULL / "normal-replay-metadata-contributor-evidence-v1.json").read_text())
    assert all(full["verification"].values())
    assert full["current_nodes"] == 1762 and full["status"]["manifest_tests"] == {"PASS": 1566, "FAIL": 196}
    rows, constants = [], []
    for item in full["rows"]:
        dut = item["dut"]
        old_meta, old_dat = native(BASE, dut)
        meta, dat = native(FULL, dut)
        assert old_meta["artifact"]["build"] == meta["artifact"]["build"]
        assert sha256_file(old_dat) == old_meta["artifact"]["sha256"]
        assert sha256_file(dat) == meta["artifact"]["sha256"]
        old = [p for p in records(old_dat) if not p["f"].endswith("_top.sv")]
        current = [p for p in records(dat) if not p["f"].endswith("_top.sv")]
        metrics = {}
        for kind in ("line", "toggle", "branch"):
            before = [p for p in old if p["t"] == kind]
            after = [p for p in current if p["t"] == kind]
            old_all = {point_key(p) for p in before}
            all_points = {point_key(p) for p in after}
            old_missing = {point_key(p) for p in before if not p["hit"]}
            missing = {point_key(p) for p in after if not p["hit"]}
            assert old_all == all_points and missing <= old_missing
            metrics[kind] = dict(total=len(all_points), remaining=len(missing),
                missing_point_set_SHA256=digest_keys(missing),
                subset_of_original_unified_missing_inventory=True,
                original_unified_missing_point_set_SHA256=digest_keys(old_missing))
        remaining = [p for p in current if p["t"] == "toggle" and not p["hit"]]
        source_counts = Counter(str(Path(p["f"]).relative_to(ROOT)) for p in remaining)
        row = dict(dut=dut, native_build_id=meta["artifact"]["build"]["build_id"], metrics=metrics,
            original_source_line_coverage=item["original_source_line_coverage"],
            source_toggle_missing=dict(sorted(source_counts.items(), key=lambda pair: (-pair[1], pair[0]))))
        if dut in ("load_queue_replay", "load_queue", "lsq_wrapper"):
            path = ROOT / "dut/load_queue_replay/LoadQueueReplayDut.v" if dut == "load_queue_replay" else ROOT / "rtl" / dut / "LoadQueueReplay.sv"
            points = [p for p in remaining if p["f"] == str(path)]
            groups = defaultdict(list)
            for p in points:
                groups[family(p["o"])].append(p)
            row["Replay_source_missing"] = len(points)
            row["Replay_families"] = [dict(family=name, missing=len(ps), source_lines=sorted({int(p["l"]) for p in ps}),
                missing_point_set_SHA256=digest_keys({point_key(p) for p in ps}))
                for name, ps in sorted(groups.items(), key=lambda pair: (-len(pair[1]), pair[0]))]
            raw = path.read_text()
            declarations = re.findall(r"output\s+\[63:0\]\s+io_replay_([0-2])_bits_fullva\s*,", raw)
            assignments = list(re.finditer(r"assign io_replay_([0-2])_bits_fullva = \{14'h0, (replay_req_vaddr(?:_[12])?)\};", raw))
            assert sorted(declarations) == ["0", "1", "2"] and len(assignments) == 3
            assert len(re.findall(r"\bassign\s+io_replay_[0-2]_bits_fullva\s*=", raw)) == 3
            assert len(re.findall(r"\bwire\s+\[49:0\]\s+replay_req_vaddr(?:_[12])?\s*=", raw)) == 3
            source_rows = []
            for match in assignments:
                bank = int(match[1])
                assert match[2] == "replay_req_vaddr" + (f"_{bank}" if bank else "")
                source_rows.append(dict(bank=bank, line=raw[:match.start()].count("\n") + 1, exact_statement=match[0]))
            high = [p for p in current if p["f"] == str(path) and p["t"] == "toggle" and
                (match := re.fullmatch(r"io_replay_[0-2]_bits_fullva\[(\d+)\]:(0->1|1->0)", p["o"])) and int(match[1]) >= 50]
            assert len(high) == 84 and not any(p["hit"] for p in high)
            pinned = json.loads((ROOT / "rtl" / dut / "source.json").read_text())["files"]["LoadQueueReplay.sv"]
            assert sha256_file(path) == pinned
            constants.append(dict(dut=dut, source=str(path.relative_to(ROOT)), source_SHA256=pinned,
                statements=source_rows, bits=[50, 63], native_toggle_points=84, hit=0,
                point_identity_SHA256=digest_keys({point_key(p) for p in high}),
                classification="COMBINATIONAL_ZERO_EXTENSION_VA50_TO_FULLVA64",
                native_dynamic_coverage_gain=0, denominator_removed=False))
        rows.append(row)
    result = dict(format="lsq-normal-replay-remaining-gap-selection-v1", run=FULL,
        metrics_scope="native original nonwrapper line/toggle/branch point sets; raw line points are not LCOV original-source closure lines",
        original_classification_run=BASE, rows=rows, exact_fullva_constant_boundaries=constants,
        selection_only=True, next_contract_or_tests_created=False, new_native_DUT_runs=0,
        verification=dict(all9actual_native_builds_compared_to_original_inventory=True,
            all3point_universes_equal_and_remaining_sets_are_original_subsets=True,
            all3exact84point_fullva_high_boundaries_checked=True,
            original_classification_denominators_raw_results_and_failures_unchanged=True),
        next_work=[
            "Replay reason/type known-write lifetimes: inspect the remaining cause,NC and dependency storage at each public slot; preserve strict/disabled failures instead of changing predicates to pass.",
            "Other opcode/vector/hyper domains need their own fixed-source legality/identity/size/mask/S3 contracts before tests; do not fill missing opcode bits using arbitrary integers.",
            "VSQ release-wait remains open: the separate8181row conditional local lemma is not the full128entry cone proof or a coverage waiver.",
            "Remaining SID data retention,mixed fair drain,head permit,full-core capacity histories and all38DUT final regression remain required.",
        ],
        limits="Current nine-build remaining sets are subsets of the original classified inventory; this does not rewrite or claim closure of that38DUT inventory. High fullva bits are exact combinational zeros, independent of reset, not startup-randomness. Other family counts are selection data, not blanket unreachability assertions. No cross-run coverage OR or new DUT execution.")
    write_report(ROOT / "results" / FULL / "remaining-gap-selection-v1.json", result)
    return result


if __name__ == "__main__":
    r = audit()
    print(json.dumps(dict(run=r["run"], remaining={row["dut"]: {kind: value["remaining"] for kind, value in row["metrics"].items()} for row in r["rows"]},
        exact_fullva_constant_points=sum(row["native_toggle_points"] for row in r["exact_fullva_constant_boundaries"]), verification=r["verification"]), indent=2))
