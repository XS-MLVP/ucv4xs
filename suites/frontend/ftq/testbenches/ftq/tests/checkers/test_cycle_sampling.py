"""Continuous multi-channel sampling controls, not hardware functional credit."""
import pytest
import asyncio
from dataclasses import dataclass, replace

from suites.frontend.ftq.testbenches.resolve_queue.tests.support import report
from suites.frontend.ftq.testbenches.ftq.tests.support import allocate

pytestmark = pytest.mark.selftest


async def test_resolve_wait_keeps_intermediate_heads_not_just_the_last_edge(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(index) for index in (10, 11, 12)])
    start = len(agent.training_monitor.history)
    await agent.ready(True)
    await agent.step(3)
    intermediate = tuple(agent.training_monitor.history)[start:]
    assert tuple(value.index for value in intermediate) == (11, 12)


async def test_ftq_multicycle_wait_keeps_both_prefetch_and_fetch_channels(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 3, with_meta=False)
    starts = [len(monitor.history) for monitor in (agent.prefetch_monitor, agent.fetch_monitor)]
    await agent.consumers(prefetch=1, mainpipe=1)
    await agent.step(5)
    for monitor, start in zip((agent.prefetch_monitor, agent.fetch_monitor), starts):
        values = tuple(monitor.history)[start:]
        assert tuple(value.index for value in values if value.valid) == (1, 2)


async def test_topdown_history_is_a_snapshot_not_a_mutable_reasons_mapping(ftq_agent):
    agent = ftq_agent
    await agent.step(1)
    value = agent.topdown_monitor.history[-1]
    with pytest.raises(TypeError):
        value.reasons[2] = not value.reasons[2]


async def test_resolve_snapshot_distinguishes_visible_and_consumed_heads(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(index) for index in (10, 11, 12)])
    await agent.ready(True)
    await agent.step(3)
    phases = tuple(agent.dut.cycle_history)[-3:]
    before = [dict(cycle.before.value.observations)['resolve_queue.training'] for cycle in phases]
    after = [dict(cycle.after.value.observations)['resolve_queue.training'] for cycle in phases]
    assert [head.index for head in before] == [10, 11, 12]
    assert [None if head is None else head.index for head in after] == [11, 12, None]
    assert all(cycle.before.event.tick + 1 == cycle.after.event.tick for cycle in phases)


async def test_all_ftq_channels_share_one_phase_and_cannot_overwrite_each_other(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 3, with_meta=False)
    await agent.consumers(prefetch=1, mainpipe=1)
    await agent.step(3)
    phases = tuple(agent.dut.cycle_history)[-3:]
    for index, cycle in enumerate(phases):
        before, after = dict(cycle.before.value.observations), dict(cycle.after.value.observations)
        expected = {'ftq.training', 'ftq.commit', 'ftq.redirect', 'ftq.prefetch', 'ftq.fetch',
                    'ftq.flush', 'ftq.topdown', 'ftq.backend_write', 'ftq.owners', 'ftq.pointers'}
        assert set(before) == set(after) == expected
        assert before['ftq.prefetch'].index == before['ftq.fetch'].index == index
        assert before['ftq.owners'].pf[0] == before['ftq.owners'].fetch[0]
        assert before['ftq.owners'].pf[0].value == index
        assert before['ftq.prefetch'].valid and before['ftq.fetch'].valid
        assert after['ftq.prefetch'].index == after['ftq.fetch'].index == index + 1


async def test_large_wait_preserves_all_edges_without_overflow_or_unbounded_queues(resolve_queue_agent):
    agent = resolve_queue_agent
    start = agent.dut.sampled_cycles
    await agent.step(150)
    assert agent.dut.sampled_cycles == start + 150
    samples = tuple(agent.dut.cycle_history)[-150:]
    ticks = [cycle.after.event.tick for cycle in samples]
    assert all(right == left + 2 for left, right in zip(ticks, ticks[1:]))


async def test_task_switches_do_not_create_unsolicited_ready_fire_edges(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(10)])
    await agent.ready(True)
    count = agent.dut.sampled_cycles
    for _ in range(12):
        await asyncio.sleep(0)
    assert agent.dut.sampled_cycles == count
    assert agent.training().index == 10
    await agent.step(1)
    assert agent.training() is None


@pytest.mark.parametrize('which', (0, 1))
async def test_closed_phase_monitor_cannot_fall_back_to_live_pin_reads(resolve_queue_factory, which):
    with pytest.raises(RuntimeError, match='closed or not active'):
        async with resolve_queue_factory() as agent:
            await agent.dut._cycle_monitors[which].aclose()
            agent.training()


async def test_removed_channel_leaves_a_sticky_sampling_failure(ftq_factory):
    with pytest.raises(RuntimeError, match='disappeared or was replaced'):
        async with ftq_factory() as agent:
            monitor = agent.dut._monitors.pop()
            try:
                await agent.step(1)
            except RuntimeError:
                agent.dut._monitors.append(monitor)
                with pytest.raises(RuntimeError, match='unreconciled'):
                    agent.dut.check_sampling()
                raise


async def test_replayed_tick_cannot_be_hidden_by_an_identical_idle_payload(resolve_queue_factory, monkeypatch):
    with pytest.raises(AssertionError, match='stale/missing phase'):
        async with resolve_queue_factory() as agent:
            monitor = agent.dut._cycle_monitors[1]
            recv = monitor.recv

            async def replay():
                observation = await recv()
                return replace(observation, event=replace(observation.event, tick=observation.event.tick - 2))

            monkeypatch.setattr(monitor, 'recv', replay)
            await agent.step(1)


async def test_cancellation_after_edge_but_before_delivery_cannot_pass_sampling_audit(resolve_queue_factory, monkeypatch):
    with pytest.raises(asyncio.CancelledError):
        async with resolve_queue_factory() as agent:
            reached = asyncio.Event()

            async def block_delivery():
                reached.set()
                await asyncio.Event().wait()

            monkeypatch.setattr(agent.dut._cycle_monitors[0], 'recv', block_delivery)
            work = asyncio.create_task(agent.step(1))
            await reached.wait()
            work.cancel()
            try:
                await work
            except asyncio.CancelledError:
                with pytest.raises(RuntimeError, match='unreconciled'):
                    agent.dut.check_sampling()
                raise


@pytest.mark.parametrize('bad', (True, 0, -1, 1.5, '2'))
async def test_invalid_wait_has_no_clock_or_observation_side_effect(resolve_queue_agent, bad):
    agent = resolve_queue_agent
    count = agent.dut.sampled_cycles
    with pytest.raises(ValueError, match='positive integer'):
        await agent.step(bad)
    assert agent.dut.sampled_cycles == count


def test_decoder_cannot_smuggle_a_mutable_dataclass_into_a_snapshot():
    from suites.frontend.ftq.testbenches.shared.env.monitors.cycle import freeze

    @dataclass
    class Mutable:
        value: int

    with pytest.raises(TypeError, match='mutable dataclass'):
        freeze(Mutable(1))
