"""All13 registered event outputs belong to the continuous checking path."""
from dataclasses import replace

import pytest

from suites.frontend.ifu.ifu.types import FetchRequest, Frame
from suites.frontend.ifu.model.cenc import c_addi
from suites.frontend.ifu.model.fetch import build_window

pytestmark = [pytest.mark.selftest, pytest.mark.feature('IFU-ENV-004')]


@pytest.mark.parametrize('phase', ['before', 'after'])
@pytest.mark.parametrize('index', range(13))
async def test_each_performance_output_is_compared_in_both_phases(ifu_agent_factory, monkeypatch, phase, index):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='performance'):
        async with agent.running():
            await agent.reset()
            monitor = getattr(agent, '_' + phase)
            capture = monitor.capture

            def wrong(event):
                sample = capture(event)
                values = list(sample.performance)
                values[index] = 3  # Valid6-bit schema, impossible Boolean event count.
                return replace(sample, performance=values)

            monkeypatch.setattr(monitor, 'capture', wrong)
            await agent.fetch(FetchRequest(build_window([(c_addi(9, 1), 1)], 0x4000)))
    assert agent._failed


async def test_a_one_cycle_finish_cannot_hide_the_still_registered_event_tail(ifu_agent_factory):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='unsettled performance event tail'):
        async with agent.running():
            await agent.reset()
            item = FetchRequest(build_window([(c_addi(9, 1), 1)], 0x4000))
            await agent.cycle(Frame(request=item))
            for _ in range(4):
                checked = await agent.cycle()
                if checked.beat_uid is not None:
                    break
            assert checked.beat_uid is not None
            await agent.finish(max_cycles=1)
    assert agent._failed


async def test_short_reset_preserves_known_event_history_and_allows_an_explicit_cancel(ifu_agent):
    item = FetchRequest(build_window([(c_addi(9, 1), 1)], 0x4000))
    await ifu_agent.cycle(Frame(request=item, ibuffer_ready=0))
    await ifu_agent.idle(3, frame=Frame(ibuffer_ready=0))
    assert ifu_agent.outstanding
    await ifu_agent.reset(1, reason='single-edge reset of a held fetch')
    assert not ifu_agent.outstanding
    await ifu_agent.fetch(item)


@pytest.mark.parametrize('operation', ['cancel', 'reset'])
async def test_explicit_carry_cancellation_keeps_original_identity_and_reason(ifu_agent, operation):
    from suites.frontend.ifu.model.isa import addi
    item = FetchRequest(build_window([(c_addi(9, 1), 1)] * 31 + [(addi(5, 0, 1), 0)],
                                     0x4000, truncate=1))
    result = await ifu_agent.fetch(item)
    half = ifu_agent.carry
    assert half is not None and half.uid == result.uid
    if operation == 'cancel':
        await ifu_agent.cancel_pending('scenario ends before the next half')
    else:
        await ifu_agent.reset(reason='scenario ends before the next half')
    cancellation = ifu_agent.carry_cancellations[-1]
    assert cancellation.half == half and cancellation.reason == 'scenario ends before the next half'
    assert cancellation.operation == operation and ifu_agent.carry is None
