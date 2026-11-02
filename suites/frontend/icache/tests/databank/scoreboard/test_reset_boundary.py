"""Reset ownership/domain controls, not a full DataBank lifecycle signoff."""
import pytest
from toffee import SyncSingleCycleDriver
from suites.frontend.icache.tests.databank.scoreboard.support import running

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize('cycles', (0, -1, True, 1.5))
async def test_invalid_reset_is_rejected_before_idle_or_control_side_effects(databank_agent, monkeypatch, cycles):
    agent = databank_agent
    calls = []
    idle = agent.idle_inputs

    def observe():
        calls.append(True)
        return idle()

    monkeypatch.setattr(agent, 'idle_inputs', observe)
    tick = agent._execution.backend.tick
    with pytest.raises(ValueError, match='positive integer'):
        await agent.reset(cycles)
    assert not calls and agent._execution.backend.tick == tick


async def test_competing_sdk_source_cannot_write_the_owned_reset(databank_agent):
    agent = databank_agent
    competitor = SyncSingleCycleDriver(agent.dut.clock, agent.dut.reset,
        idle=0, name='databank.competing-reset')
    try:
        with pytest.raises((ValueError, RuntimeError), match='driver|owner|claim'):
            await competitor.send(0)
    finally:
        competitor.close()
    await agent.write(3, 15, data=7)
    assert all(entry.data == 7 for entry in await agent.check_read(3))


@pytest.mark.parametrize('cycles', (1, 4, 9))
async def test_positive_reset_keeps_its_original_edges_and_clears_the_real_macro(databank_agent, cycles):
    agent = databank_agent
    await agent.write(3, 15, data=7, code=1)
    tick = agent._execution.backend.tick
    await agent.reset(cycles)
    assert agent._execution.backend.tick - tick == 2 * (cycles + 2)
    assert all(entry.data == entry.code == 0 for entry in await agent.check_read(3))


async def test_close_releases_reset_without_reusing_a_closed_agent(dut_factory):
    async with running(dut_factory) as agent:
        execution = agent._execution
        clock, reset = agent.dut.clock, agent.dut.reset
        await agent.aclose()
        replacement = SyncSingleCycleDriver(clock, reset, idle=0, name='databank.replacement-reset')
        try:
            await replacement.send(0)
            with pytest.raises(RuntimeError, match='active agent'):
                await agent.reset()
            with pytest.raises(RuntimeError, match='restarted'):
                await agent.start(execution)
        finally:
            replacement.close()
