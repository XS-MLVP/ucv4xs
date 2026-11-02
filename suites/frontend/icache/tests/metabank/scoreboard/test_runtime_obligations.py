"""Native protocol/storage/checker discrimination, not new hardware credit."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
import pytest
from toffee import Execution, XCommClockBackend, SyncSingleCycleDriver
from suites.frontend.icache.metabank.agent.main import MetaBankAgent
from suites.frontend.icache.metabank.transaction.types import MetaBankCycle, MetaBankRead, MetaBankWrite, MetaBankBist

pytestmark = pytest.mark.selftest


@asynccontextmanager
async def running(factory):
    dut = factory.create('metabank', coverage_name='metabank-runtime-control.dat')
    backend = XCommClockBackend(dut.GetXClock())
    try:
        async with Execution(backend, max_batch_ticks=64) as execution:
            agent = MetaBankAgent(dut);await agent.start(execution)
            try:yield agent
            finally:await agent.aclose()
    finally:backend.close()


@pytest.mark.parametrize('field', ('valid', 'phy_tag', 'maybe_rvc_map', 'code'))
async def test_default_read_rejects_a_wrong_return_view_without_expected_polling(dut_factory, monkeypatch, field):
    async with running(dut_factory) as agent:
        await agent.write(0x21, 15, phy_tag=7, maybe_rvc_map=8, code=1)
        sample, times = agent.read_entries, []
        tick = agent._execution.backend.tick
        def wrong():
            value = sample();times.append(agent._execution.backend.tick)
            first = value[0]
            if field == 'valid':first = replace(first, valid=first.valid ^ 1)
            else:first = replace(first, entry=replace(first.entry, **{field: getattr(first.entry, field) ^ 1}))
            return (first, *value[1:])
        monkeypatch.setattr(agent, 'read_entries', wrong)
        with pytest.raises(AssertionError) as caught:await agent.read(0x21)
        assert times == [tick + 4]
        with pytest.raises(AssertionError) as repeated:await agent.finish()
        assert repeated.value is caught.value


async def test_stopping_the_unique_frame_consumer_cannot_finish_green(dut_factory):
    async with running(dut_factory) as agent:
        await agent.wait_ready()
        consumer = agent._consumer
        consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)
        tick = agent._execution.backend.tick
        with pytest.raises(RuntimeError, match="consumer|sampling"):
            await agent.finish()
        assert agent._execution.backend.tick == tick


async def test_payload_is_ignored_only_when_the_way_is_really_invalid(metabank_agent, monkeypatch):
    agent = metabank_agent
    await agent.write(0x21, 15, phy_tag=7);await agent.flush_all()
    sample = agent.read_entries
    def inactive_payload():
        values = sample()
        return tuple(replace(way, entry=replace(way.entry, phy_tag=way.entry.phy_tag ^ 1)) for way in values)
    monkeypatch.setattr(agent, 'read_entries', inactive_payload)
    assert all(way.valid == 0 for way in await agent.read(0x21))


@pytest.mark.parametrize('field', ('phyTag', 'maybeRvcMap', 'code', 'waymask'))
async def test_wrong_original_write_fails_without_requiring_readback(dut_factory, monkeypatch, field):
    async with running(dut_factory) as agent:
        put, injected = agent.write_driver.set, []
        def wrong(values):
            if values['valid']:
                values = dict(values, **{field: values[field] ^ 1});injected.append(True)
            return put(values)
        monkeypatch.setattr(agent.write_driver, 'set', wrong)
        with pytest.raises(AssertionError):await agent.write(0x21, 15, phy_tag=7, maybe_rvc_map=8, code=1)
        assert injected


@pytest.mark.parametrize('control', ('reset', 'bist', 'sram'))
async def test_each_control_plane_has_a_real_sdk_owner(metabank_agent, control):
    agent = metabank_agent
    signal = agent.dut.reset if control == 'reset' else agent.ports.mbist.bits.req if control == 'bist' else agent.ports.sram_control.bits.ways[1].mcp_hold
    competitor = SyncSingleCycleDriver(agent.dut.clock, signal, idle=0, name='metabank.competing-control')
    try:
        with pytest.raises((ValueError, RuntimeError), match='driver|owner|claim'):await competitor.send(0)
    finally:competitor.close()
    await agent.write(0x21, 15, phy_tag=7)


@pytest.mark.parametrize('cycles', (0, -1, True, 1.5))
async def test_invalid_reset_has_no_input_or_time_side_effect(metabank_agent, monkeypatch, cycles):
    agent = metabank_agent
    tick, calls, idle = agent._execution.backend.tick, [], agent.idle_inputs
    def observed():calls.append(True);return idle()
    monkeypatch.setattr(agent, 'idle_inputs', observed)
    with pytest.raises(ValueError):await agent.reset(cycles)
    assert not calls and agent._execution.backend.tick == tick


async def test_only_a_planned_input_can_acquire_response_identity(dut_factory):
    async with running(dut_factory) as agent:
        await agent.write(0x21, 15, phy_tag=7)
        agent.read_driver.set(dict(valid=1, setIdx=0x21))
        with pytest.raises(AssertionError):await agent._edge()
        with pytest.raises(AssertionError):await agent.finish()


async def test_equal_payloads_keep_distinct_read_and_storage_ancestry(metabank_agent):
    agent = metabank_agent
    await agent.write(0x21, 15, phy_tag=7);await agent.write(0x22, 15, phy_tag=7)
    values = await asyncio.gather(agent.read(0x21), agent.read(0x21), agent.read(0x22))
    assert all(entry.entry.phy_tag == 7 for ways in values for entry in ways)
    rows = [row for row in (await agent.finish())['inputs'] if row.kind == 'read']
    assert len({row.uid for row in rows}) == 3
    assert all(row.launch_tick + 2 == row.accepted_tick == row.response_tick == row.delivery_tick for row in rows)
    assert rows[0].storage_sources == rows[1].storage_sources
    assert rows[0].storage_sources != rows[2].storage_sources


async def test_both_real_macros_and_byte_masks_update_tags_but_not_validity_ancestors(metabank_agent):
    agent = metabank_agent
    await agent.write(0x21, 15, phy_tag=7, maybe_rvc_map=8, code=1)
    low = (0x123456789 << 33) | (0x12345678 << 1) | 1
    high = (0x23456789a << 33) | (0x87654321 << 1)
    word = low | (high << 69)
    for group in (0, 1):
        await agent.bist_command(array=group, readen=0, writeen=1, be=1, addr=0x33, addr_rd=0xa1, indata=word)
        ack, actual = await agent.bist_command(array=group, addr_rd=0x21)
        old = (7 << 33) | (8 << 1) | 1
        assert ack == 1 and actual == low | (old << 69)
    values = await agent.read(0x21)
    assert [way.entry.phy_tag for way in values] == [0x123456789, 7, 0x123456789, 7]
    rows = agent.receipt()['inputs'];read = rows[-1]
    assert all(origin.kind == 'write' for origin in read.validity_sources)
    assert read.storage_sources[0].kind == read.storage_sources[2].kind == 'bist'
    assert read.storage_sources[0].uid != read.storage_sources[2].uid


async def test_flush_wins_validity_without_fabricating_a_discarded_tag_write(metabank_agent):
    agent = metabank_agent
    await agent.wait_ready()
    offered = await agent.cycle(MetaBankCycle(write=MetaBankWrite(0x21, 1, 7, 8, 1), flush_all=1))
    await agent.cycle();await agent.cycle()
    assert all(not way.valid for way in await agent.read(0x21))
    ack, actual = await agent.bist_command(array=0, addr_rd=0x21)
    assert ack == 1 and actual == (7 << 33) | (8 << 1) | 1
    row = next(row for row in agent.receipt()['inputs'] if row.uid in offered.launched and row.kind == 'write')
    assert row.memory_tick is not None and row.validity_tick is None


async def test_zero_mask_is_accepted_without_claiming_memory_or_validity_effects(metabank_agent):
    agent = metabank_agent
    await agent.write(0x21, 0, phy_tag=(1 << 36) - 1, maybe_rvc_map=(1 << 32) - 1, code=1)
    row = agent.receipt()['inputs'][-1]
    assert row.state == 'empty-write' and row.memory_tick is None and row.validity_tick is None
    assert all(not way.valid for way in await agent.read(0x21))


async def test_reset_cancels_an_offered_read_and_preserves_completed_history(metabank_agent):
    agent = metabank_agent
    await agent.write(0x21, 15, phy_tag=7);await agent.read(0x21)
    prior = agent.receipt()['inputs']
    offered = await agent.cycle(MetaBankCycle(read=MetaBankRead(0x21)))
    await agent.reset()
    assert all(not way.valid for way in await agent.read(0x21))
    receipt = await agent.finish()
    assert receipt['inputs'][:len(prior)] == prior
    old = next(row for row in receipt['inputs'] if row.uid in offered.launched)
    assert old.state == 'reset-cancelled' and old.response_tick is None


@pytest.mark.parametrize('kind', ('read', 'reset'))
async def test_prelaunch_cancellation_cannot_be_executed_by_finish(dut_factory, monkeypatch, kind):
    async with running(dut_factory) as agent:
        await agent.wait_ready()
        entered, forever = asyncio.Event(), asyncio.Event()
        target, name = (agent, '_edge') if kind == 'read' else (agent.reset_driver, 'send')
        original = getattr(target, name)
        async def blocked(*args):entered.set();await forever.wait()
        monkeypatch.setattr(target, name, blocked)
        task = asyncio.create_task(agent.cycle(MetaBankCycle(read=MetaBankRead(0x21))) if kind == 'read' else agent.reset())
        await entered.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        monkeypatch.setattr(target, name, original)
        tick = agent._execution.backend.tick
        with pytest.raises(AssertionError):await agent.finish()
        assert agent._execution.backend.tick == tick


async def test_closed_monitor_and_bypassed_delivery_cannot_finish_green(dut_factory, monkeypatch):
    async with running(dut_factory) as agent:
        await agent.after_monitor.aclose()
        with pytest.raises(RuntimeError):await agent.read(0x21)
        with pytest.raises(RuntimeError):await agent.finish()
    async with running(dut_factory) as agent:
        monkeypatch.setattr(agent.checker, 'deliver', lambda *_: None)
        await agent.read(0x21)
        with pytest.raises(AssertionError):await agent.finish()
