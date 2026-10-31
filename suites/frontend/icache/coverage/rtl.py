"""Merge only the RTL coverage files produced by one pytest invocation.

Verilator's old default ``verilator-coverage.dat`` files and its default
annotation threshold are not suitable for this regression. This report uses
the pytest manifest, native LCOV line counts from ``v_line`` + ``v_branch``
(including their ``S`` line spans), and separate point/branch/toggle counts.
"""

from __future__ import annotations
from suites.frontend.icache import ROOT as _SUITE_ROOT

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime
from datetime import timezone
from hashlib import sha256
from pathlib import Path


ROOT = _SUITE_ROOT


def _abtb_source_helpers():
    """ABTB's counter ownership index is BPU-only.

    ICache DUTs never reach this branch, so the import stays lazy and the
    ICache project does not need the BPU predictor packages installed.
    """
    from suites.frontend.icache.abtb.coverage.counter import source_index
    from suites.frontend.icache.abtb.coverage.counter import source_matrix

    return source_index, source_matrix

POINT = re.compile(r"^C '(.*)' ([0-9]+)$")
SCALA_REF = re.compile(
    r"(?P<file>[A-Za-z0-9_./-]+\.scala):(?P<line>[0-9]+)"
    r"|,\s*:(?P<continued_line>[0-9]+)"
)
ABTB_COUNTER = re.compile(r"\btakenCounter_([0-9]+)_([0-9]+)_([0-9]+)_value\b")


def _metadata(raw: str) -> dict[str, str]:
    return dict(field.split("\x02", 1) for field in raw.split("\x01") if "\x02" in field)


def _source_line(path: Path, line: int, cache: dict[Path, list[str]]) -> str:
    if path not in cache:
        cache[path] = path.read_text(encoding="utf-8").splitlines()
    lines = cache[path]
    return lines[line - 1].strip() if 0 < line <= len(lines) else ""


def _scala_refs(path: Path, line: int, cache: dict[Path, list[str]]) -> list[str]:
    """Include the continuation carrying a Scala source comment, if present."""

    source = _source_line(path, line, cache)
    context = source
    balance = source.count("(") - source.count(")")
    for offset in range(1, 5):
        if balance <= 0:
            break
        continuation = _source_line(path, line + offset, cache)
        if not continuation:
            break
        context += " " + continuation
        balance += continuation.count("(") - continuation.count(")")
    refs = []
    filename = None
    for match in SCALA_REF.finditer(context):
        if match["file"]:
            filename = match["file"]
        if filename is not None:
            number = match["line"] or match["continued_line"]
            refs.append(f"{filename}:{number}")
    return list(dict.fromkeys(refs))


def _abtb_counter_gap(
    path: Path,
    line: int,
    refs: list[str],
    cache: dict[Path, list[str]],
) -> dict[str, object] | None:
    """Locate the generated counter cell behind one uncovered ABTB arm.

    Chisel emits the selector before the counter reference. Looking forward
    within that short block avoids guessing geometry from a nearby reset or
    from a neighboring way's preceding assignment.
    """

    if any(ref.endswith("SaturateCounter.scala:41") for ref in refs):
        role = "increment"
    elif any(ref.endswith("AheadBtb.scala:241") for ref in refs):
        role = "decrease_selection"
    else:
        return None
    source = _source_line(path, line, cache)
    if re.search(r"\b_needIncrease_T(?:_[0-9]+)?\b", source) is None:
        return None
    for offset in range(6):
        match = ABTB_COUNTER.search(_source_line(path, line + offset, cache))
        if match is not None:
            bank, set_index, way = (int(value) for value in match.groups())
            return {
                "role": role,
                "bank": bank,
                "set": set_index,
                "way": way,
            }
    return None


