"""Real owner-adapter exercises, not new predictor functionality or IO credit."""
from dataclasses import FrozenInstanceError

import pytest
from toffee import TransferState

from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuBatchTraining
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuBranchFeedback

pytestmark = pytest.mark.selftest
PC = 0x40000800


async def test_public_feedback_handle_uses_real_admission_then_separate_effect_drain(bpu_agent):
    await bpu_agent.reset(PC)
    meta = await bpu_agent.next_meta()
    await bpu_agent.set_ready(prediction=False, meta=True)
    handle = bpu_agent.submit_training_batch(BpuBatchTraining(
        PC, meta.resolve, (BpuBranchFeedback(4, PC + 0x100, 2),)))
    assert handle.state is TransferState.PENDING and handle.accepted_event is None
    accepted = await handle
    assert handle.accepted_event is not None
    assert accepted.tick == handle.accepted_event.tick
    # Admission did not claim SRAM visibility. Explicitly pay that obligation.
    await bpu_agent.wait_training(committed=True)


async def test_public_prediction_window_copies_real_stream_accepts(bpu_agent):
    await bpu_agent.reset(PC)
    start = await bpu_agent.wait_cycles(1)
    end = await bpu_agent.wait_cycles(8)
    frames = await bpu_agent.prediction_window(start, end)
    assert frames
    assert all(start < frame.accepted_tick <= end for frame in frames)
    assert all(left.accepted_tick < right.accepted_tick for left, right in zip(frames, frames[1:]))
    with pytest.raises(FrozenInstanceError):
        frames[0].accepted_tick = 0
