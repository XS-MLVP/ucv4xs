"""A same-bank prediction read must backpressure tagged TAGE feedback."""

from __future__ import annotations

import asyncio

import pytest

from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.transaction.types import BpuTraining
from bpuverify.bpu.coverage.catalog import bpu_same_bank_burst_coverage_model
from bpuverify.bpu.coverage.catalog import bpu_same_bank_training_coverage_model
from bpuverify.bpu.coverage.catalog import write_bpu_same_bank_burst_coverage
from bpuverify.bpu.coverage.catalog import write_bpu_same_bank_training_coverage
from bpuverify.bpu.checker.assertions import mbtb_counter_for_position
from bpuverify.bpu.checker.assertions import revisit_from_redirect
from bpuverify.bpu.checker.assertions import tage_meta_for_position
from bpuverify.bpu.case.definitions import EARLIER_TARGET
from bpuverify.bpu.case.definitions import PC
from bpuverify.bpu.case.definitions import POSITION
from bpuverify.bpu.case.definitions import REDIRECT_PC
from bpuverify.bpu.case.scenarios import prepare_history_tage_providers
from bpuverify.bpu.case.scenarios import revisit_via_history_path
from bpuverify.common.env.paths import REPO_ROOT
from toffee import ClockCycles
from toffee import TransferState


async def _start_same_bank_prediction_loop(agent, contexts) -> int:
    """Keep S0 reading the feedback bank without training TAGE at the loop PC."""

    loop_pc = REDIRECT_PC
    assert (PC >> 1) & 3 == (loop_pc >> 1) & 3
    cold = await revisit_from_redirect(
        agent, loop_pc, contexts.anchor.meta.redirect
    )
    await agent.train(BpuTraining(
        loop_pc, POSITION, loop_pc, cold.meta.resolve,
    ))
    await agent.redirect_and_settle(
        BpuRedirect(loop_pc, cold.meta.redirect)
    )
    return loop_pc


async def _predictions_through(agent, start: int, end: int):
    predictions = []
    async with asyncio.timeout(15):
        for _ in range(1024):
            observed = await agent.prediction_monitor.recv()
            if observed.accepted_tick > end:
                break
            if observed.accepted_tick > start:
                predictions.append(observed)
        else:
            raise AssertionError("prediction monitor did not reach the held window")
    return tuple(predictions)


@pytest.mark.feature("BPU-INT-030")
async def test_same_bank_prediction_read_holds_tage_feedback(bpu_agent):
    coverage = bpu_same_bank_training_coverage_model()
    contexts = await prepare_history_tage_providers(bpu_agent)
    original = tage_meta_for_position(contexts.first, POSITION)
    assert original["hasProvider"] == 1
    assert original["providerTakenCtr_value"] == 2
    assert mbtb_counter_for_position(contexts.first, POSITION) == 1

    loop_pc = await _start_same_bank_prediction_loop(bpu_agent, contexts)
    coverage.sample({"phase": "provider_and_stream_prepared"})

    start = (await ClockCycles(bpu_agent.dut.clock, 1)).tick
    pending = bpu_agent.training_driver.send(BpuBatchTraining(
        PC, contexts.first.meta.resolve,
        (BpuBranchFeedback(
            POSITION, EARLIER_TARGET, 1, taken=1, mispredict=1,
        ),),
    ))
    held_until = (await ClockCycles(bpu_agent.dut.clock, 8)).tick
    predictions = await _predictions_through(bpu_agent, start, held_until)
    assert len(predictions) >= 6, predictions
    assert all(item.value.start_pc == loop_pc for item in predictions)
    coverage.sample({"phase": "prediction_reads_active"})
    assert pending.state is TransferState.PENDING
    assert pending.accepted_event is None
    coverage.sample({"phase": "feedback_held"})

    await bpu_agent.set_ready(prediction=False, meta=True)
    try:
        async with asyncio.timeout(15):
            accepted = await pending
        assert accepted.tick > held_until
        await bpu_agent.wait_training(committed=True)
    finally:
        await bpu_agent.set_ready(prediction=True, meta=True)
    coverage.sample({"phase": "accepted_after_release"})

    updated = await revisit_from_redirect(
        bpu_agent, PC, contexts.prepared.cold.meta.redirect
    )
    provider = tage_meta_for_position(updated, POSITION)
    assert mbtb_counter_for_position(updated, POSITION) == 2
    assert provider["hasProvider"] == 1
    assert provider["providerTableIdx"] > original["providerTableIdx"], f'{original!r} -> {provider!r}'
    assert provider["providerTakenCtr_value"] == 4
    coverage.sample({"phase": "training_effect_readback"})

    coverage.assert_coverage(100.0)
    write_bpu_same_bank_training_coverage(coverage, REPO_ROOT)


