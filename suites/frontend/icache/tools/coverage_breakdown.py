#!/usr/bin/env python3
"""Line / branch / toggle coverage breakdown from the raw Verilator database.

The native database (``coverage.dat``) carries three instrumented point kinds:

* ``line``   - one point per executable block; the count is block executions.
* ``branch`` - one point per condition arm (``cond_then`` / ``cond_else`` /
  ``case``); the count is how often that arm was taken.
* ``toggle`` - one point per signal bit and direction (``0->1`` / ``1->0``);
  the count is how often that transition happened.

``verilator_coverage --write-info`` only emits LCOV ``DA`` records, and those
mix block and branch points; it cannot express toggle coverage at all.  This
tool reads the native points directly so the three metrics stay separate.

A point is covered when at least one hierarchy instance of the same source
location saw it.  Points in the picker ``*_top`` harness are excluded exactly
as in ``tools/coverage_gaps.py``.  Nothing else is removed from the
denominator: storage-macro bits and payload bits stay in the totals and are
reported separately instead.

Usage::

    python3 tools/coverage_breakdown.py results/toffee-full-14
    python3 tools/coverage_breakdown.py results/toffee-full-14 --dut waylookup
    python3 tools/coverage_breakdown.py results/toffee-full-14 --json out.json
    python3 tools/coverage_breakdown.py results/toffee-full-14 --dut waylookup --list branch
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections import defaultdict
from pathlib import Path

SEP = "\x01"

PAYLOAD = re.compile(
    r"(addr|data|code|tag|ptag|idx|setidx|rvc|map|mask|way|source|opcode|size|"
    r"offset|entries|entry|meta|inst|instr|alias|indata|outdata|wmask|gpaddr|"
    r"pbmt|paddr|vaddr|blk|be\b|num|count|value)",
    re.IGNORECASE,
)
CONTROL = re.compile(
    r"(valid|ready|flush|fencei|state|waymask|sramHits|hit|miss|exception|error|"
    r"corrupt|denied|enable|req|ack|empty|full|wrap|flag|sel|_oh|writeen|readen|"
    r"write|read|touch|victim|inject|status|target|wfi|bp[uU]|redirect|refill|"
    r"lock|free|stall|conflict|same|updated|fire|send|issue)",
    re.IGNORECASE,
)
STORAGE = re.compile(r"(^|/)(array_[^/]*\.sv|sram_array_[^/]*\.sv)$")


def parse_dat(path: Path):
    for raw in path.open(errors="replace"):
        if not raw.startswith("C "):
            continue
        body = raw[3:]
        try:
            payload, count = body.rsplit("' ", 1)
            count = int(count.strip())
        except ValueError:
            continue
        fields: dict[str, str] = {}
        for segment in payload.split(SEP):
            if not segment:
                continue
            key, _, value = segment.partition("\x02")
            fields[key] = value
        yield count, fields


def classify(source: str, description: str) -> str:
    """Return ``storage``, ``control`` or ``payload`` for a toggle point."""
    if STORAGE.search(source):
        return "storage"
    name = description.split(":", 1)[0]
    if PAYLOAD.search(name):
        return "payload"
    if CONTROL.search(name):
        return "control"
    return "other"


def analyse(run: Path, dut_filter: str | None = None) -> dict:
    manifest = json.loads((run / "rtl-coverage-manifest.json").read_text())
    report: dict = {"run": str(run), "duts": {}}
    for native in manifest["native"]:
        name = native["build"]["name"]
        dut = native.get("dut", "")
        if dut_filter and dut_filter not in name and dut_filter != dut:
            continue
        points: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        for count, fields in parse_dat(Path(native["path"])):
            source = fields.get("f", "")
            if Path(source).stem.endswith("_top"):
                continue
            key = (source, fields.get("l", ""), fields.get("n", ""),
                   fields.get("t", ""), fields.get("o", ""))
            points[key][0] += 1
            points[key][1] += 1 if count > 0 else 0

        kinds = ("line", "branch", "toggle")
        totals = {kind: {"total": 0, "covered": 0} for kind in kinds}
        files: dict[str, dict] = {}
        toggle_class = Counter()
        for (source, line, column, kind, description), (total, covered) in points.items():
            if kind not in totals:
                continue
            totals[kind]["total"] += total
            totals[kind]["covered"] += covered
            entry = files.setdefault(source, {
                **{f"{k}_total": 0 for k in kinds},
                **{f"{k}_covered": 0 for k in kinds},
            })
            entry[f"{kind}_total"] += total
            entry[f"{kind}_covered"] += covered
            if kind == "toggle":
                toggle_class[classify(source, description)] += total - covered

        report["duts"][name] = {
            "dut": dut,
            "totals": totals,
            "files": {
                source: {
                    **entry,
                    "storage": bool(STORAGE.search(source)),
                }
                for source, entry in sorted(files.items())
            },
            "uncovered_toggle_by_class": dict(toggle_class),
            "uncovered_points": [
                {
                    "source": source,
                    "line": int(line) if str(line).isdigit() else line,
                    "column": column,
                    "kind": kind,
                    "description": description,
                    "class": classify(source, description) if kind == "toggle" else None,
                }
                for (source, line, column, kind, description), (total, covered)
                in points.items() if covered == 0
            ],
        }
    return report


def pct(covered: int, total: int) -> float:
    return 100.0 * covered / total if total else 100.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    parser.add_argument("--dut", help="only this DUT (build name or dut id)")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--list", choices=("branch", "line", "toggle"),
                        help="list uncovered points of one kind")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    report = analyse(args.run, args.dut)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")

    for name, data in report["duts"].items():
        print(f"\n== {name} ({data['dut']})")
        for kind in ("line", "branch", "toggle"):
            total = data["totals"][kind]["total"]
            covered = data["totals"][kind]["covered"]
            print(f"  {kind:7s} {covered}/{total} = {pct(covered, total):.2f}%")
        cls = data["uncovered_toggle_by_class"]
        if cls:
            print("  uncovered toggle by class: " +
                  ", ".join(f"{k}={v}" for k, v in sorted(cls.items())))
        if args.list:
            rows = [p for p in data["uncovered_points"] if p["kind"] == args.list]
            print(f"  uncovered {args.list}: {len(rows)}")
            for point in rows[:args.limit]:
                print(f"    {Path(point['source']).name}:{point['line']} "
                      f"{point['description']}")
            if len(rows) > args.limit:
                print(f"    ... {len(rows) - args.limit} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
