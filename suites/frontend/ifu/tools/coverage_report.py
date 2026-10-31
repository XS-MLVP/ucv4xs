#!/usr/bin/env python3
"""Summarize native Verilator line/branch/toggle coverage from a toffee run.

The toffee runner merges every testcase's native table into one
``coverage.dat`` per DUT build and also exports LCOV line data.  This tool
reads the native table directly so that the three metrics are kept separate:

* line: ``v_line`` point hits and unique generated-RTL source lines expanded
  from the ``l``/``S`` fields;
* branch: ``v_branch`` condition-arm bins;
* toggle: ``v_toggle`` transition bins, plus the set of signal bits that
  changed at least once.

Uncovered items keep the generated-RTL line text so the gap can be mapped
back to the Scala construct and to a functional point.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

POINT = re.compile(rb"C '(.*)' ([0-9]+)\n?\Z")
SPAN = re.compile(r"([1-9][0-9]*)(?:-([1-9][0-9]*))?")
TOGGLE = re.compile(r"^(.*?)(?:\[([0-9]+)\])?:([01xX])->([01xX])$")


def fields(raw: bytes) -> dict[str, str]:
    return {key.decode("utf-8", "replace"): value.decode("utf-8", "replace")
            for part in raw.split(b"\x01") if b"\x02" in part
            for key, value in (part.split(b"\x02", 1),)}


def read_points(path: Path):
    with path.open("rb") as stream:
        if stream.readline() != b"# SystemC::Coverage-3\n":
            raise ValueError(f"not a native coverage table: {path}")
        for line in stream:
            match = POINT.fullmatch(line)
            if match is None:
                raise ValueError(f"bad coverage record in {path}")
            meta = fields(match[1])
            yield meta, int(match[2])


def counted_lines(meta: dict[str, str]) -> set[int]:
    lines = {int(meta["l"])}
    for span in meta.get("S", "").split(","):
        if not span:
            continue
        match = SPAN.fullmatch(span)
        if match is None:
            raise ValueError(f"bad source span {span!r}")
        first, last = int(match[1]), int(match[2] or match[1])
        lines.update(range(first, last + 1))
    return lines


def source_cache(path: Path, cache: dict[Path, list[str]]) -> list[str]:
    if path not in cache:
        cache[path] = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return cache[path]


def source_line(path: Path, number: int, cache: dict[Path, list[str]]) -> str:
    lines = source_cache(path, cache)
    return lines[number - 1].strip() if 0 < number <= len(lines) else ""


def check_manifest(manifest: dict) -> None:
    if manifest.get("format") != "xreactor-execution" or manifest.get("state") != "committed":
        raise ValueError("an executed/committed toffee manifest is required")


def parse_lcov(path: Path, rtl: Path) -> tuple[dict[int, int], list[dict]]:
    """Return DA counts and BRDA arms for the core generated-RTL file only."""

    lines: dict[int, int] = {}
    branches: list[dict] = []
    source = None
    for record in path.read_text(encoding="utf-8").splitlines():
        if record.startswith("SF:"):
            source = Path(record[3:]).resolve()
            continue
        if source != rtl.resolve():
            if record == "end_of_record":
                source = None
            continue
        if record.startswith("DA:"):
            number, count = record[3:].split(",", 1)
            lines[int(number)] = max(lines.get(int(number), 0), int(count))
        elif record.startswith("BRDA:"):
            number, block, arm, count = record[5:].split(",", 3)
            branches.append({"line": int(number), "block": int(block), "arm": arm,
                             "hit": 0 if count in {"-", ""} else int(count)})
        elif record == "end_of_record":
            source = None
    return lines, branches


def summarize_build(manifest_path: Path, row: dict, cache, lcov: Path | None = None) -> dict:
    native = Path(row["path"])
    if not native.is_file():
        raise FileNotFoundError(native)
    build = row["build"]
    rtl_paths = [Path(path) for path in build["files"]
                 if Path(path).suffix == ".v" and not Path(path).stem.endswith("_top")]
    if len(rtl_paths) != 1:
        raise ValueError(f"expected one generated RTL file per build, got {rtl_paths}")
    rtl = rtl_paths[0]
    stats = {
        "line": {"points": 0, "hit": 0},
        "branch": {"points": 0, "hit": 0},
        "toggle": {"points": 0, "hit": 0},
    }
    lcov_lines: dict[int, int] = {}
    lcov_branches: list[dict] = []
    if lcov is not None and lcov.is_file():
        lcov_lines, lcov_branches = parse_lcov(lcov, rtl)
    lines: dict[int, bool] = {}
    branch_points: list[dict] = []
    toggle_bins: list[dict] = []
    modules: defaultdict[str, dict] = defaultdict(lambda: {
        "line": {"points": 0, "hit": 0}, "branch": {"points": 0, "hit": 0},
        "toggle": {"points": 0, "hit": 0}})
    toggle_bits: dict[str, bool] = {}
    core = rtl.resolve()
    for meta, count in read_points(native):
        if Path(meta.get("f", "")).resolve() != core:
            continue
        page = meta.get("page", "")
        kind, _, module = page.partition("/")
        kind = kind[2:] if kind.startswith("v_") else kind
        if kind not in stats or not module:
            continue
        hit = count > 0
        stats[kind]["points"] += 1
        stats[kind]["hit"] += int(hit)
        modules[module][kind]["points"] += 1
        modules[module][kind]["hit"] += int(hit)
        line = int(meta["l"])
        if kind == "line":
            for number in counted_lines(meta):
                lines[number] = lines.get(number, False) or hit
        elif kind == "branch":
            branch_points.append({"line": line, "arm": meta.get("o", ""), "hit": count,
                                  "verilog": source_line(rtl, line, cache)})
        elif kind == "toggle":
            label = meta.get("o", "")
            match = TOGGLE.match(label)
            if match is None:
                key = label
            else:
                key = f"{match.group(1)}[{match.group(2)}]" if match.group(2) else match.group(1)
            toggle_bits[key] = toggle_bits.get(key, False) or hit
            toggle_bins.append({"line": line, "transition": label, "signal_bit": key,
                                "hit": count, "verilog": source_line(rtl, line, cache)})
    if lcov_lines:
        lines = {number: count > 0 for number, count in lcov_lines.items()}
    uncovered_lines = [
        {"line": number, "verilog": source_line(rtl, number, cache)}
        for number, hit in sorted(lines.items()) if not hit
    ]
    uncovered_branches = [point for point in branch_points if point["hit"] == 0]
    uncovered_toggles = [point for point in toggle_bins if point["hit"] == 0]
    total_lines = len(lines)
    hit_lines = sum(lines.values())
    return {
        "dut": build["name"],
        "build_id": build["build_id"],
        "native": str(native),
        "rtl": str(rtl),
        "rtl_sha256": build["files"].get(str(rtl)),
        "line": {
            "point_hit": stats["line"]["hit"], "point_total": stats["line"]["points"],
            "source_hit": hit_lines, "source_total": total_lines,
            "percent": 100 * hit_lines / total_lines if total_lines else 0.0,
            "uncovered": uncovered_lines,
        },
        "branch": {
            "hit": stats["branch"]["hit"], "total": stats["branch"]["points"],
            "percent": 100 * stats["branch"]["hit"] / stats["branch"]["points"]
            if stats["branch"]["points"] else 100.0,
            "uncovered": uncovered_branches,
        },
        "toggle": {
            "bin_hit": stats["toggle"]["hit"], "bin_total": stats["toggle"]["points"],
            "bin_percent": 100 * stats["toggle"]["hit"] / stats["toggle"]["points"]
            if stats["toggle"]["points"] else 100.0,
            "bits_hit": sum(toggle_bits.values()), "bits_total": len(toggle_bits),
            "bits_percent": 100 * sum(toggle_bits.values()) / len(toggle_bits)
            if toggle_bits else 100.0,
            "uncovered_bins": uncovered_toggles,
            "uncovered_bits": sorted(bit for bit, hit in toggle_bits.items() if not hit),
        },
        "modules": {name: dict(value) for name, value in sorted(modules.items())},
    }


def make_report(manifest_path: Path) -> dict:
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    check_manifest(manifest)
    cache: dict[Path, list[str]] = {}
    duts = {}
    lcov_by_build: dict[str, Path] = {}
    last_build = None
    for row in manifest["artifacts"]:
        if row["kind"] == "native":
            last_build = row["build"]["build_id"]
        elif row["kind"] == "lcov" and last_build is not None:
            lcov_by_build[last_build] = Path(row["path"])
    for row in manifest["artifacts"]:
        if row["kind"] == "native":
            summary = summarize_build(manifest_path, row, cache,
                                      lcov_by_build.get(row["build"]["build_id"]))
            duts[summary["dut"]] = summary
    return {
        "format": "ifu-native-coverage-report",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "pytest_exitstatus": manifest.get("pytest_exitstatus"),
        "duts": duts,
    }


def markdown(report: dict) -> str:
    lines = ["# IFU native coverage", "",
             f"Manifest: `{report['manifest']}`", ""]
    for dut, data in report["duts"].items():
        lines += [f"## {dut}", "",
                  "| metric | hit | total | percent |", "|---|---:|---:|---:|",
                  f"| line (source lines) | {data['line']['source_hit']} | "
                  f"{data['line']['source_total']} | {data['line']['percent']:.2f}% |",
                  f"| branch | {data['branch']['hit']} | {data['branch']['total']} | "
                  f"{data['branch']['percent']:.2f}% |",
                  f"| toggle transitions | {data['toggle']['bin_hit']} | "
                  f"{data['toggle']['bin_total']} | {data['toggle']['bin_percent']:.2f}% |",
                  f"| toggle signal bits | {data['toggle']['bits_hit']} | "
                  f"{data['toggle']['bits_total']} | {data['toggle']['bits_percent']:.2f}% |",
                  ""]
        if data["line"]["uncovered"]:
            lines.append("Uncovered source lines:")
            for item in data["line"]["uncovered"]:
                lines.append(f"- L{item['line']}: `{item['verilog']}`")
            lines.append("")
        if data["branch"]["uncovered"]:
            lines.append("Uncovered branch arms:")
            for item in data["branch"]["uncovered"]:
                lines.append(f"- L{item['line']} {item['arm']}: `{item['verilog']}`")
            lines.append("")
        if data["toggle"]["uncovered_bits"]:
            lines.append("Signal bits that never changed:")
            lines.append(", ".join(f"`{bit}`" for bit in data["toggle"]["uncovered_bits"]))
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    report = make_report(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(report), encoding="utf-8")
    if args.previous:
        old = json.loads(args.previous.read_text(encoding="utf-8"))
        for dut, data in report["duts"].items():
            before = old.get("duts", {}).get(dut)
            if before is None:
                continue
            print(f"{dut}: line {before['line']['percent']:.2f}% -> {data['line']['percent']:.2f}%, "
                  f"branch {before['branch']['percent']:.2f}% -> {data['branch']['percent']:.2f}%, "
                  f"toggle {before['toggle']['bin_percent']:.2f}% -> {data['toggle']['bin_percent']:.2f}%")
    for dut, data in report["duts"].items():
        print(f"{dut}: line {data['line']['source_hit']}/{data['line']['source_total']} "
              f"({data['line']['percent']:.2f}%), branch {data['branch']['hit']}/{data['branch']['total']} "
              f"({data['branch']['percent']:.2f}%), toggle {data['toggle']['bin_hit']}/{data['toggle']['bin_total']} "
              f"({data['toggle']['bin_percent']:.2f}%), bits {data['toggle']['bits_hit']}/{data['toggle']['bits_total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
