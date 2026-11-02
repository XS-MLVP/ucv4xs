"""Real native observation controls, not extra hardware functional credit."""
import pytest
import asyncio
from dataclasses import replace

from suites.frontend.ftq.oracle import CallRet
from suites.frontend.ftq.commit_queue.transaction.types import EMPTY

pytestmark = pytest.mark.selftest


async def test_multicycle_wait_keeps_every_intermediate_commit_head(commit_queue_agent):
    agent = commit_queue_agent
    start = len(agent.training_monitor.history)
    await agent.drive(tuple(CallRet(40 + lane, 1 + lane % 3) for lane in range(4)) + (None,) * 4)
    await agent.step(1)
    await agent.release()
    await agent.step(6)
    observed = tuple(agent.training_monitor.history)[start:]
    assert tuple(item.ptr for item in observed) == (40, 41, 42, 43)
    assert agent.training() is None


async def test_missing_commit_output_is_rejected_during_an_uninterrupted_wait(commit_queue_factory, monkeypatch):
    with pytest.raises(AssertionError, match='commit_queue'):
        async with commit_queue_factory() as agent:
            monkeypatch.setattr(agent.training_monitor, 'sample_fn', lambda _: None)
            await agent.drive((CallRet(9, 2),) + (None,) * 7)
            await agent.step(4)


@pytest.mark.parametrize('mutation', ('missing', 'pointer', 'action'))
async def test_corrupt_output_leaves_a_sticky_unreconciled_slot(commit_queue_factory, monkeypatch, mutation):
    with pytest.raises(AssertionError, match='commit_queue'):
        async with commit_queue_factory() as agent:
            original = agent.training_monitor.sample_fn

            def corrupt(dut):
                value = original(dut)
                if value is None:
                    return None
                if mutation == 'missing':
                    return None
                return replace(value, **({'ptr': value.ptr ^ 1} if mutation == 'pointer' else {'ras': 1}))

            monkeypatch.setattr(agent.training_monitor, 'sample_fn', corrupt)
            try:
                await agent.submit((CallRet(9, 2),) + (None,) * 7)
            except AssertionError:
                monkeypatch.setattr(agent.training_monitor, 'sample_fn', original)
                with pytest.raises(RuntimeError, match='unreconciled'):
                    await agent.finish()
                with pytest.raises(RuntimeError, match='unreconciled'):
                    agent.receipt()
                raise


async def test_unexpected_idle_output_fails_even_without_an_explicit_training_read(commit_queue_factory, monkeypatch):
    with pytest.raises(AssertionError, match='commit_queue'):
        async with commit_queue_factory() as agent:
            monkeypatch.setattr(agent.training_monitor, 'sample_fn', lambda _: CallRet(2, 1))
            await agent.step(1)


async def test_late_output_is_checked_by_finish_before_monitors_close(commit_queue_factory, monkeypatch):
    with pytest.raises(AssertionError, match='commit_queue'):
        async with commit_queue_factory() as agent:
            original = agent.training_monitor.sample_fn
            captures = 0

            def late(dut):
                nonlocal captures
                captures += 1
                return CallRet(4, 3) if captures == 2 else original(dut)

            monkeypatch.setattr(agent.training_monitor, 'sample_fn', late)
            await agent.finish()


async def test_actual_input_must_equal_the_planned_input_before_acceptance(commit_queue_factory, monkeypatch):
    with pytest.raises(AssertionError, match='commit_queue'):
        async with commit_queue_factory() as agent:
            capture = agent.before_monitor.capture
            monkeypatch.setattr(agent.before_monitor, 'capture',
                                lambda event: replace(capture(event), rows=EMPTY))
            await agent.submit((CallRet(9, 2),) + (None,) * 7)


async def test_replayed_phase_tick_cannot_be_associated_by_matching_payload(commit_queue_factory, monkeypatch):
    with pytest.raises(AssertionError, match='stale/missing'):
        async with commit_queue_factory() as agent:
            recv = agent.training_monitor.recv

            async def replay():
                observation = await recv()
                return replace(observation, event=replace(observation.event, tick=observation.event.tick - 2))

            monkeypatch.setattr(agent.training_monitor, 'recv', replay)
            await agent.submit((CallRet(9, 2),) + (None,) * 7)


async def test_closed_monitor_cannot_be_replaced_by_live_training_reads(commit_queue_factory):
    from toffee import MonitorClosedError
    with pytest.raises(MonitorClosedError):
        async with commit_queue_factory() as agent:
            await agent.training_monitor.aclose()
            await agent.step(1)


async def test_cancellation_after_the_real_edge_cannot_produce_an_empty_receipt(commit_queue_factory, monkeypatch):
    with pytest.raises(asyncio.CancelledError):
        async with commit_queue_factory() as agent:
            reached = asyncio.Event()

            async def block_receipt():
                reached.set()  # Driver has already returned the actual edge.
                await asyncio.Event().wait()

            monkeypatch.setattr(agent.before_monitor, 'recv', block_receipt)
            work = asyncio.create_task(agent.submit((CallRet(9, 2),) + (None,) * 7))
            await reached.wait()
            work.cancel()
            try:
                await work
            except asyncio.CancelledError:
                with pytest.raises(RuntimeError, match='unreconciled'):
                    await agent.finish()
                with pytest.raises(RuntimeError, match='unreconciled'):
                    agent.receipt()
                raise


