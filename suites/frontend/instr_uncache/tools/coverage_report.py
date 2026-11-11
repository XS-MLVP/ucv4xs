#!/usr/bin/env python3
"""Per-DUT line/branch/toggle coverage from one toffee run manifest.

The Picker package contains three kinds of source files:

* the generated RTL copy (``<Top>Dut.v`` for a leaf, or the top RTL file);
* the generated closure RTL under ``rtl/*.sv`` used by the top DUT;
* a Picker wrapper ``<Top>Dut_top.sv`` whose DA lines are DPI/port glue.

The wrapper is excluded, otherwise its generated accessors would look like
untested design lines.  Line data comes from LCOV when Verilator emitted it;
branch/toggle bins are read from the native table because LCOV does not carry
them.  A real RTL file with no line/branch instrumentation is reported
explicitly instead of being counted as 100% covered.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
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
            yield fields(match[1]), int(match[2])


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


def source_line(path: Path, number: int, cache: dict[Path, list[str]]) -> str:
    if path not in cache:
        cache[path] = path.read_text(encoding="utf-8", errors="replace").splitlines()
    lines = cache[path]
    return lines[number - 1].strip() if 0 < number <= len(lines) else ""


def check_manifest(manifest: dict) -> None:
    if manifest.get("format") != "xreactor-execution" or manifest.get("state") != "committed":
        raise ValueError("an executed/committed toffee manifest is required")


def parse_lcov(path: Path) -> dict[Path, dict]:
    """Return per-source DA counts and BRDA arms (toggle stays native)."""
    records: dict[Path, dict] = {}
    source = None
    if not path.is_file():
        return records
    for record in path.read_text(encoding="utf-8").splitlines():
        if record.startswith("SF:"):
            source = Path(record[3:]).resolve()
            records.setdefault(source, {"lines": {}, "branches": []})
            continue
        if source is None:
            continue
        if record.startswith("DA:"):
            number, count = record[3:].split(",", 1)
            lines = records[source]["lines"]
            lines[int(number)] = max(lines.get(int(number), 0), int(count))
        elif record.startswith("BRDA:"):
            number, block, arm, count = record[5:].split(",", 3)
            records[source]["branches"].append({
                "line": int(number), "block": int(block), "arm": arm,
                "hit": 0 if count in {"-", ""} else int(count)})
        elif record == "end_of_record":
            source = None
    return records


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def is_wrapper(path: Path) -> bool:
    return path.name.endswith("_top.sv") or path.name.endswith("_top.v")


def summarize_file(path: Path, native: dict, lcov: dict, cache) -> dict:
    lines = dict(lcov.get("lines", {}))
    branch_points = list(native["branch"])
    toggle_points = list(native["toggle"])
    for point in native["line"]:
        for number in point["lines"]:
            lines.setdefault(number, int(point["hit"] > 0))
    uncovered_lines = [
        {"line": number, "verilog": source_line(path, number, cache)}
        for number, count in sorted(lines.items()) if count <= 0
    ]
    uncovered_branches = [point for point in branch_points if point["hit"] == 0]
    toggle_bits: dict[str, bool] = {}
    for point in toggle_points:
        label = point["transition"]
        match = TOGGLE.match(label)
        key = f"{match.group(1)}[{match.group(2)}]" if match and match.group(2) else (
            match.group(1) if match else label)
        toggle_bits[key] = toggle_bits.get(key, False) or point["hit"] > 0
    uncovered_toggles = [point for point in toggle_points if point["hit"] == 0]
    line_hit = sum(count > 0 for count in lines.values())
    instrumentation = "line+branch+toggle"
    if not lines and not branch_points:
        instrumentation = "no line/branch points emitted (pure wiring or tool boundary)"
    elif not branch_points:
        instrumentation = "line+toggle; no branch points emitted"
    return {
        "path": str(path),
        "rtl_sha256": file_hash(path) if path.is_file() else None,
        "line": {
            "point_hit": sum(point["hit"] > 0 for point in native["line"]),
            "point_total": len(native["line"]),
            "source_hit": line_hit,
            "source_total": len(lines),
            "percent": 100 * line_hit / len(lines) if lines else 100.0,
            "uncovered": uncovered_lines,
        },
        "branch": {
            "hit": sum(point["hit"] > 0 for point in branch_points),
            "total": len(branch_points),
            "percent": (100 * sum(point["hit"] > 0 for point in branch_points)
                        / len(branch_points) if branch_points else 100.0),
            "uncovered": uncovered_branches,
        },
        "toggle": {
            "bin_hit": sum(point["hit"] > 0 for point in toggle_points),
            "bin_total": len(toggle_points),
            "bin_percent": (100 * sum(point["hit"] > 0 for point in toggle_points)
                            / len(toggle_points) if toggle_points else 100.0),
            "bits_hit": sum(toggle_bits.values()),
            "bits_total": len(toggle_bits),
            "bits_percent": (100 * sum(toggle_bits.values()) / len(toggle_bits)
                             if toggle_bits else 100.0),
            "uncovered_bins": uncovered_toggles,
            "uncovered_bits": sorted(bit for bit, hit in toggle_bits.items() if not hit),
        },
        "instrumentation": instrumentation,
    }


def summarize_build(row: dict, cache, lcov_records: dict[Path, dict]) -> dict:
    native_path = Path(row["path"])
    if not native_path.is_file():
        raise FileNotFoundError(native_path)
    build = row["build"]
    per_file: dict[Path, dict] = defaultdict(
        lambda: {"line": [], "branch": [], "toggle": []})
    for meta, count in read_points(native_path):
        source = Path(meta.get("f", "")).resolve()
        page = meta.get("page", "")
        kind, _, module = page.partition("/")
        kind = kind[2:] if kind.startswith("v_") else kind
        if kind not in {"line", "branch", "toggle"} or not module:
            continue
        if kind == "line":
            per_file[source]["line"].append(
                {"lines": counted_lines(meta), "hit": count})
        elif kind == "branch":
            per_file[source]["branch"].append({
                "line": int(meta["l"]), "arm": meta.get("o", ""), "hit": count,
                "verilog": source_line(source, int(meta["l"]), cache)})
        else:
            per_file[source]["toggle"].append({
                "line": int(meta["l"]), "transition": meta.get("o", ""), "hit": count,
                "verilog": source_line(source, int(meta["l"]), cache)})
    # LCOV may mention sources that have no native line point (top submodule).
    for source in lcov_records:
        per_file.setdefault(source, {"line": [], "branch": [], "toggle": []})

    files = {}
    excluded = []
    for source, native in sorted(per_file.items()):
        if is_wrapper(source):
            excluded.append(source.name)
            continue
        files[source.name] = summarize_file(
            source, native, lcov_records.get(source, {}), cache)

    def total(metric: str, key: str) -> int:
        return sum(row[metric][key] for row in files.values())

    line_hit, line_total = total("line", "source_hit"), total("line", "source_total")
    branch_hit, branch_total = total("branch", "hit"), total("branch", "total")
    bin_hit, bin_total = total("toggle", "bin_hit"), total("toggle", "bin_total")
    bits_hit, bits_total = total("toggle", "bits_hit"), total("toggle", "bits_total")
    return {
        "dut": build["name"],
        "build_id": build["build_id"],
        "native": str(native_path),
        "files": {name: row for name, row in sorted(files.items())},
        "excluded_wrappers": sorted(excluded),
        "line": {
            "point_hit": sum(row["line"]["point_hit"] for row in files.values()),
            "point_total": sum(row["line"]["point_total"] for row in files.values()),
            "source_hit": line_hit, "source_total": line_total,
            "percent": 100 * line_hit / line_total if line_total else 100.0,
            "uncovered": [item for row in files.values()
                          for item in row["line"]["uncovered"]],
        },
        "branch": {
            "hit": branch_hit, "total": branch_total,
            "percent": 100 * branch_hit / branch_total if branch_total else 100.0,
            "uncovered": [item for row in files.values()
                          for item in row["branch"]["uncovered"]],
        },
        "toggle": {
            "bin_hit": bin_hit, "bin_total": bin_total,
            "bin_percent": 100 * bin_hit / bin_total if bin_total else 100.0,
            "bits_hit": bits_hit, "bits_total": bits_total,
            "bits_percent": 100 * bits_hit / bits_total if bits_total else 100.0,
            "uncovered_bins": [item for row in files.values()
                               for item in row["toggle"]["uncovered_bins"]],
            "uncovered_bits": sorted({bit for row in files.values()
                                      for bit in row["toggle"]["uncovered_bits"]}),
        },
    }


def make_report(manifest_path: Path) -> dict:
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    check_manifest(manifest)
    cache: dict[Path, list[str]] = {}
    lcov_by_build: dict[str, Path] = {}
    last_build = None
    for row in manifest["artifacts"]:
        if row["kind"] == "native":
            last_build = row["build"]["build_id"]
        elif row["kind"] == "lcov" and last_build is not None:
            lcov_by_build[last_build] = Path(row["path"])
    duts = {}
    for row in manifest["artifacts"]:
        if row["kind"] == "native":
            duts[row["build"]["name"]] = summarize_build(
                row, cache, parse_lcov(lcov_by_build.get(row["build"]["build_id"],
                                                         Path("/nonexistent"))))
    return {
        "format": "instr-uncache-native-coverage-report",
        "version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "pytest_exitstatus": manifest.get("pytest_exitstatus"),
        "duts": duts,
    }


def markdown(report: dict) -> str:
    lines = ["# InstrUncache native coverage", "",
             f"Manifest: `{report['manifest']}`", "",
             "Picker wrapper `*_top.sv` files are excluded; their DA lines are",
             "DPI/port glue. Files with no line/branch points are marked N/A.", ""]
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
        lines += ["| RTL file | line | branch | toggle | hash |",
                  "|---|---|---|---|---|"]
        for name, row in data["files"].items():
            lines.append(
                f"| `{name}` | {row['line']['source_hit']}/{row['line']['source_total']} | "
                f"{row['branch']['hit']}/{row['branch']['total']} | "
                f"{row['toggle']['bin_hit']}/{row['toggle']['bin_total']} | "
                f"`{(row['rtl_sha256'] or '')[:12]}` |")
        if data["excluded_wrappers"]:
            lines += ["", "Excluded Picker wrapper(s): "
                      + ", ".join(f"`{name}`" for name in data["excluded_wrappers"])]
        lines.append("")
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
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(report), encoding="utf-8")
    if args.previous:
        old = json.loads(args.previous.read_text(encoding="utf-8"))
        for dut, data in report["duts"].items():
            before = old.get("duts", {}).get(dut)
            if before is None:
                continue
            print(f"{dut}: line {before['line']['percent']:.2f}% -> "
                  f"{data['line']['percent']:.2f}%, branch "
                  f"{before['branch']['percent']:.2f}% -> {data['branch']['percent']:.2f}%, "
                  f"toggle {before['toggle']['bin_percent']:.2f}% -> "
                  f"{data['toggle']['bin_percent']:.2f}%")
    for dut, data in report["duts"].items():
        print(f"{dut}: line {data['line']['source_hit']}/{data['line']['source_total']} "
              f"({data['line']['percent']:.2f}%), branch {data['branch']['hit']}/"
              f"{data['branch']['total']} ({data['branch']['percent']:.2f}%), "
              f"toggle {data['toggle']['bin_hit']}/{data['toggle']['bin_total']} "
              f"({data['toggle']['bin_percent']:.2f}%), bits "
              f"{data['toggle']['bits_hit']}/{data['toggle']['bits_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