def _abtb_counter_matrix(points: list[dict[str, object]]) -> dict[str, object]:
    cells: dict[tuple[int, int, int], dict[str, int]] = defaultdict(
        lambda: {"increment": 0, "decrease_selection": 0}
    )
    unmapped = 0
    for point in points:
        gap = point.get("counter_gap")
        if not isinstance(gap, dict):
            unmapped += 1
            continue
        key = (gap["bank"], gap["set"], gap["way"])
        cells[key][gap["role"]] += 1
    rows = [
        {
            "bank": bank,
            "set": set_index,
            "way": way,
            "missing_increment": counts["increment"],
            "missing_decrease_selection": counts["decrease_selection"],
        }
        for (bank, set_index, way), counts in sorted(cells.items())
    ]
    by_bank = [
        {
            "bank": bank,
            "missing_increment": sum(
                row["missing_increment"] for row in rows if row["bank"] == bank
            ),
            "missing_decrease_selection": sum(
                row["missing_decrease_selection"]
                for row in rows if row["bank"] == bank
            ),
        }
        for bank in sorted({row["bank"] for row in rows})
    ]
    gap_patterns = {
        "increment_and_decrease": sum(
            bool(row["missing_increment"] and row["missing_decrease_selection"])
            for row in rows
        ),
        "increment_only": sum(
            bool(row["missing_increment"] and not row["missing_decrease_selection"])
            for row in rows
        ),
        "decrease_only": sum(
            bool(row["missing_decrease_selection"] and not row["missing_increment"])
            for row in rows
        ),
    }
    return {
        "uncovered_line_points": len(points),
        "mapped_line_points": len(points) - unmapped,
        "unmapped_line_points": unmapped,
        "by_bank": by_bank,
        "gap_patterns": gap_patterns,
        "cells": rows,
    }


def _source_path(recorded: str, dut: str) -> Path:
    """Resolve a generated source after its DUT package has been relocated."""

    original = Path(recorded)
    # Resolve only the active package/closure directory, never a basename match.
    for directory in (ROOT / 'rtl' / dut, ROOT / 'dut' / dut):
        candidate = directory / original.name
        if original.parent.resolve() == directory.resolve() and candidate.is_file():
            return candidate
    if original.parent.name == dut:
        installed = ROOT / "dut" / dut / original.name
        if installed.is_file():
            return installed
    # A named diagnostic export can later be installed under its canonical
    # DUT name. Relocate only the exact export directory recorded by that
    # build, never an arbitrary source with a coincidentally matching basename.
    provenance = _build_provenance(dut)
    if provenance and str(original.parent) == provenance["export_directory"]:
        installed = ROOT / "dut" / dut / original.name
        if installed.is_file() and original.name in {
            f"{dut.capitalize()}Dut.v", f"{dut.capitalize()}Dut_top.sv",
        }:
            return installed
    if original.is_file():
        return original
    raise FileNotFoundError(f"coverage source for {dut} is missing: {recorded}")


def _build_provenance(dut: str) -> dict[str, object] | None:
    """Distinguish the model's compiler from the coverage merging tool."""

    directory = ROOT / "dut" / dut
    path = directory / "build-provenance.json"
    if not path.is_file():
        return None  # Historical packages have no verifiable compiler record.
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("format") != "bpu-dut-build-provenance"
            or data.get("version") != 1 or data.get("dut") != dut):
        raise ValueError(f"invalid DUT build provenance: {path}")
    for name, field in (
        (f"{dut.capitalize()}Dut.v", "primary_rtl_sha256"),
        ("signals.json", "signals_sha256"),
    ):
        source = directory / name
        if not source.is_file() or sha256(source.read_bytes()).hexdigest() != data.get(field):
            raise ValueError(f"DUT build provenance does not match {source}")
    if not isinstance(data.get("verilator_version"), str) or not isinstance(data.get("export_directory"), str):
        raise ValueError(f"incomplete DUT build provenance: {path}")
    return data


def _coverage_tool(dut: str) -> str:
    """Use the build's recorded processor instead of an unrelated PATH tool."""

    override = os.environ.get("BPU_VERILATOR_COVERAGE")
    provenance = _build_provenance(dut)
    recorded = provenance.get("coverage_processor") if provenance else None
    selected = override or recorded or "verilator_coverage"
    executable = shutil.which(str(selected))
    if executable is None:
        raise FileNotFoundError(f"coverage processor is unavailable: {selected}")
    return executable


def _source_type(path: Path, dut: str) -> str:
    """Separate picker accessors from Chisel RTL, regardless of HDL suffix."""

    dut_dir = ROOT / "dut" / dut
    if path.parent == dut_dir and path.stem == f"{dut.capitalize()}Dut_top":
        return "picker_wrapper"
    if path.suffix in {".v", ".sv"} and (
        path.parent == dut_dir or path.is_relative_to(ROOT / "rtl" / dut)
    ):
        return "rtl_verilog"
    return "other"


def _covered_lines(fields: dict[str, str]) -> set[int]:
    """Expand the same anchor and statement spans as Verilator's annotateCalc."""

    lines = {int(fields["l"])}
    for span in fields.get("S", "").split(","):
        if not span:
            continue
        match = re.fullmatch(r"([1-9][0-9]*)(?:-([1-9][0-9]*))?", span)
        if match is None:
            raise ValueError(f"invalid Verilator line span: {span!r}")
        first = int(match[1])
        last = int(match[2] or first)
        if last < first:
            raise ValueError(f"reversed Verilator line span: {span!r}")
        lines.update(range(first, last + 1))
    return lines


