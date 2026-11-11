"""Source relocation contract for Verilator coverage from rebuilt DUTs."""
import pytest

from suites.frontend.bpu.tools import rtl_coverage as rtl_coverage


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