@pytest.mark.feature("BPU-INT-031")
async def test_two_history_beats_survive_same_bank_prediction_stall(bpu_agent):
    coverage = bpu_same_bank_burst_coverage_model()
    contexts = await prepare_history_tage_providers(bpu_agent)
    first_before = tage_meta_for_position(contexts.first, POSITION)
    second_before = tage_meta_for_position(contexts.second, POSITION)
    assert contexts.first.meta.resolve["phr"] != contexts.second.meta.resolve["phr"]
    assert first_before["hasProvider"] == second_before["hasProvider"] == 1
    assert first_before["providerTakenCtr_value"] == 2
    assert second_before["providerTakenCtr_value"] == 4
    coverage.sample({"phase": "two_history_cells"})

    loop_pc = await _start_same_bank_prediction_loop(bpu_agent, contexts)
    start = (await ClockCycles(bpu_agent.dut.clock, 1)).tick
    first = bpu_agent.training_driver.send(BpuBatchTraining(
        PC, contexts.first.meta.resolve,
        (BpuBranchFeedback(
            POSITION, EARLIER_TARGET, 1, taken=1, mispredict=1,
        ),),
    ))
    second = bpu_agent.training_driver.send(BpuBatchTraining(
        PC, contexts.second.meta.resolve,
        (BpuBranchFeedback(
            POSITION, EARLIER_TARGET, 1, taken=1, mispredict=1,
        ),),
    ))
    held_until = (await ClockCycles(bpu_agent.dut.clock, 8)).tick
    predictions = await _predictions_through(bpu_agent, start, held_until)
    assert len(predictions) >= 6, predictions
    assert all(item.value.start_pc == loop_pc for item in predictions)
    coverage.sample({"phase": "same_bank_stream"})
    assert first.state is second.state is TransferState.PENDING
    assert first.accepted_event is second.accepted_event is None
    coverage.sample({"phase": "both_beats_held"})

    await bpu_agent.set_ready(prediction=False, meta=True)
    try:
        async with asyncio.timeout(15):
            first_event = await first
            second_event = await second
        assert first_event.tick > held_until
        assert second_event.tick == first_event.tick + 2
        await bpu_agent.wait_training(committed=True)
    finally:
        await bpu_agent.set_ready(prediction=True, meta=True)
    coverage.sample({"phase": "adjacent_release"})

    first_after = await revisit_from_redirect(
        bpu_agent, PC, contexts.prepared.cold.meta.redirect
    )
    second_after = await revisit_via_history_path(
        bpu_agent, PC, contexts.via_pc, contexts.anchor.meta.redirect
    )
    assert first_after.meta.resolve["phr"] == contexts.first.meta.resolve["phr"]
    assert second_after.meta.resolve["phr"] == contexts.second.meta.resolve["phr"]
    first_provider = tage_meta_for_position(first_after, POSITION)
    second_provider = tage_meta_for_position(second_after, POSITION)
    assert first_provider["hasProvider"] == 1
    assert first_provider["providerTableIdx"] > first_before["providerTableIdx"], f'{first_before!r} -> {first_provider!r}'
    assert first_provider["providerTakenCtr_value"] == 4
    coverage.sample({"phase": "first_history_updated"})
    assert second_provider["hasProvider"] == 1
    assert (
        second_provider["providerTableIdx"],
        second_provider["providerWayIdx"],
        second_provider["providerTakenCtr_value"],
    ) == (
        second_before["providerTableIdx"],
        second_before["providerWayIdx"],
        5,
    )
    # Both beats carry a stale snapshot of the shared MainBTB counter. Its
    # final value is not a count of how many TAGE feedback beats retired.
    assert mbtb_counter_for_position(first_after, POSITION) == 2
    coverage.sample({"phase": "second_history_updated"})

    coverage.assert_coverage(100.0)
    write_bpu_same_bank_burst_coverage(coverage, REPO_ROOT)
