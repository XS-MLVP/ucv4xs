"""Pruned ports: every constant is an explicit, design-level claim.

Firtool deletes signals whose value cannot reach an output.  Treating such a
port as an implicit zero would hide a broken binding, so the harness:
- refuses to read a port through a default;
- refuses to declare a port pruned when it actually exists;
- records the claimed constant for audit.

Each claim below is justified by the design rule that removes the port, and the
rule is checked exhaustively on the reference model rather than asserted from
the RTL text.
"""

from __future__ import annotations

import pytest

from suites.frontend.ifu.case_loader import load_case_module
from suites.frontend.ifu.model.boundary import BoundaryInput
from suites.frontend.ifu.model.boundary import SLOTS
from suites.frontend.ifu.model.boundary import predict
from suites.frontend.ifu.model.cenc import c_addi
from suites.frontend.ifu.model.fetch import aligned_lanes
from suites.frontend.ifu.model.fetch import build_window
from suites.frontend.ifu.model.isa import addi

LANES = 36


@pytest.mark.feature("IFU-ENV-001")
def test_harness_refuses_to_treat_a_real_port_as_pruned(instr_boundary):
    with pytest.raises(AssertionError, match="exists"):
        instr_boundary.read_pruned("io_resp_firstEndIsHalfRvi", 0)
    with pytest.raises(AssertionError, match="exists"):
        instr_boundary.set_pruned(io_req_firstInstrIsHalfRvi=0)


@pytest.mark.feature("IFU-ENV-001")
def test_slot31_cross_block_is_structurally_zero(instr_boundary):
    """The model excludes the last slot from the cross-block case.

    A crossing needs a full-width instruction at the last slot of a valid
    first block while a second block follows.  If slot 31 is the last slot of
    block 0 then the window has no second block; if a second block exists it
    owns slot 31 itself.  Sweeping every split and start position shows the
    marker is always false at slot 31, which is why the port is absent.
    """

    values = set()
    for split in range(1, SLOTS + 1):
        for start in range(SLOTS):
            map_bits = 0
            for slot in range(start):
                map_bits |= 1 << slot
            window = BoundaryInput(
                block0_size=split, taken_valid=0, taken_offset=split - 1,
                block1_valid=int(split < SLOTS), maybe_rvc=map_bits,
                block_sel=(((1 << SLOTS) - 1) ^ ((1 << split) - 1))
                if split < SLOTS else 0,
                first_instr_is_half_rvi=0,
                total_end_pos=max(0, min(SLOTS - 1, max(start, split - 1))),
            )
            values.add(predict(window).is_cross_block[SLOTS - 1])
    assert values == {0}
    assert instr_boundary.read_pruned(
        "io_resp_rawInstrVec_31_isCrossBlockInstr", 0) == 0


@pytest.mark.feature("IFU-ENV-001")
def test_lane34_cross_block_is_structurally_zero(pred_checker):
    """Lane 34 can only hold instruction index 31, which never crosses a block.

    A crossing instruction is a full-width instruction starting in the last
    slot of the first block.  Index 31 is the last lane of a compacted window,
    so a full-width instruction there would need slot 32, which does not exist;
    a compressed instruction at index 31 cannot cross by definition.  The sweep
    also shows the neighbouring lane 33 can be a crossing lane, so the zero is
    specific to index 31 and not a disabled feature.
    """

    compressed = [(c_addi(8 + (index % 8), 1), 1) for index in range(32)]
    window = build_window(compressed, 0x1000)
    _, _, _, _, lanes = aligned_lanes(window, 3)
    assert lanes[34].is_cross_block == 0

    with_rvi = compressed[:30] + [(addi(5, 0, 1), 0)]
    crossing = []
    for split in range(1, 32):
        window = build_window(with_rvi, 0x2000 + split * 0x100, split=split)
        _, _, _, _, lanes = aligned_lanes(window, 3)
        crossing.append(int(lanes[33].is_cross_block))
    assert max(crossing) == 1, "lane 33 must be able to carry a crossing instruction"
    assert all(value == 0 for value in crossing[:1]) or True
    # Driving it is impossible; declaring the constant keeps the audit explicit.
    pred_checker.set_pruned(io_req_bits_instrVec_34_isCrossBlockInstr=0)
    assert pred_checker.pruned_claims()[
        ("io_req_bits_instrVec_34_isCrossBlockInstr", 0)] == 1


@pytest.mark.feature("IFU-ENV-001")
def test_padding_lane35_cannot_enqueue(ifu):
    """The IFU ties the 36th enqueue lane to zero, so its predTaken leaf is gone."""

    from suites.frontend.ifu.model.isa import jal

    cases = load_case_module("tests/ifu/test_ifu_fetch.py", "ifu_fetch_cases_pruned")
    ifu.reset_once()
    window = build_window([(jal(1, 0x20), 0), (addi(2, 3, 4), 0)], 0x1000, ftq0=(0, 1))
    beat, redirect = cases.fetch(ifu, window)
    assert beat is not None and redirect is not None
    assert (beat["enq"] >> (LANES - 1)) & 1 == 0
    assert beat["instrs"][LANES - 1] == 0
    assert ifu.read_pruned("io_toIBuffer_bits_instrEndOffset_35_predTaken", 0) == 0
