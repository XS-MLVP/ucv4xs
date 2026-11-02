"""SDK full-slot/staging controls. No additional RTL functional credit."""
import asyncio
from dataclasses import fields, replace
from types import SimpleNamespace

import pytest
from toffee import SyncDriver

from suites.frontend.ftq.ftq.driver.slots import FtqInputDriver
from suites.frontend.ftq.ftq.transaction.cycle import FtqInput
from suites.frontend.ftq.ftq.transaction.types import Consumers, Meta, Prediction
from suites.frontend.ftq.oracle import CallRet
from tests.ftq.support import allocate, resolve

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize('values', (
    dict(reset=1), dict(consumers=SimpleNamespace(train=1)),
    dict(prediction=SimpleNamespace(start_pc=0)), dict(meta=SimpleNamespace(index=0)),
    dict(resolve=(None,) * 2), dict(resolve=(None, None, object())),
    dict(callret=(None,) * 7), dict(callret=(None,) * 7 + (object(),)),
    dict(commit=(False, 0)), dict(ahead=(0, 64)), dict(commit=[0, 1]),
    dict(meta=Meta(0, fields={'unknown': 1})),
    dict(meta=Meta(0, fields={'resolveMeta_phr_phrPtr_value': 1 << 10})),
    dict(prediction=Prediction(0, s3_override=1, s3_ptr=1), meta=Meta(2)),
))
def test_bad_full_slot_is_rejected_before_a_driver_exists(values):
    with pytest.raises(ValueError):
        FtqInput(**values)


def test_lane_vectors_and_metadata_are_immutable_input_plans():
    rows = [CallRet(63, 3)] + [None] * 7
    frame = FtqInput(callret=rows, commit=(1, 63), ahead=(1, 63),
        prediction=Prediction((1 << 50) - 1, s3_override=1, s3_ptr=63, s3_flag=1),
        meta=Meta(63, flag=1, fields={'redirectMeta_ras_topRetAddr_addr': (1 << 50) - 1}))
    rows[0] = None
    assert frame.callret[0] == CallRet(63, 3)
    assert frame.prediction.s3_ptr == frame.meta.index == 63


async def test_sdk_driver_exclusively_owns_every_input_including_reset(ftq_agent):
    agent = ftq_agent
    assert isinstance(agent.input_driver, SyncDriver)
    assert len(agent.input_ports.inputs) == 433
    second = FtqInputDriver(agent.dut, agent.input_ports)
    with pytest.raises(RuntimeError, match='already have a driver'):
        async with second:
            raise AssertionError('a second complete input owner was admitted')


async def test_full_observation_bindings_cover_every_public_output(ftq_agent):
    agent = ftq_agent
    bound = set()
    for field in fields(agent.ports):
        value = getattr(agent.ports, field.name)
        for pins in value if isinstance(value, tuple) else (value,):
            bound.update(pins.names.values())
    assert agent.dut.output_names() <= bound


async def test_stage_is_preview_not_acceptance_and_task_switches_do_not_make_edges(ftq_agent):
    agent = ftq_agent
    count = agent.dut.sampled_cycles
    preview = await agent.offer(Prediction(0x80001000))
    assert preview.wen and preview.index == 0
    for _ in range(12):
        await asyncio.sleep(0)
    assert agent.dut.sampled_cycles == count
    assert not agent.input_receipt()
    await agent.step(3)
    entries = agent.input_receipt()
    assert len(entries) == 3
    assert [item.slot for item in entries] == [1, 2, 3]
    assert len({item.tick for item in entries}) == 3
    assert all(item.frame.prediction.start_pc == 0x80001000 for item in entries)
    assert agent.pointers().bpu.value == 3
    await agent.complete_offer()


async def test_matching_s3_metadata_and_override_are_one_atomic_slot(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 3, with_meta=False)
    frame = FtqInput(prediction=Prediction(0x80002000, s3_override=1, s3_ptr=1),
        meta=Meta(1, fields={'resolveMeta_phr_phrPtr_value': 17}))
    await agent.cycle(frame)
    assert agent.pointers().bpu.value == agent.pointers().pnr.value == 2
    assert agent.entry(1).start_pc == frame.prediction.start_pc
    assert agent.meta_resolve(1, 'phr_phrPtr_value') == 17
    await agent.cycle(FtqInput())
    await agent.step(2)
    assert agent.pointers().bpu.value == 2
    assert not agent.flush().s3_valid