async def test_task_switches_do_not_invent_valid_only_commit_edges(commit_queue_agent):
    agent = commit_queue_agent
    await agent.submit((CallRet(6, 2),) + (None,) * 7)
    before = agent.receipt()
    for _ in range(12):
        await asyncio.sleep(0)
    assert agent.receipt() == before
    assert agent.training() == CallRet(6, 2)
    await agent.finish()
    assert len(agent.receipt()['accepted']) == 1


async def test_same_payload_in_different_lanes_and_cycles_has_distinct_input_uids(commit_queue_agent):
    agent = commit_queue_agent
    await agent.submit((CallRet(5, 2),) * 3 + (None,) * 5)
    await agent.drive((CallRet(5, 2),) + (None,) * 7)
    await agent.step(3)
    await agent.release()
    receipt = await agent.finish()
    assert len(receipt['offered']) == len(receipt['accepted']) == 6
    assert len(set(receipt['accepted'])) == 6
    assert not receipt['pending']
    assert tuple(terminal.action.uid for terminal in receipt['terminals']) == receipt['accepted']
    assert {terminal.status for terminal in receipt['terminals']} == {'completed'}


async def test_async_reset_cancels_exactly_the_old_epoch_not_a_fresh_equal_payload(commit_queue_agent):
    agent = commit_queue_agent
    await agent.submit((CallRet(12, 2),) * 3 + (None,) * 5)
    old = set(agent.receipt()['accepted'])
    await agent.reset()
    await agent.submit((CallRet(12, 2),) + (None,) * 7)
    receipt = await agent.finish()
    cancelled = {terminal.action.uid for terminal in receipt['terminals'] if terminal.status == 'reset-cancelled'}
    completed = {terminal.action.uid for terminal in receipt['terminals'] if terminal.status == 'completed'}
    assert cancelled == old and len(completed) == 1 and not (cancelled & completed)
    assert {uid[0] for uid in cancelled}.isdisjoint(uid[0] for uid in completed)


async def test_capacity_rejection_is_explicit_not_a_dropped_completion(commit_queue_agent):
    agent = commit_queue_agent
    for _ in range(10):
        await agent.submit((CallRet(3, 2),) * 8)
    receipt = await agent.finish()
    rejected = [terminal for terminal in receipt['terminals'] if terminal.status == 'capacity-rejected']
    assert len(receipt['offered']) == 80 and len(receipt['accepted']) == 64
    assert len(rejected) == 16 and not receipt['pending']


async def test_none_action_is_filtered_without_a_response_obligation(commit_queue_agent):
    agent = commit_queue_agent
    await agent.submit((CallRet(3, 0), CallRet(3, 1)) + (None,) * 6)
    receipt = await agent.finish()
    assert len(receipt['offered']) == 2 and len(receipt['accepted']) == 1
    assert {terminal.status for terminal in receipt['terminals']} == {'filtered-none', 'completed'}


@pytest.mark.parametrize('bad', (True, 0, -1, 1.5, '2'))
async def test_invalid_cycle_budget_is_rejected_before_any_input_or_oracle_change(commit_queue_agent, bad):
    agent = commit_queue_agent
    before = agent.receipt()
    with pytest.raises(ValueError, match='positive integer'):
        await agent.step(bad)
    assert agent.receipt() == before


async def test_finish_cannot_silently_clear_a_still_armed_producer(commit_queue_factory):
    with pytest.raises(AssertionError, match='producer remains armed'):
        async with commit_queue_factory() as agent:
            await agent.drive((CallRet(1, 2),) + (None,) * 7)
            await agent.finish()


async def test_too_small_finish_budget_does_not_claim_unfinished_work_as_completed(commit_queue_factory):
    with pytest.raises(AssertionError, match='budget exhausted'):
        async with commit_queue_factory() as agent:
            await agent.submit((CallRet(1, 2),) * 3 + (None,) * 5)
            await agent.finish(cycles=2)


async def test_last_preedge_consumer_is_checked_before_completing_its_uid(commit_queue_factory, monkeypatch):
    with pytest.raises(AssertionError, match='commit_queue'):
        async with commit_queue_factory() as agent:
            await agent.submit((CallRet(1, 2),) + (None,) * 7)
            monkeypatch.setattr(agent.before_monitor, 'sample_fn', lambda _: None)
            await agent.finish()


async def test_sdk_ownership_rejects_a_second_driver_even_with_the_same_name(commit_queue_agent):
    from suites.frontend.ftq.commit_queue.driver import CommitInputDriver
    agent = commit_queue_agent
    second = CommitInputDriver(agent.dut.dut.clock, agent.ports)
    with pytest.raises(RuntimeError, match='already have a driver'):
        async with second:
            raise AssertionError('a second physical input driver was admitted')
    await agent.submit((CallRet(7, 2),) + (None,) * 7)


async def test_sdk_driver_cannot_claim_a_native_output(commit_queue_agent):
    from toffee import SyncSingleCycleDriver, Bundle
    agent = commit_queue_agent
    second = SyncSingleCycleDriver(agent.dut.dut.clock,
        Bundle(output=agent.dut.dut.io_bpuTrain_valid), idle={'output': 0}, name='bad-output-driver')
    with pytest.raises(ValueError, match='cannot drive DUT outputs'):
        async with second:
            raise AssertionError('a DUT output was admitted as a driver input')


async def test_swallowed_public_checker_failure_cannot_become_a_clean_finish(commit_queue_factory):
    with pytest.raises(RuntimeError, match='prior comparison failure'):
        async with commit_queue_factory() as agent:
            with pytest.raises(AssertionError):
                agent.checker.check(CallRet(9, 2), CallRet(10, 2))
            await agent.finish()
