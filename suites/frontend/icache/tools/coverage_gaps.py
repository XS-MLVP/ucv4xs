#!/usr/bin/env python3
"""Report line-coverage gaps for one toffee run, grouped by module.

The methodology treats an uncovered line as evidence that the functional-point
definition is incomplete, so the report deliberately prints the surrounding
source text and the Scala origin reference. A gap may only be closed by adding
a functional point that reaches it, or by recording a written unreachability
argument - never by editing RTL or dropping the denominator.

Usage::

    python3 tools/coverage_gaps.py results/toffee-full-1
    python3 tools/coverage_gaps.py results/toffee-full-1 --dut waylookup
    python3 tools/coverage_gaps.py results/toffee-full-1 --json out.json
"""

from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCALA_REF = re.compile(r"//\s*(?P<file>[^\s:]+\.scala):(?P<line>\d+)")


VERILATOR_COVERAGE = Path(str(ucv_paths.project_root() / '.tools/verilator/bin/verilator_coverage'))


def dat_to_info(dat: Path, into: Path) -> Path:
    """Convert one Verilator ``.dat`` into LCOV so every instrumented file is seen.

    The managed runner's merged ``coverage.info`` keeps only a subset of source
    paths (it drops the picker-generated DUT wrapper and some macros), so gap
    analysis reads the raw database instead. This changes nothing about the
    denominator Verilator measured.
    """
    into.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(VERILATOR_COVERAGE), "--write-info", str(into), str(dat)],
                   check=True, capture_output=True)
    return into


def parse_info(path: Path) -> dict[str, list[tuple[int, int]]]:
    """Return {source file: [(line, count), ...]} from a verilator .info file."""
    sources: dict[str, list[tuple[int, int]]] = defaultdict(list)
    current: str | None = None
    for raw in path.read_text(errors="replace").splitlines():
        if raw.startswith("SF:"):
            current = raw[3:].strip()
        elif raw.startswith("DA:") and current is not None:
            fields = raw[3:].split(",")
            sources[current].append((int(fields[0]), int(fields[1])))
    return sources


def scala_origin(source_line: str) -> str | None:
    match = SCALA_REF.search(source_line)
    return f"{match.group('file')}:{match.group('line')}" if match else None


def is_declaration_line(text: str) -> bool:
    """True for lines that only declare structure, never execute.

    Verilator still assigns them line points when a declared wire feeds an
    instrumented expression, so a raw line count mixes ports, wires and
    statements. Reporting both keeps the artifact visible instead of dropping
    it from the denominator.
    """
    stripped = text.strip()
    if not stripped or stripped.startswith("//"):
        return True
    if re.match(r"^(input|output|inout)\b", stripped):
        return True
    if re.match(r"^(wire|reg|logic)\b", stripped) and "=" not in stripped:
        return True
    if stripped in ("end", "begin", "else begin", "end else begin", "endmodule"):
        return True
    if stripped in (");", "(", ");"):
        return True
    return False


def is_picker_wrapper(source: str) -> bool:
    """The generated *_top harness is testbench glue, not RTL under test.

    The BPU project excludes it as ``picker_wrapper``; counting it would dilute
    the DUT's line coverage with wiring that is never stimulated.
    """
    stem = Path(source).stem
    return stem.endswith("_top")


