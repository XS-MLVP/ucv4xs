#!/usr/bin/env python3
"""Audit an if/else-if/else-if priority chain for line-attribution artifacts.

Verilator (with firtool output) hoists a chain's conditions into precomputed
wires, so the final ``else if`` line often keeps a zero count even though its
branch body executes. This tool reports, per chain, the condition and body
counts so a coverage gap can be classified as an artifact or a real hole.

Usage::

    python3 tools/chain_audit.py results/<run> dut/replacer/ReplacerDut.v \
        --pattern 'set_touch_ways_({lane})_({index})_valid'
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def load_counts(run: Path) -> dict[str, dict[int, int]]:
    counts: dict[str, dict[int, int]] = defaultdict(dict)
    for info in sorted(run.glob("native/*/coverage.info")):
        current = None
        for line in info.read_text(errors="replace").splitlines():
            if line.startswith("SF:"):
                current = line[3:].strip()
            elif line.startswith("DA:") and current:
                fields = line[3:].split(",")
                counts[current][int(fields[0])] = counts[current].get(int(fields[0]), 0) + int(fields[1])
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", type=Path)
    ap.add_argument("source")
    ap.add_argument("--pattern", required=True,
                    help="regex with named groups lane and index")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    counts = load_counts(args.run)
    key = next((path for path in counts if path.endswith(Path(args.source).name)), None)
    if key is None:
        raise SystemExit(f"{args.source} not present in the run's coverage data")
    lines = Path(key).read_text(errors="replace").splitlines()
    pattern = re.compile(rf"(?:\s*\}}\s*)?(?:else\s+)?if\s*\({args.pattern}\)")

    chains: dict[str, dict[int, int]] = defaultdict(dict)
    for number, text in enumerate(lines, start=1):
        match = pattern.search(text)
        if match:
            chains[match["index"]][int(match["lane"])] = number

    stats = {"chains": len(chains), "cond_zero": 0, "cond_nonzero": 0,
             "body_zero": 0, "body_nonzero": 0}
    holes: list[dict] = []
    for index, lanes in sorted(chains.items()):
        for lane, number in sorted(lanes.items()):
            cond = counts[key].get(number, 0)
            body = counts[key].get(number + 1, 0)
            stats["cond_nonzero" if cond else "cond_zero"] += 1
            stats["body_nonzero" if body else "body_zero"] += 1
            if not body:
                holes.append({"index": index, "lane": lane, "line": number,
                              "condition_count": cond, "body_count": body})
    result = {"source": key, "stats": stats, "behavioral_holes": holes}
    print(json.dumps(result, indent=2))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2) + "\n")
    return 1 if holes else 0


if __name__ == "__main__":
    raise SystemExit(main())
