"""Source relocation contract for Verilator coverage from rebuilt DUTs."""

from __future__ import annotations

import json
from hashlib import sha256
import re
import subprocess

import pytest

from suites.frontend.bpu.coverage import rtl as rtl_coverage


def test_relocated_generated_source_uses_installed_dut(tmp_path, monkeypatch):
    monkeypatch.setattr(rtl_coverage, "ROOT", tmp_path)
    source = tmp_path / "dut" / "uras" / "UrasDut.v"
    source.parent.mkdir(parents=True)
    source.write_text("module MicroRas;\n  else if (s2_hasPop) begin\n", encoding="utf-8")
    stale = tmp_path / "staging" / "uras" / "UrasDut.v"
    merged = tmp_path / "merged.dat"
    metadata = f"\x01f\x02{stale}\x01l\x022\x01page\x02v_line/MicroRas"
    merged.write_text(f"C '{metadata}' 0\n", encoding="utf-8")

    summary = rtl_coverage._summarize(merged, "uras")

    assert summary["modules"][0]["uncovered"] == [{
        "file": "dut/uras/UrasDut.v",
        "line": 2,
        "verilog": "else if (s2_hasPop) begin",
        "scala_refs": [],
    }]
    assert summary["uncovered_rtl_line_points"] == [{
        "module": "MicroRas",
        "file": "dut/uras/UrasDut.v",
        "line": 2,
        "arm": "",
        "verilog": "else if (s2_hasPop) begin",
        "scala_refs": [],
    }]