async def test_rejected_later_lane_cannot_partly_stage_or_advance_an_earlier_lane(ftq_agent):
    agent = ftq_agent
    await agent.consumers(prefetch=1, train=1)
    before = dict((name, int(signal.U())) for name, signal in agent.input_ports.inputs.items())
    count = agent.dut.sampled_cycles
    for operation in (
        lambda: agent.resolve_lanes((resolve(0), None, object())),
        lambda: agent.callret_rows((CallRet(0, 2),) + (None,) * 6 + (object(),)),
        lambda: agent.write_meta(Meta(0, fields={'missing': 1})),
        lambda: agent.resolve_stream(((resolve(0),), (object(),))),
    ):
        with pytest.raises(ValueError):
            await operation()
        assert agent.dut.sampled_cycles == count
        assert before == {name: int(signal.U()) for name, signal in agent.input_ports.inputs.items()}
    assert not agent.input_receipt()


async def test_consumer_merge_and_complete_payload_withdrawal_do_not_leak_old_lanes(ftq_agent):
    agent = ftq_agent
    await agent.consumers(prefetch=1)
    await agent.consumers(train=1)
    await agent.callret(7, CallRet(63, 3))
    assert agent.input_driver.frame == FtqInput(consumers=Consumers(prefetch=1, train=1))
    assert not any(int(signal.U()) for name, signal in agent.input_ports.inputs.items()
                   if name.startswith('io_fromBackend_callRetCommit_'))
    await agent.step(2)


async def test_replayed_input_receipt_cannot_pass_with_equal_payload(ftq_factory, monkeypatch):
    with pytest.raises(AssertionError, match='tick mismatch'):
        async with ftq_factory() as agent:
            send = agent.input_driver.send

            async def replay(frame):
                event = await send(frame)
                return replace(event, tick=event.tick - 2)

            monkeypatch.setattr(agent.input_driver, 'send', replay)
            await agent.step(1)


async def test_real_input_mutation_cannot_be_hidden_by_the_driver_call_return(ftq_factory, monkeypatch):
    with pytest.raises(AssertionError):
        async with ftq_factory() as agent:
            send = agent.input_driver._drive_one

            async def wrong(frame):
                return await send(replace(frame, consumers=Consumers(train=1)))

            monkeypatch.setattr(agent.input_driver, '_drive_one', wrong)
            await agent.step(1)


async def test_swallowed_input_failure_is_sticky_at_normal_fixture_finish(ftq_factory, monkeypatch):
    with pytest.raises(RuntimeError, match='unreconciled'):
        async with ftq_factory() as agent:
            send = agent.input_driver.send

            async def wrong(frame):
                event = await send(frame)
                return replace(event, tick=event.tick - 2)

            monkeypatch.setattr(agent.input_driver, 'send', wrong)
            with pytest.raises(AssertionError):
                await agent.step(1)
            for operation in (agent.reset, agent.step):
                with pytest.raises(RuntimeError, match='unreconciled'):
                    await operation()


async def test_staging_during_an_active_slot_fails_without_writes(ftq_agent, monkeypatch):
    agent = ftq_agent
    entered, proceed = asyncio.Event(), asyncio.Event()
    send = agent.input_driver._drive_one

    async def blocked(frame):
        entered.set()
        await proceed.wait()
        return await send(frame)

    monkeypatch.setattr(agent.input_driver, '_drive_one', blocked)
    task = asyncio.create_task(agent.step(1))
    await entered.wait()
    try:
        with pytest.raises(RuntimeError, match='concurrent'):
            await agent.consumers(train=1)
    finally:
        proceed.set()
        await task
    assert agent.input_receipt()[-1].frame.consumers == Consumers()


async def test_cancellation_after_edge_does_not_become_a_cancelled_or_accepted_receipt(ftq_factory, monkeypatch):
    with pytest.raises(asyncio.CancelledError):
        async with ftq_factory() as agent:
            reached = asyncio.Event()

            async def block_delivery():
                reached.set()
                await asyncio.Event().wait()

            monkeypatch.setattr(agent.dut._cycle_monitors[0], 'recv', block_delivery)
            task = asyncio.create_task(agent.step(1))
            await reached.wait()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                with pytest.raises(RuntimeError, match='unreconciled'):
                    agent.input_receipt()
                raise


async def test_finish_cannot_silently_clear_a_staged_override(ftq_factory):
    with pytest.raises(AssertionError, match='explicitly release'):
        async with ftq_factory() as agent:
            await agent.offer(Prediction(0, s2_override=1, s2_ptr=0))


@pytest.mark.parametrize('bad', (True, 0, -1, '1', 1.5))
async def test_invalid_cycle_budget_leaves_all_staged_state_and_ticks_unchanged(ftq_agent, bad):
    agent = ftq_agent
    count = agent.dut.sampled_cycles
    for operation in (lambda: agent.step(bad), lambda: agent.reset(asserted=bad)):
        with pytest.raises(ValueError, match='positive integer'):
            await operation()
    assert agent.dut.sampled_cycles == count
