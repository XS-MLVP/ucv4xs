"""Persistent level sources must share the SDK's real signal ownership."""
import pytest
from toffee import SyncSingleCycleDriver
from suites.frontend.icache.drivers.level import LevelDriver
from suites.frontend.icache.ports.bindings import PortBinding

pytestmark = pytest.mark.selftest

IDLE = dict(valid=0, setIdx=(0,) * 4, waymask=0)


@pytest.mark.parametrize("same_name", (True, False))
async def test_competing_level_source_is_rejected_before_any_real_input_changes(databank_agent, same_name):
    agent = databank_agent
    binding = agent.ports.read
    if not same_name:
        binding = PortBinding(binding.clock, binding.bits, "competing-level-writer")
    competitor = LevelDriver(binding)
    before = tuple(index.U() for index in binding.bits.setIdx)
    try:
        with pytest.raises((RuntimeError, ValueError), match="driver|owner|claim"):
            competitor.set(dict(IDLE, setIdx=(255,) * 4))
        assert tuple(index.U() for index in binding.bits.setIdx) == before
    finally:
        competitor.close()
    await agent.write(3, 15, data=7)
    assert all(entry.data == 7 for entry in await agent.check_read(3))


async def test_sdk_driver_cannot_replace_an_existing_level_owner(databank_agent):
    agent = databank_agent
    competitor = SyncSingleCycleDriver(agent.dut.clock, agent.ports.read.bits,
        idle=IDLE, name="competing-sdk-writer")
    try:
        with pytest.raises((RuntimeError, ValueError), match="driver|owner|claim"):
            await competitor.send(IDLE)
    finally:
        competitor.close()


async def test_owner_can_update_its_persistent_level_without_consuming_an_edge(databank_agent):
    agent = databank_agent
    before = agent._execution.backend.tick
    agent.read_driver.set(dict(IDLE, setIdx=(1,) * 4))
    agent.read_driver.set(IDLE)
    assert agent._execution.backend.tick == before


async def test_closed_level_source_releases_sdk_ownership_but_cannot_be_reused(databank_agent):
    agent = databank_agent
    binding = agent.ports.read
    agent.read_driver.close()
    replacement = LevelDriver(binding)
    try:
        replacement.set(IDLE)
        with pytest.raises(RuntimeError, match="closed"):
            agent.read_driver.set(IDLE)
    finally:
        replacement.close()


async def test_rejected_closed_send_cannot_reclaim_inputs_or_advance_time(databank_agent):
    agent = databank_agent
    old = agent.read_driver
    old.close()
    replacement = LevelDriver(agent.ports.read)
    before = agent._execution.backend.tick
    try:
        with pytest.raises(RuntimeError, match="closed"):
            await old.send(IDLE)
        assert agent._execution.backend.tick == before
        replacement.set(IDLE)
    finally:
        old.close()
        replacement.close()
