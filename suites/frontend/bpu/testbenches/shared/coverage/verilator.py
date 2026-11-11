"""Verilator record parsing and build-pinned processor selection, without DUT models."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil

from suites.frontend.bpu import ROOT

POINT = re.compile(r"^C '(.*)' ([0-9]+)$")


def _metadata(raw: str) -> dict[str, str]:
    return dict(field.split("\x02", 1) for field in raw.split("\x01") if "\x02" in field)


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


def build_provenance(dut: str, *, root: Path = ROOT) -> dict[str, object] | None:
    """Distinguish the model's compiler from the coverage merging tool."""

    directory = root / "dut" / dut
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


def coverage_tool(dut: str, *, provenance=None) -> str:
    """Use the build's recorded processor instead of an unrelated PATH tool."""

    override = os.environ.get("BPU_VERILATOR_COVERAGE")
    provenance = build_provenance(dut) if provenance is None else provenance(dut)
    recorded = provenance.get("coverage_processor") if provenance else None
    selected = override or recorded or "verilator_coverage"
    executable = shutil.which(str(selected))
    if executable is None:
        raise FileNotFoundError(f"coverage processor is unavailable: {selected}")
    return executable