def test_zero_hit_arm_is_reported_even_when_its_source_line_is_hit(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(rtl_coverage, "ROOT", tmp_path)
    source = tmp_path / "dut" / "abtb" / "AbtbDut.v"
    source.parent.mkdir(parents=True)
    source.write_text("module AheadBtb;\n  else if (increase) begin\n", encoding="utf-8")
    merged = tmp_path / "merged.dat"
    base = f"\x01f\x02{source}\x01l\x022\x01page\x02v_line/AheadBtb\x01o\x02"
    merged.write_text(
        f"C '{base}if' 9\nC '{base}else' 0\n", encoding="utf-8"
    )

    summary = rtl_coverage._summarize(merged, "abtb")

    assert summary["modules"][0]["uncovered"] == []
    assert summary["by_source"]["rtl_verilog"]["v_line"] == {
        "total": 2, "hit": 1
    }
    assert summary["uncovered_rtl_line_points"] == [{
        "module": "AheadBtb",
        "file": "dut/abtb/AbtbDut.v",
        "line": 2,
        "arm": "else",
        "verilog": "else if (increase) begin",
        "scala_refs": [],
    }]


def test_abtb_counter_gaps_map_to_physical_cell_and_role(tmp_path, monkeypatch):
    monkeypatch.setattr(rtl_coverage, "ROOT", tmp_path)
    source = tmp_path / "dut" / "abtb" / "AbtbDut.v"
    source.parent.mkdir(parents=True)
    source.write_text(
        "module AheadBtb;\n"
        "  if (_needIncrease_T_1 && taken) begin // /src/AheadBtb.scala:241\n"
        "    if (|takenCounter_1_36_2_value) begin\n"
        "      takenCounter_1_36_2_value <= takenCounter_1_36_2_value - 1;\n"
        "  else if (~(_needIncrease_T_1 && taken) // /src/SaturateCounter.scala:41\n"
        "      | (&takenCounter_1_36_2_value)) begin\n",
        encoding="utf-8",
    )
    merged = tmp_path / "merged.dat"
    records = []
    for line, arm in ((2, "elsif"), (5, "else")):
        metadata = (
            f"\x01f\x02{source}\x01l\x02{line}"
            f"\x01page\x02v_line/AheadBtb\x01o\x02{arm}"
        )
        records.append(f"C '{metadata}' 0")
    merged.write_text("\n".join(records) + "\n", encoding="utf-8")

    summary = rtl_coverage._summarize(merged, "abtb")

    assert [point["counter_gap"] for point in summary["uncovered_rtl_line_points"]] == [
        {"role": "decrease_selection", "bank": 1, "set": 36, "way": 2},
        {"role": "increment", "bank": 1, "set": 36, "way": 2},
    ]
    assert summary["abtb_counter_matrix"] == {
        "uncovered_line_points": 2,
        "mapped_line_points": 2,
        "unmapped_line_points": 0,
        "by_bank": [{
            "bank": 1,
            "missing_increment": 1,
            "missing_decrease_selection": 1,
        }],
        "gap_patterns": {
            "increment_and_decrease": 1,
            "increment_only": 0,
            "decrease_only": 0,
        },
        "cells": [{
            "bank": 1,
            "set": 36,
            "way": 2,
            "missing_increment": 1,
            "missing_decrease_selection": 1,
        }],
    }


def test_multiline_condition_resolves_scala_comment_on_continuation(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(rtl_coverage, "ROOT", tmp_path)
    source = tmp_path / "dut" / "abtb" / "AbtbDut.v"
    source.parent.mkdir(parents=True)
    source.write_text(
        "module AheadBtb;\n"
        "  if (write_valid &&\n"
        "      (&set_idx)) // /src/AheadBtb.scala:51:61\n",
        encoding="utf-8",
    )
    merged = tmp_path / "merged.dat"
    metadata = (
        f"\x01f\x02{source}\x01l\x022\x01page\x02v_branch/AheadBtb"
        "\x01o\x02if"
    )
    merged.write_text(f"C '{metadata}' 0\n", encoding="utf-8")

    summary = rtl_coverage._summarize(merged, "abtb")

    assert summary["uncovered_rtl_branches"][0]["scala_refs"] == [
        "/src/AheadBtb.scala:51"
    ]


def test_zero_hit_rtl_toggle_reports_signal_but_not_wrapper_toggle(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(rtl_coverage, "ROOT", tmp_path)
    source = tmp_path / "dut" / "sc" / "ScDut.v"
    source.parent.mkdir(parents=True)
    source.write_text(
        "module Sc;\n  input [49:0] perf_target; // /src/Sc.scala:54\n",
        encoding="utf-8",
    )
    wrapper = tmp_path / "dut" / "sc" / "ScDut_top.sv"
    wrapper.write_text("module ScDut_top;\n  input perf_target;\n", encoding="utf-8")
    merged = tmp_path / "merged.dat"
    rtl_metadata = (
        f"\x01f\x02{source}\x01l\x022\x01page\x02v_toggle/Sc"
        "\x01o\x02perf_target[32]"
    )
    wrapper_metadata = (
        f"\x01f\x02{wrapper}\x01l\x022\x01page\x02v_toggle/ScDut_top"
        "\x01o\x02perf_target[32]"
    )
    merged.write_text(
        f"C '{rtl_metadata}' 0\nC '{wrapper_metadata}' 0\n",
        encoding="utf-8",
    )

    summary = rtl_coverage._summarize(merged, "sc")

    assert summary["uncovered_rtl_toggles"] == [{
        "module": "Sc",
        "file": "dut/sc/ScDut.v",
        "line": 2,
        "signal": "perf_target[32]",
        "verilog": "input [49:0] perf_target; // /src/Sc.scala:54",
        "scala_refs": ["/src/Sc.scala:54"],
    }]


def test_generated_sv_is_rtl_and_picker_top_sv_is_wrapper(tmp_path, monkeypatch):
    monkeypatch.setattr(rtl_coverage, "ROOT", tmp_path)
    generated = tmp_path / "rtl" / "tage" / "WriteBuffer.sv"
    generated.parent.mkdir(parents=True)
    generated.write_text("module WriteBuffer;\n  if (pending) begin\n", encoding="utf-8")
    wrapper = tmp_path / "dut" / "tage" / "TageDut_top.sv"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("module TageDut_top;\n  if (ready) begin\n", encoding="utf-8")
    merged = tmp_path / "merged.dat"
    records = []
    for source, kind, hits in (
        (generated, "v_line", 0),
        (generated, "v_branch", 0),
        (generated, "v_toggle", 0),
        (wrapper, "v_line", 1),
        (wrapper, "v_branch", 1),
        (wrapper, "v_toggle", 0),
    ):
        metadata = (
            f"\x01f\x02{source}\x01l\x022"
            f"\x01page\x02{kind}/{source.stem}"
        )
        records.append(f"C '{metadata}' {hits}")
    merged.write_text("\n".join(records) + "\n", encoding="utf-8")

    summary = rtl_coverage._summarize(merged, "tage")

    for kind in ("v_line", "v_branch", "v_toggle"):
        assert summary["by_source"]["rtl_verilog"][kind] == {
            "total": 1, "hit": 0
        }
    assert summary["by_source"]["picker_wrapper"]["v_line"] == {
        "total": 1, "hit": 1
    }
    assert summary["line_points"] == {"total": 1, "hit": 0}
    assert summary["source_lines"] == {"total": 1, "hit": 0}
    assert summary["uncovered_rtl_line_points"][0]["file"] == (
        "rtl/tage/WriteBuffer.sv"
    )
    assert summary["uncovered_rtl_branches"][0]["file"] == (
        "rtl/tage/WriteBuffer.sv"
    )
    assert [point["file"] for point in summary["uncovered_rtl_toggles"]] == [
        "rtl/tage/WriteBuffer.sv"
    ]


def test_missing_unrelated_source_is_not_silently_remapped(tmp_path, monkeypatch):
    monkeypatch.setattr(rtl_coverage, "ROOT", tmp_path)
    source = tmp_path / "staging" / "different_dut" / "UrasDut.v"

    with pytest.raises(FileNotFoundError, match="coverage source for uras is missing"):
        rtl_coverage._source_path(str(source), "uras")


def _provenance(directory, dut, export):
    source = directory / f"{dut.capitalize()}Dut.v"
    signals = directory / "signals.json"
    signals.write_text("{}", encoding="utf-8")
    data = {
        "format": "bpu-dut-build-provenance", "version": 1, "dut": dut,
        "export_directory": str(export), "verilator_version": "Verilator 5.052",
        "primary_rtl_sha256": sha256(source.read_bytes()).hexdigest(),
        "signals_sha256": sha256(signals.read_bytes()).hexdigest(),
    }
    (directory / "build-provenance.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def test_named_export_relocates_only_with_matching_build_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(rtl_coverage, "ROOT", tmp_path)
    directory = tmp_path / "dut/tage"
    directory.mkdir(parents=True)
    source = directory / "TageDut.v"
    source.write_text("module Tage;", encoding="utf-8")
    export = tmp_path / "removed/tage-v5052"
    data = _provenance(directory, "tage", export)
    assert rtl_coverage._build_provenance("tage") == data
    assert rtl_coverage._source_path(str(export / source.name), "tage") == source
    with pytest.raises(FileNotFoundError, match="coverage source"):
        rtl_coverage._source_path(str(export.with_name("unrelated") / source.name), "tage")


@pytest.mark.parametrize("filename", ["TageDut.v", "signals.json"])
def test_modified_export_rejects_stale_build_provenance(tmp_path, monkeypatch, filename):
    monkeypatch.setattr(rtl_coverage, "ROOT", tmp_path)
    directory = tmp_path / "dut/tage"
    directory.mkdir(parents=True)
    (directory / "TageDut.v").write_text("module Tage;", encoding="utf-8")
    _provenance(directory, "tage", tmp_path / "removed/tage-v5052")
    (directory / filename).write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="provenance does not match"):
        rtl_coverage._build_provenance("tage")


def test_legacy_package_does_not_claim_coverage_processor_is_its_compiler(tmp_path, monkeypatch):
    monkeypatch.setattr(rtl_coverage, "ROOT", tmp_path)
    assert rtl_coverage._build_provenance("tage") is None


def test_recorded_processor_is_used_instead_of_an_unrelated_path_tool(tmp_path, monkeypatch):
    processor = tmp_path / "verilator_coverage"
    processor.write_text("test executable", encoding="utf-8")
    processor.chmod(0o755)
    monkeypatch.delenv("BPU_VERILATOR_COVERAGE", raising=False)
    monkeypatch.setattr(rtl_coverage, "_build_provenance", lambda dut: {
        "coverage_processor": str(processor),
    })
    assert rtl_coverage._coverage_tool("tage") == str(processor)


def test_missing_recorded_processor_is_not_silently_replaced(tmp_path, monkeypatch):
    monkeypatch.delenv("BPU_VERILATOR_COVERAGE", raising=False)
    monkeypatch.setattr(rtl_coverage, "_build_provenance", lambda dut: {
        "coverage_processor": str(tmp_path / "missing/verilator_coverage"),
    })
    with pytest.raises(FileNotFoundError, match="processor is unavailable"):
        rtl_coverage._coverage_tool("tage")


@pytest.mark.parametrize("suffix", [".v", ".sv"])
def test_picker_wrapper_is_excluded_regardless_of_hdl_suffix(tmp_path, monkeypatch, suffix):
    monkeypatch.setattr(rtl_coverage, "ROOT", tmp_path)

    assert rtl_coverage._source_type(
        tmp_path / "dut" / "tage" / f"TageDut_top{suffix}", "tage"
    ) == "picker_wrapper"
    assert rtl_coverage._source_type(
        tmp_path / "rtl" / "tage" / f"TageTable{suffix}", "tage"
    ) == "rtl_verilog"


def test_native_lines_include_branch_spans_but_not_toggles(tmp_path, monkeypatch):
    monkeypatch.setattr(rtl_coverage, "ROOT", tmp_path)
    source = tmp_path / "rtl" / "tage" / "WriteBuffer.sv"
    source.parent.mkdir(parents=True)
    source.write_text(
        "module WriteBuffer;\n"
        "  always @(posedge clock) begin\n"
        "    state <= next_state;\n"
        "    if (pending)\n"
        "      entry <= old_entry; // /src/WriteBuffer.scala:173\n"
        "    else entry <= new_entry;\n"
        "  wire unused;\n",
        encoding="utf-8",
    )
    merged = tmp_path / "merged.dat"
    records = []
    for kind, line, arm, span, count in (
        ("v_line", 2, "block", "2-3", 9),
        ("v_branch", 4, "if", "4-5", 0),
        ("v_branch", 4, "else", "6", 5),
        ("v_toggle", 7, "unused", "", 0),
    ):
        meta = (
            f"\x01f\x02{source}\x01l\x02{line}"
            f"\x01page\x02{kind}/WriteBuffer\x01o\x02{arm}\x01S\x02{span}"
        )
        records.append(f"C '{meta}' {count}")
    merged.write_text("\n".join(records) + "\n", encoding="utf-8")
    info = tmp_path / "rtl-lines" / "tage.info"

    summary = rtl_coverage._summarize(merged, "tage", info_output=info)

    assert summary["line_points"] == {"total": 1, "hit": 1}
    assert summary["by_source"]["rtl_verilog"]["anchor_lines"] == {"total": 1, "hit": 1}
    # Native 5.052 includes the shared condition anchor when the else arm
    # executes; 5.026 only uses that arm's S span. Both remain native results,
    # not counts massaged to satisfy a version-independent golden number.
    version = subprocess.check_output([rtl_coverage._coverage_tool("tage"), "--version"], text=True)
    match = re.search(r"Verilator ([0-9]+)\.([0-9]+)", version)
    assert match is not None, version
    shared_anchor = tuple(map(int, match.groups())) >= (5, 52)
    hit = 4 if shared_anchor else 3
    gaps = [5] if shared_anchor else [4, 5]
    assert summary["source_lines"] == {"total": 5, "hit": hit}
    assert summary["modules"][0]["source_lines"] == {"total": 5, "hit": hit}
    assert [gap["line"] for gap in summary["uncovered_rtl_source_lines"]] == gaps
    assert summary["uncovered_rtl_source_lines"][-1]["scala_refs"] == [
        "/src/WriteBuffer.scala:173"
    ]
    assert "DA:6,5" in info.read_text()
    assert "DA:7," not in info.read_text()


def test_report_persists_relocated_rtl_only_lcov(tmp_path, monkeypatch):
    monkeypatch.setattr(rtl_coverage, "ROOT", tmp_path)
    source = tmp_path / "dut" / "tage" / "TageDut.v"
    source.parent.mkdir(parents=True)
    source.write_text("module Tage;\n  state <= next_state;\n", encoding="utf-8")
    wrapper = source.with_name("TageDut_top.v")
    wrapper.write_text("module TageDut_top;\n  getter();\n", encoding="utf-8")
    result = tmp_path / "results" / "tage" / "test.dat"
    result.parent.mkdir(parents=True)
    stale = tmp_path / "removed-staging" / "tage"
    result.write_text(
        f"C '\x01f\x02{stale / source.name}\x01l\x022\x01page\x02v_line/Tage\x01S\x022' 4\n"
        f"C '\x01f\x02{stale / wrapper.name}\x01l\x022\x01page\x02v_line/TageDut_top' 0\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "results" / "manifest.json"
    manifest.write_text(json.dumps({
        "format": "bpu-rtl-coverage-manifest", "pytest_exitstatus": 0,
        "files": ["results/tage/test.dat"],
    }), encoding="utf-8")

    report = rtl_coverage.build_report(manifest, tmp_path / "results" / "report.json")

    assert report["version"] == 3
    assert report["line_coverage"]["point_kinds"] == ["v_line", "v_branch"]
    assert report["dut"]["tage"]["source_lines"] == {"total": 1, "hit": 1}
    assert report["dut"]["tage"]["line_points"] == {"total": 1, "hit": 1}
    info = (tmp_path / "results" / "rtl-lines" / "tage.info").read_text()
    assert f"SF:{source}" in info
    assert "removed-staging" not in info
    assert "TageDut_top" not in info


def test_span_expansion_keeps_anchor_and_disjoint_ranges():
    assert rtl_coverage._covered_lines({"l": "2", "S": "4-6,9,11-12"}) == {
        2, 4, 5, 6, 9, 11, 12
    }


def test_scala_refs_expand_abbreviated_lines_without_treating_columns_as_lines(tmp_path):
    source = tmp_path / "RasStack.sv"
    source.write_text(
        "commitStack_1_ctr <= updated; // /src/PrunedAddr.scala:78:10, "
        "/src/RasStack.scala:68:12, :346:51, :365:{44,85}, :346:51\n",
        encoding="utf-8",
    )

    assert rtl_coverage._scala_refs(source, 1, {}) == [
        "/src/PrunedAddr.scala:78", "/src/RasStack.scala:68",
        "/src/RasStack.scala:346", "/src/RasStack.scala:365",
    ]


@pytest.mark.parametrize("span", ["0", "-1", "4-2", "1-x", "3-4-5"])
def test_invalid_span_is_not_silently_ignored(span):
    with pytest.raises(ValueError, match="Verilator line span"):
        rtl_coverage._covered_lines({"l": "2", "S": span})