def _native_line_counts(
    records: list[str], dut: str, info_output: Path | None
) -> dict[tuple[Path, int], int]:
    """Keep native line merging semantics, but never blend toggles into lines.

    Verilator's unfiltered --write-info also folds toggle counters into DA.
    Use only line/branch records and relocate SF entries to installed sources.
    The persisted LCOV artifact contains RTL only, not picker accessors.
    """

    counts = {}
    rtl_info = ["TN:verilator_coverage\n"]
    with tempfile.TemporaryDirectory(prefix="bpu-native-lines-") as directory:
        data = Path(directory) / "line-branch.dat"
        info = Path(directory) / "line-branch.info"
        data.write_text("# SystemC::Coverage-3\n" + "\n".join(records) + "\n", encoding="utf-8")
        subprocess.run(
            [_coverage_tool(dut), "--write-info", str(info), str(data)],
            check=True, capture_output=True, text=True,
        )
        source = None
        for record in info.read_text(encoding="utf-8").splitlines():
            if record.startswith("SF:"):
                source = _source_path(record[3:], dut)
                if _source_type(source, dut) == "rtl_verilog":
                    rtl_info.append(f"SF:{source}\n")
            elif record.startswith("DA:"):
                if source is None:
                    raise ValueError("LCOV DA record precedes its source file")
                line, count = map(int, record[3:].split(","))
                counts[(source, line)] = count
                if _source_type(source, dut) == "rtl_verilog":
                    rtl_info.append(record + "\n")
            elif record == "end_of_record":
                if source is not None and _source_type(source, dut) == "rtl_verilog":
                    rtl_info.append(record + "\n")
                source = None
    if info_output is not None:
        info_output.parent.mkdir(parents=True, exist_ok=True)
        info_output.write_text("".join(rtl_info), encoding="utf-8")
    return counts