def analyse(run: Path, dut: str | None) -> dict:
    infos = sorted(run.glob("native/*/coverage.info"))
    dats = sorted(run.glob("native/*/coverage.dat"))
    if dats:
        # Prefer the raw database: it still carries the DUT wrapper and macros.
        infos = [dat_to_info(dat, Path(tempfile.mkdtemp()) / "coverage.info")
                 for dat in dats]
    elif not infos:
        raise SystemExit(f"no coverage database under {run}/native")
    merged: dict[str, dict[int, int]] = defaultdict(dict)
    for info in infos:
        for source, entries in parse_info(info).items():
            for line, count in entries:
                merged[source][line] = merged[source].get(line, 0) + count

    report: dict = {"run": str(run), "sources": {}}
    for source, counts in sorted(merged.items()):
        if is_picker_wrapper(source):
            continue
        text = Path(source).read_text(errors="replace").splitlines() if Path(source).is_file() else []
        uncovered = sorted(line for line, count in counts.items() if count == 0)
        if not uncovered:
            continue
        # Group contiguous uncovered lines into ranges, keeping a little context.
        groups: list[list[int]] = []
        for line in uncovered:
            if groups and line == groups[-1][-1] + 1:
                groups[-1].append(line)
            else:
                groups.append([line])
        blocks = []
        for group in groups:
            first, last = group[0], group[-1]
            context = []
            for line in range(max(1, first - 2), min(len(text), last + 2) + 1):
                origin = scala_origin(text[line - 1]) if line <= len(text) else None
                context.append({
                    "line": line,
                    "text": text[line - 1].strip() if line <= len(text) else "",
                    "covered": counts.get(line, 0) > 0,
                    "scala": origin,
                })
            blocks.append({
                "first": first,
                "last": last,
                "lines": len(group),
                "scala_origins": sorted({c["scala"] for c in context if c["scala"]}),
                "context": context,
            })
        declaration_lines = [line for line in uncovered
                             if line <= len(text) and is_declaration_line(text[line - 1])]
        statements = [line for line in counts
                      if line <= len(text) and not is_declaration_line(text[line - 1])]
        statement_covered = [line for line in statements if counts[line] > 0]
        report["sources"][source] = {
            "total": len(counts),
            "covered": sum(1 for c in counts.values() if c > 0),
            "uncovered_lines": uncovered,
            "uncovered_declarations": declaration_lines,
            "statement_total": len(statements),
            "statement_covered": len(statement_covered),
            "blocks": [block for block in blocks
                       if any(line not in set(declaration_lines) for line in range(
                           block["first"], block["last"] + 1))],
        }
    report["summary"] = {
        source: {
            "total": data["total"],
            "covered": data["covered"],
            "percent": round(100.0 * data["covered"] / data["total"], 2) if data["total"] else 0.0,
            "uncovered": len(data["uncovered_lines"]),
            "statement_total": data["statement_total"],
            "statement_covered": data["statement_covered"],
            "statement_percent": round(
                100.0 * data["statement_covered"] / data["statement_total"], 2
            ) if data["statement_total"] else 0.0,
            "uncovered_declarations": len(data["uncovered_declarations"]),
        }
        for source, data in report["sources"].items()
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path, help="toffee output directory")
    parser.add_argument("--dut", help="only report sources for this DUT name")
    parser.add_argument("--json", type=Path, help="also write the full report as JSON")
    parser.add_argument("--max-blocks", type=int, default=0,
                        help="limit printed blocks per source (0 = all)")
    args = parser.parse_args()

    report = analyse(args.run, args.dut)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")

    for source, summary in report["summary"].items():
        if args.dut and args.dut not in source:
            continue
        print(f"{source}")
        print(f"  all lines {summary['covered']}/{summary['total']} = {summary['percent']:.2f}%"
              f"  uncovered={summary['uncovered']}"
              f"  (of which declarations: {summary['uncovered_declarations']})")
        print(f"  statements {summary['statement_covered']}/{summary['statement_total']}"
              f" = {summary['statement_percent']:.2f}%")
        blocks = report["sources"][source]["blocks"]
        shown = blocks if not args.max_blocks else blocks[:args.max_blocks]
        for block in shown:
            origins = ", ".join(block["scala_origins"][:2]) or "-"
            print(f"  [{block['first']}-{block['last']}] {block['lines']} lines  scala={origins}")
        if args.max_blocks and len(blocks) > args.max_blocks:
            print(f"  ... {len(blocks) - args.max_blocks} more blocks (see --json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
