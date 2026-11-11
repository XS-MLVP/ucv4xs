"""Independent-oracle audit: the model must not be a port enumeration."""

from __future__ import annotations

import pytest

from suites.frontend.ibuffer.testbenches.ibuffer.model import Beat
from suites.frontend.ibuffer.testbenches.ibuffer.model import FetchEntry
from suites.frontend.ibuffer.testbenches.ibuffer.model import reset_outputs
from suites.frontend.ibuffer.testbenches.vtype_gen.model import INIT_VTYPE


def entry(index: int) -> FetchEntry:
    return FetchEntry(inst=0x0200_0000 | (index << 8))


@pytest.mark.feature("IBUF-ENV-004")
def test_beat_placement_uses_the_write_bank_offset():
    beat = Beat(entries=(entry(0), entry(1)), decode_can_accept=0)
    for offset in range(4):
        inputs = beat.to_inputs(offset)
        assert inputs.valid == 0b11 << offset
        assert inputs.enq_enable == 0b11 << offset
        assert inputs.exception_mask == 1 << offset
        assert inputs.entries[offset].inst == entry(0).inst
        assert inputs.entries[offset + 1].inst == entry(1).inst
        # Lanes outside the beat are neutral padding.
        if offset:
            assert inputs.entries[offset - 1].inst == 0
        assert inputs.entries[35].inst == 0


@pytest.mark.feature("IBUF-ENV-004")
def test_reset_snapshot_is_empty_and_ready():
    outputs = reset_outputs()
    assert outputs.in_ready == 1 and outputs.full == 0 and outputs.empty == 1
    assert [lane.valid for lane in outputs.lanes] == [0] * 8
    assert outputs.stall_reason == (0,) * 8
    assert all(lane.vtype == INIT_VTYPE for lane in outputs.lanes)