def _summarize(
    merged: Path, dut: str, *, info_output: Path | None = None
) -> dict[str, object]:
    points = defaultdict(lambda: {"total": 0, "hit": 0})
    source_groups = defaultdict(lambda: {"total": 0, "hit": 0})
    anchor_lines: dict[tuple[str, str, str, int], bool] = {}
    module_lines: dict[tuple[str, str], set[tuple[Path, int]]] = defaultdict(set)
    line_records = []
    line_cache: dict[Path, list[str]] = {}
    source_paths: dict[str, Path] = {}
    counter_indices: dict[Path, dict] = {}
    uncovered_branches = []
    uncovered_line_points = []
    uncovered_toggles = []
    for record in merged.read_text(encoding="utf-8").splitlines():
        match = POINT.match(record)
        if match is None:
            continue
        fields = _metadata(match.group(1))
        page = fields.get("page", "")
        kind, _, module = page.partition("/")
        if kind not in {"v_line", "v_branch", "v_toggle"}:
            continue
        hit = int(match.group(2)) > 0
        counter = points[(kind, module)]
        counter["total"] += 1
        counter["hit"] += hit
        recorded = fields.get("f", "")
        if recorded not in source_paths:
            source_paths[recorded] = _source_path(recorded, dut)
        source_path = source_paths[recorded]
        source_type = _source_type(source_path, dut)
        source_counter = source_groups[(source_type, kind)]
        source_counter["total"] += 1
        source_counter["hit"] += hit
        if kind in {"v_line", "v_branch"}:
            line_records.append(record)
            module_lines[(source_type, module)].update(
                (source_path, line) for line in _covered_lines(fields)
            )
        if kind == "v_branch" and source_type == "rtl_verilog" and not hit:
            line_number = int(fields["l"])
            source = _source_line(source_path, line_number, line_cache)
            uncovered_branches.append({
                "module": module,
                "file": str(source_path.relative_to(ROOT)),
                "line": line_number,
                "arm": fields.get("o", ""),
                "verilog": source,
                "scala_refs": _scala_refs(source_path, line_number, line_cache),
            })
        if kind == "v_line" and source_type == "rtl_verilog" and not hit:
            line_number = int(fields["l"])
            source = _source_line(source_path, line_number, line_cache)
            refs = _scala_refs(source_path, line_number, line_cache)
            point = {
                "module": module,
                "file": str(source_path.relative_to(ROOT)),
                "line": line_number,
                "arm": fields.get("o", ""),
                "verilog": source,
                "scala_refs": refs,
            }
            if dut in ("abtb", "bpu") and module == "AheadBtb":
                gap = _abtb_counter_gap(
                    source_path, line_number, refs, line_cache
                )
                if gap is not None:
                    point["counter_gap"] = gap
            uncovered_line_points.append(point)
        if kind == "v_toggle" and source_type == "rtl_verilog" and not hit:
            line_number = int(fields["l"])
            uncovered_toggles.append({
                "module": module,
                "file": str(source_path.relative_to(ROOT)),
                "line": line_number,
                "signal": fields.get("o", ""),
                "verilog": _source_line(source_path, line_number, line_cache),
                "scala_refs": _scala_refs(source_path, line_number, line_cache),
            })
        if kind == "v_line":
            key = (source_type, module, str(source_path), int(fields["l"]))
            anchor_lines[key] = anchor_lines.get(key, False) or hit

    native_counts = _native_line_counts(line_records, dut, info_output)
    modules = []
    uncovered_source_lines = []
    for (source_type, module), lines in sorted(module_lines.items()):
        missed = []
        for path, line in sorted(lines):
            if native_counts[(path, line)] > 0:
                continue
            gap = {
                "file": str(path.relative_to(ROOT)),
                "line": line,
                "verilog": _source_line(path, line, line_cache),
                "scala_refs": _scala_refs(path, line, line_cache),
            }
            if dut in ("abtb", "bpu") and module == "AheadBtb":
                source_index, _ = _abtb_source_helpers()
                if path not in counter_indices:
                    counter_indices[path] = source_index(line_cache[path])
                owner = counter_indices[path]["lines"].get(line)
                if owner is not None:
                    gap["counter_gap"] = dict(owner)
            missed.append(gap)
            if source_type == "rtl_verilog":
                uncovered_source_lines.append({"module": module, **gap})
        modules.append({
            "name": module,
            "source_type": source_type,
            "line_points": points[("v_line", module)],
            "branch_points": points[("v_branch", module)],
            "source_lines": {"total": len(lines), "hit": len(lines) - len(missed)},
            "uncovered": missed,
        })
    grouped_points = defaultdict(dict)
    for (source_type, kind), counter in sorted(source_groups.items()):
        grouped_points[source_type][kind] = counter
    anchors = defaultdict(lambda: {"total": 0, "hit": 0})
    for (source_type, _, _, _), hit in anchor_lines.items():
        anchors[source_type]["total"] += 1
        anchors[source_type]["hit"] += hit
    for source_type, counter in anchors.items():
        grouped_points[source_type]["anchor_lines"] = counter
    source_lines = defaultdict(lambda: {"total": 0, "hit": 0})
    for (path, _), count in native_counts.items():
        counter = source_lines[_source_type(path, dut)]
        counter["total"] += 1
        counter["hit"] += count > 0
    for source_type, counter in source_lines.items():
        grouped_points[source_type]["source_lines"] = counter
    rtl = grouped_points["rtl_verilog"]
    result = {
        "line_points": rtl.get("v_line", {"total": 0, "hit": 0}),
        "source_lines": rtl.get("source_lines", {"total": 0, "hit": 0}),
        "by_source": dict(grouped_points),
        "modules": modules,
        "uncovered_rtl_source_lines": uncovered_source_lines,
        "uncovered_rtl_branches": uncovered_branches,
        "uncovered_rtl_line_points": uncovered_line_points,
        "uncovered_rtl_toggles": uncovered_toggles,
    }
    if dut in ("abtb", "bpu"):
        counter_points = uncovered_line_points if dut == "abtb" else [
            point for point in uncovered_line_points if point["module"] == "AheadBtb"]
        result["abtb_counter_matrix"] = _abtb_counter_matrix(counter_points)
        counter_gaps = [gap for gap in uncovered_source_lines if gap["module"] == "AheadBtb"]
        if counter_indices:
            if len(counter_indices) != 1:
                raise ValueError("ambiguous ABTB source ownership across files")
            _, source_matrix = _abtb_source_helpers()
            result["abtb_counter_source_matrix"] = source_matrix(
                counter_gaps, next(iter(counter_indices.values())))
    return result


