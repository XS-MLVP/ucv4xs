"""Shared Verilator native-coverage parsing and build-provenance helpers.

These are mechanisms used by both the pytest runtime and offline report tools:
record parsing, source relocation, provenance checks and processor selection.
Offline report assembly and ABTB-specific attribution stay in tools/.
"""
from __future__ import annotations
from suites.frontend.icache import ROOT as _SUITE_ROOT

import json
import os
import re
import shutil
from hashlib import sha256
from pathlib import Path


ROOT = _SUITE_ROOT

POINT = re.compile(r"^C '(.*)' ([0-9]+)$")


def _metadata(raw: str) -> dict[str, str]:
    return dict(field.split("\x02", 1) for field in raw.split("\x01") if "\x02" in field)


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
