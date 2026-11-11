"""Illegal-stimulus guards: protocol-illegal input never reaches the DUT."""

from __future__ import annotations

import pytest

from suites.frontend.ibuffer.testbenches.ibuffer.model import Beat
from suites.frontend.ibuffer.testbenches.ibuffer.model import ExceptionEntry
from suites.frontend.ibuffer.testbenches.ibuffer.model import FetchEntry
from suites.frontend.ibuffer.testbenches.ibuffer.model import IBufferModel
from suites.frontend.ibuffer.testbenches.ibuffer.model import Inputs
from suites.frontend.ibuffer.testbenches.ibuffer.model import StimulusError
from suites.frontend.ibuffer.testbenches.ibuffer.model import ZERO_ENTRY


def entry(index: int) -> FetchEntry:
    return FetchEntry(inst=0x0200_0000 | (index << 8))


@pytest.mark.feature("IBUF-ENV-003")
def test_enq_enable_must_be_a_subset_of_valid():
    with pytest.raises(StimulusError, match="subset"):
        Inputs(valid=0b1, enq_enable=0b10)


@pytest.mark.feature("IBUF-ENV-003")
def test_ifu_padding_lanes_cannot_be_valid():
    with pytest.raises(StimulusError, match="32"):
        Inputs(valid=1 << 32)
    with pytest.raises(StimulusError, match="32"):
        Inputs(valid=(1 << 31) | (1 << 32))


@pytest.mark.feature("IBUF-ENV-003")
def test_lane_runs_must_be_contiguous():
    with pytest.raises(StimulusError, match="contiguous"):
        Inputs(valid=(1 << 0) | (1 << 2))
    with pytest.raises(StimulusError, match="contiguous"):
        Inputs(valid=0b1111, enq_enable=(1 << 0) | (1 << 2))


@pytest.mark.feature("IBUF-ENV-003")
def test_quiet_beat_cannot_carry_fetch_payload():
    with pytest.raises(StimulusError, match="quiet"):
        Inputs(in_valid=0, valid=1)
    with pytest.raises(StimulusError, match="quiet"):
        Inputs(in_valid=0, exception=ExceptionEntry(exc_type=1))
    Inputs(in_valid=0)  # the legal quiet control must be accepted


@pytest.mark.feature("IBUF-ENV-003")
def test_exception_type_must_be_a_frontend_encoding():
    with pytest.raises(StimulusError, match="exception type"):
        ExceptionEntry(exc_type=6)
    ExceptionEntry(exc_type=5)


@pytest.mark.feature("IBUF-ENV-003")
def test_beat_must_fit_the_ifu_window_and_its_own_entries():
    with pytest.raises(StimulusError, match="enq_count"):
        Beat(entries=(entry(0),), enq_count=2)
    with pytest.raises(StimulusError, match="32"):
        Beat(entries=tuple(entry(index) for index in range(33)))
    with pytest.raises(StimulusError, match="32"):
        Beat(entries=tuple(entry(index) for index in range(32))).to_inputs(1)
    # A 32-instruction beat is only legal at write-bank offset zero.
    placed = Beat(entries=tuple(entry(index) for index in range(32))).to_inputs(0)
    assert placed.enq_enable == (1 << 32) - 1


@pytest.mark.feature("IBUF-ENV-003")
def test_model_rejects_a_beat_that_is_not_write_bank_aligned():
    model = IBufferModel()
    lanes = [ZERO_ENTRY] * 36
    lanes[1] = entry(1)
    inputs = Inputs(in_valid=1, valid=1 << 1, enq_enable=1 << 1,
                    entries=tuple(lanes))
    with pytest.raises(StimulusError, match="enqPtr"):
        model.events(inputs)


@pytest.mark.feature("IBUF-ENV-003")
def test_model_rejects_an_unannounced_queue_overflow():
    model = IBufferModel()
    model.enq_ptr = 47
    model.ifu_aligned = [((47 & ~3) + lane) % 48 for lane in range(36)]
    lanes = [ZERO_ENTRY] * 36
    lanes[3] = entry(3)
    lanes[4] = entry(4)
    # Hold decode off so the two instructions cannot be absorbed by dequeue.
    inputs = Inputs(in_valid=1,
                    valid=(1 << 3) | (1 << 4),
                    enq_enable=(1 << 3) | (1 << 4),
                    entries=tuple(lanes), prev_instr_count=0,
                    resuming_vtype=1)
    with pytest.raises(StimulusError, match="overflow"):
        model.events(inputs)


@pytest.mark.feature("IBUF-ENV-003")
async def test_agent_rejects_an_enqueue_that_the_previous_cycle_did_not_announce(
        ibuffer_agent):
    agent = ibuffer_agent
    beat = Beat(entries=(entry(0),), decode_can_accept=0)
    with pytest.raises(StimulusError, match="announced"):
        await agent.cycle(beat.to_inputs(0), announce=0)
    # The same beat is legal through play(), which announces it correctly.
    cycles = await agent.play([beat])
    assert cycles[0].events.fire == 1
