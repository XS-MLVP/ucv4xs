"""Stimulus legality: the fixture rejects windows the real producer cannot emit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from suites.frontend.ifu.model.cenc import c_addi
from suites.frontend.ifu.model.fetch import build_window
from suites.frontend.ifu.model.isa import addi
from suites.frontend.ifu.model.isa import beq

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.feature("IFU-ENV-004")
def test_signal_schema_confirms_the_halfword_address_unit():
    """GuardedPc ports carry bits [50:1]; the low address bit is implicit."""

    schema = json.loads((ROOT / "dut" / "ifu" / "signals.json").read_text())
    bits = schema["io"]["fromICache"]["req"]["bits"]
    start = bits["info"]["0"]["startVAddr_addr"]
    out = schema["io"]["toFtq_wbRedirect"]["bits"]
    pc_out = out["pc"]
    target = out["target"]
    assert start["High"] == 49 and start["Low"] == 0  # 50 wires = GuardedPc[50:1]
    assert pc_out["High"] == 49  # 50-bit VAddrBits field on this baseline
    assert target["High"] == 50  # 51-bit GuardedPc field (bit 0 implicit)


@pytest.mark.feature("IFU-ENV-004")
def test_misaligned_base_pc_is_rejected():
    with pytest.raises(ValueError, match="2-byte aligned"):
        build_window([(addi(1, 2, 3), 0)], 0x1001)


@pytest.mark.feature("IFU-ENV-004")
def test_compressed_flag_must_match_the_encoding():
    with pytest.raises(ValueError, match="not compressed"):
        build_window([(addi(1, 2, 3), 1)], 0x1000)
    with pytest.raises(ValueError, match="is compressed"):
        build_window([(c_addi(10, 1), 0)], 0x1000)


@pytest.mark.feature("IFU-ENV-004")
def test_window_capacity_is_enforced_unless_truncation_is_requested():
    over = [(c_addi(8 + (index % 8), 1), 1) for index in range(33)]
    with pytest.raises(ValueError, match="exceeds 32"):
        build_window(over, 0x1000)
    # Truncation is the legitimate way to model a window cut inside an RVI.
    window = build_window(over[:31] + [(addi(1, 2, 3), 0)], 0x1000, truncate=1)
    assert window.instructions[-1].truncated == 1


@pytest.mark.feature("IFU-ENV-004")
def test_carry_word_must_be_a_full_width_instruction():
    with pytest.raises(ValueError, match="low bits 11"):
        build_window([(c_addi(10, 1), 1)], 0x1000, carry_word=c_addi(5, 2))


@pytest.mark.feature("IFU-ENV-004")
def test_carry_in_consumes_a_slot():
    program = [(c_addi(8 + (index % 8), 1), 1) for index in range(32)]
    with pytest.raises(ValueError, match="slot 0"):
        build_window(program, 0x1000, carry_word=addi(1, 2, 3))


@pytest.mark.feature("IFU-ENV-004")
def test_exception_and_memory_type_ranges_are_checked():
    program = [(beq(5, 6, 8), 0)]
    with pytest.raises(ValueError, match="exception code"):
        build_window(program, 0x1000, exc0=6)
    with pytest.raises(ValueError, match="two bits"):
        build_window(program, 0x1000, pbmt0=4)


@pytest.mark.feature("IFU-ENV-004")
def test_split_and_prediction_fields_are_checked():
    program = [(addi(1, 2, 3), 0)]
    with pytest.raises(ValueError, match="invalid split"):
        build_window(program, 0x1000, split=3)
    with pytest.raises(ValueError, match="taken0"):
        build_window(program, 0x1000, taken0=2)
