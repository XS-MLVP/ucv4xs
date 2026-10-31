#!/usr/bin/env python3
"""Merge FTQ native coverage and expose line/toggle/branch gaps.

Verilator's native database is the source of truth.  The script keeps the
three point kinds separate, maps only the active DUT closure to RTL, and
prints every uncovered RTL line/branch/toggle with its source text.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections import defaultdict
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RTL_ROOT = ROOT / "rtl"
TOOL = ROOT.parents[2] / ".tools" / "verilator" / "bin" / "verilator_coverage"
POINT = re.compile(r"^C '(.*)' ([0-9]+)$")


def metadata(raw: str) -> dict[str, str]:
    return dict(field.split("\x02", 1) for field in raw.split("\x01") if "\x02" in field)


def covered_lines(fields: dict[str, str]) -> set[int]:
    lines = {int(fields["l"])}
    for span in fields.get("S", "").split(","):
        if not span:
            continue
        match = re.fullmatch(r"([1-9][0-9]*)(?:-([1-9][0-9]*))?", span)
        if match is None:
            raise ValueError(f"invalid line span: {span!r}")
        first = int(match[1])
        last = int(match[2] or first)
        lines.update(range(first, last + 1))
    return lines


def merge(dut: str, inputs: list[Path], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [str(TOOL), "--write", str(output), *map(str, inputs)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output


def top_name(dut: str) -> str:
    data = json.loads((RTL_ROOT / dut / "source.json").read_text())
    return data["top"]


def source_path(recorded: str, dut: str, top: str) -> Path | None:
    name = Path(recorded).name
    # Picker copies the elaborated top into <Top>Dut.v for instrumentation.
    # Attribute that copy back to the byte-identical RTL closure source.
    if name == f"{top}Dut.v":
        candidate = RTL_ROOT / dut / f"{top}.sv"
        if candidate.is_file():
            return candidate
    if name == f"{top}Dut_top.sv":
        return None
    candidate = RTL_ROOT / dut / name
    return candidate if candidate.is_file() else None


def native_line_counts(records: list[str], dut: str, top: str) -> tuple[dict[tuple[str, int], int], Path]:
    with tempfile.TemporaryDirectory(prefix="ftq-lines-") as directory:
        data = Path(directory) / "line-branch.dat"
        info = Path(directory) / "line-branch.info"
        data.write_text("# SystemC::Coverage-3\n" + "\n".join(records) + "\n")
        subprocess.run([str(TOOL), "--write-info", str(info), str(data)],
                       check=True, capture_output=True, text=True)
        counts: dict[tuple[str, int], int] = {}
        source = None
        for record in info.read_text().splitlines():
            if record.startswith("SF:"):
                path = source_path(record[3:], dut, top)
                source = path.name if path is not None else None
            elif record.startswith("DA:") and source is not None:
                line, count = map(int, record[3:].split(","))
                counts[(source, line)] = count
        return counts, info


def summarize(merged: Path, dut: str) -> dict[str, object]:
    top = top_name(dut)
    line_points = defaultdict(lambda: {"total": 0, "hit": 0})
    branch_points = defaultdict(lambda: {"total": 0, "hit": 0})
    toggle_points = defaultdict(lambda: {"total": 0, "hit": 0})
    line_sources: dict[str, list[str]] = {}
    line_modules: dict[tuple[str, int], set[str]] = defaultdict(set)
    uncovered_branches = []
    uncovered_toggles = []
    other_sources = Counter()
    native_inputs = []

    for record in merged.read_text(encoding="utf-8").splitlines():
        match = POINT.match(record)
        if match is None:
            continue
        fields = metadata(match[1])
        page = fields.get("page", "")
        kind, _, module = page.partition("/")
        hit = int(match[2]) > 0
        if kind not in {"v_line", "v_branch", "v_toggle"}:
            continue
        path = source_path(fields.get("f", ""), dut, top)
        if path is None:
            other_sources[Path(fields.get("f", "")).name] += 1
            continue
        if path.name not in line_sources:
            line_sources[path.name] = path.read_text().splitlines()
        text = line_sources[path.name]
        line = int(fields["l"])
        line_text = text[line - 1].strip() if 0 < line <= len(text) else ""
        if kind == "v_line":
            bucket = line_points[module]
            bucket["total"] += 1
            bucket["hit"] += hit
            for number in covered_lines(fields):
                line_modules[(path.name, number)].add(module)
            native_inputs.append(record)
        elif kind == "v_branch":
            native_inputs.append(record)
            bucket = branch_points[module]
            bucket["total"] += 1
            bucket["hit"] += hit
            for number in covered_lines(fields):
                line_modules[(path.name, number)].add(module)
            if not hit:
                uncovered_branches.append({
                    "module": module, "file": path.name, "line": line,
                    "arm": fields.get("o", ""), "verilog": line_text,
                })
        else:
            bucket = toggle_points[module]
            bucket["total"] += 1
            bucket["hit"] += hit
            if not hit:
                uncovered_toggles.append({
                    "module": module, "file": path.name, "line": line,
                    "signal": fields.get("o", ""), "verilog": line_text,
                })

    native_counts, info = native_line_counts(native_inputs, dut, top)
    covered_count = sum(1 for count in native_counts.values() if count > 0)
    source_total = len(native_counts)
    line_summary = {"total": source_total, "hit": covered_count,
                    "percent": 100.0 * covered_count / source_total if source_total else 0.0}
    uncovered_lines = []
    for (file, line), count in sorted(native_counts.items()):
        if count > 0:
            continue
        text = line_sources[file]
        uncovered_lines.append({
            "module": ",".join(sorted(line_modules.get((file, line), {"unknown"}))),
            "file": file,
            "line": line,
            "signal": "",
            "verilog": text[line - 1].strip() if 0 < line <= len(text) else "",
        })
    branch_total = sum(row["total"] for row in branch_points.values())
    branch_hit = sum(row["hit"] for row in branch_points.values())
    toggle_total = sum(row["total"] for row in toggle_points.values())
    toggle_hit = sum(row["hit"] for row in toggle_points.values())
    return {
        "dut": dut,
        "rtl_files": sorted(line_sources),
        "line": line_summary,
        "line_points": {
            "total": sum(row["total"] for row in line_points.values()),
            "hit": sum(row["hit"] for row in line_points.values()),
        },
        "branch": {
            "total": branch_total, "hit": branch_hit,
            "percent": 100.0 * branch_hit / branch_total if branch_total else 0.0,
            "by_module": dict(sorted(branch_points.items())),
        },
        "toggle": {
            "total": toggle_total, "hit": toggle_hit,
            "percent": 100.0 * toggle_hit / toggle_total if toggle_total else 0.0,
            "by_module": dict(sorted(toggle_points.items())),
        },
        "uncovered_lines": sorted(uncovered_lines, key=lambda row: (row["module"], row["line"])),
        "uncovered_branches": sorted(uncovered_branches, key=lambda row: (row["module"], row["line"], row["arm"])),
        "uncovered_toggles": sorted(uncovered_toggles, key=lambda row: (row["module"], row["line"], row["signal"])),
        "non_rtl_sources": dict(sorted(other_sources.items())),
    }


def markdown(results: list[dict[str, object]]) -> str:
    out = ["# FTQ 原生覆盖率缺口", ""]
    out.append("| DUT | 行覆盖 | 行点 | 分支 | Toggle |")
    out.append("|---|---:|---:|---:|---:|")
    for row in results:
        out.append(
            f"| {row['dut']} | {row['line']['hit']}/{row['line']['total']} "
            f"({row['line']['percent']:.1f}%) | {row['line_points']['hit']}/{row['line_points']['total']} | "
            f"{row['branch']['hit']}/{row['branch']['total']} ({row['branch']['percent']:.1f}%) | "
            f"{row['toggle']['hit']}/{row['toggle']['total']} ({row['toggle']['percent']:.1f}%) |"
        )
    for row in results:
        out += ["", f"## {row['dut']}", "", "### 未覆盖 RTL 行"]
        for gap in row["uncovered_lines"]:
            out.append(f"- `{gap['file']}:{gap['line']}` [{gap['module']}] "
                       f"`{gap['signal']}` — `{gap['verilog']}`")
        if not row["uncovered_lines"]:
            out.append("- 无")
        out += ["", "### 未覆盖分支"]
        for gap in row["uncovered_branches"]:
            out.append(f"- `{gap['file']}:{gap['line']}` [{gap['module']}] arm=`{gap['arm']}` "
                       f"— `{gap['verilog']}`")
        if not row["uncovered_branches"]:
            out.append("- 无")
        out += ["", "### 未覆盖 Toggle"]
        for gap in row["uncovered_toggles"]:
            out.append(f"- `{gap['file']}:{gap['line']}` [{gap['module']}] "
                       f"`{gap['signal']}` — `{gap['verilog']}`")
        if not row["uncovered_toggles"]:
            out.append("- 无")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--dut", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="ftq-cov-") as temporary:
        for dut in args.dut:
            directory = args.result_dir / "coverage" / dut
            inputs = sorted(directory.glob("*.dat"))
            if not inputs:
                print(f"{dut}: no coverage inputs (selection exercised no case for this DUT)")
                continue
            merged = merge(dut, inputs, Path(temporary) / f"{dut}.dat")
            result = summarize(merged, dut)
            result["inputs"] = str(len(inputs))
            result["input_bytes"] = sum(path.stat().st_size for path in inputs)
            results.append(result)
    if not results:
        raise SystemExit("no coverage inputs for any requested DUT")
    (args.output / "coverage.json").write_text(json.dumps(results, indent=2) + "\n")
    (args.output / "coverage-gaps.md").write_text(markdown(results))
    for row in results:
        print(f"{row['dut']}: line {row['line']['hit']}/{row['line']['total']} "
              f"({row['line']['percent']:.1f}%), branch {row['branch']['hit']}/{row['branch']['total']} "
              f"({row['branch']['percent']:.1f}%), toggle {row['toggle']['hit']}/{row['toggle']['total']} "
              f"({row['toggle']['percent']:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