def build_report(manifest_path: Path, output: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get('format') == 'bpu-managed-native-manifest':
        return build_managed_report(manifest, output)
    if manifest.get("format") != "bpu-rtl-coverage-manifest":
        raise ValueError("expected a BPU pytest RTL coverage manifest")
    grouped: dict[str, list[Path]] = defaultdict(list)
    for entry in manifest["files"]:
        path = (ROOT / entry).resolve()
        if not path.is_relative_to(ROOT / "results") or not path.is_file():
            raise ValueError(f"invalid or missing coverage file: {entry}")
        grouped[path.parent.name].append(path)
    result = {
        "format": "bpu-rtl-line-coverage",
        "version": 3,
        "line_coverage": {
            "metric": "verilator_native_lcov",
            "point_kinds": ["v_line", "v_branch"],
            "line_mapping": "l anchor plus expanded S spans",
            "hit_threshold": 1,
            "exclude": ["picker_wrapper", "v_toggle"],
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pytest_exitstatus": manifest["pytest_exitstatus"],
        "dut": {},
    }
    processor_versions = {}
    with tempfile.TemporaryDirectory(prefix="bpu-rtl-coverage-") as directory:
        for dut, paths in sorted(grouped.items()):
            processor = _coverage_tool(dut)
            if processor not in processor_versions:
                processor_versions[processor] = subprocess.check_output(
                    [processor, "--version"], text=True
                ).strip()
            merged = Path(directory) / f"{dut}.dat"
            subprocess.run(
                [processor, "--write", str(merged), *(str(path) for path in paths)],
                check=True,
                capture_output=True,
                text=True,
            )
            info_output = output.parent / "rtl-lines" / f"{dut}.info"
            summary = _summarize(merged, dut, info_output=info_output)
            summary["build_provenance"] = _build_provenance(dut)
            summary["coverage_processor"] = processor
            summary["coverage_processor_version"] = processor_versions[processor]
            summary["lcov_file"] = str(info_output.resolve())
            summary["test_files"] = manifest.get("native_retention", {}).get(
                "input_files_by_dut", {}).get(dut, len(paths))
            summary["aggregate_files"] = len(paths)
            result["dut"][dut] = summary
    versions = sorted(set(processor_versions.values()))
    result["line_coverage"]["tool_versions"] = versions
    result["line_coverage"]["tool_version"] = versions[0] if len(versions) == 1 else "mixed (see per-DUT processors)"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def build_managed_report(manifest, output):
    """Attribute final native tables; never re-merge toffee's worker inputs."""
    result = dict(format='bpu-rtl-line-coverage', version=3,
        line_coverage=dict(metric='verilator_native_lcov', point_kinds=['v_line','v_branch'],
            line_mapping='l anchor plus expanded S spans', hit_threshold=1,
            exclude=['picker_wrapper','v_toggle']),
        generated_at=datetime.now(timezone.utc).isoformat(),
        pytest_exitstatus=manifest['pytest_exitstatus'], dut={})
    versions = {}
    for row in manifest['native']:
        dut, path = row['dut'], Path(row['path']).resolve()
        if (dut in result['dut'] or not path.is_relative_to(ROOT/'results')
                or not path.is_file() or path.stat().st_size != row['size']
                or sha256(path.read_bytes()).hexdigest() != row['sha256']):
            raise ValueError('invalid managed final native artifact')
        processor = _coverage_tool(dut)
        if processor not in versions:
            versions[processor] = subprocess.check_output([processor,'--version'],text=True).strip()
        info = Path(output).parent/'rtl-lines'/f'{dut}.info'
        summary = _summarize(path, dut, info_output=info)
        summary.update(build_provenance=_build_provenance(dut), coverage_processor=processor,
            coverage_processor_version=versions[processor], lcov_file=str(info.resolve()),
            test_files=row['input_files'], aggregate_files=1, merge_owner='toffee')
        result['dut'][dut] = summary
    tool_versions = sorted(set(versions.values()))
    result['line_coverage'].update(tool_versions=tool_versions,
        tool_version=tool_versions[0] if len(tool_versions)==1 else 'mixed (see per-DUT processors)')
    Path(output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "results/rtl-coverage-manifest.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/rtl-line-coverage.json")
    args = parser.parse_args()
    report = build_report(args.manifest, args.output)
    for dut, data in report["dut"].items():
        points = data["by_source"].get("rtl_verilog", {}).get("v_line", {"hit": 0, "total": 0})
        lines = data["source_lines"]
        wrapper = data["by_source"].get("picker_wrapper", {}).get("v_line", {"hit": 0, "total": 0})
        percent = 100 * lines["hit"] / lines["total"] if lines["total"] else 0
        print(f"{dut}: RTL source lines {lines['hit']}/{lines['total']} ({percent:.2f}%), "
              f"v_line points {points['hit']}/{points['total']}, "
              f"picker wrapper v_line points {wrapper['hit']}/{wrapper['total']}, "
              f"{data['test_files']} test coverage file(s)")


if __name__ == "__main__":
    main()
