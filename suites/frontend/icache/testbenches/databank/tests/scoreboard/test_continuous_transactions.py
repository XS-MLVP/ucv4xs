"""Native transaction adapter discrimination, not new RTL feature credit."""
import asyncio
from dataclasses import replace
import pytest
from toffee import SyncSingleCycleDriver
from suites.frontend.icache.testbenches.databank.transactions.types import BankBist
from suites.frontend.icache.testbenches.databank.transactions.types import BankCycle
from suites.frontend.icache.testbenches.databank.transactions.types import BankPortRead
from suites.frontend.icache.testbenches.databank.transactions.types import BankReadData
from suites.frontend.icache.testbenches.databank.transactions.types import BankWrite
from suites.frontend.icache.testbenches.databank.tests.scoreboard.support import running

pytestmark = pytest.mark.selftest


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


async def test_default_read_checks_even_a_corrupted_return_view_without_opt_in(dut_factory, monkeypatch):
    async with running(dut_factory) as agent:
        await agent.write(0x21, 15, data=7, code=1)
        read = agent.read_entries
        monkeypatch.setattr(agent, 'read_entries', lambda: (replace(read()[0], data=6), *read()[1:]))
        with pytest.raises(AssertionError) as caught:
            await agent.read(0x21)
        with pytest.raises(AssertionError) as repeated:
            await agent.finish()
        assert repeated.value is caught.value


async def test_wrong_original_write_fails_without_any_readback(dut_factory, monkeypatch):
    async with running(dut_factory) as agent:
        put, injected = agent.write_driver.set, []
        def wrong(values):
            if values['valid']:
                values = dict(values, data=values['data'] ^ 1)
                injected.append(True)
            return put(values)
        monkeypatch.setattr(agent.write_driver, 'set', wrong)
        with pytest.raises(AssertionError):
            await agent.write(0x21, 15, data=7, code=1)
        assert injected


@pytest.mark.parametrize('field', ('data', 'code'))
async def test_continuous_monitor_checks_first_native_response_even_when_only_cycles_are_used(dut_factory, monkeypatch, field):
    async with running(dut_factory) as agent:
        await agent.write(0x21, 15, data=7, code=1)
        capture, injected = agent.after_monitor.capture, []
        offered = await agent.cycle(BankCycle(read=BankPortRead((0x21,) * 4)))
        def wrong(event):
            value = capture(event)
            if event.tick == offered.tick + 2:
                entries = value.entries
                bad = (getattr(entries, field)[0] ^ 1, *getattr(entries, field)[1:])
                value = replace(value, entries=replace(entries, **{field: bad}))
                injected.append(event.tick)
            return value
        monkeypatch.setattr(agent.after_monitor, 'capture', wrong)
        with pytest.raises(AssertionError):
            await agent.cycle()
        assert injected == [offered.tick + 2]


@pytest.mark.parametrize('group', ('mbist', 'sram_control'))
async def test_sdk_claim_covers_test_mode_and_every_broadcast_control(databank_agent, group):
    agent = databank_agent
    bits = getattr(agent.ports, group).bits
    contender = SyncSingleCycleDriver(agent.dut.clock, bits, idle={}, name='databank.competing-controls')
    try:
        with pytest.raises((ValueError, RuntimeError), match='driver|owner|claim'):
            await contender.send({})
    finally:
        contender.close()
    await agent.write(0x21, 15, data=7)
    assert (await agent.read(0x21))[0].data == 7


async def test_repeated_equal_inputs_have_distinct_uids_and_concurrent_calls_remain_serialized(databank_agent):
    agent = databank_agent
    await agent.write(0x21, 15, data=7, code=1)
    await agent.write(0x22, 15, data=9)
    values = await asyncio.gather(agent.read(0x21), agent.read(0x21), agent.read(0x22))
    assert [entries[0].data for entries in values] == [7, 7, 9]
    rows = (await agent.finish())['inputs']
    reads = [row for row in rows if row.kind == 'read']
    assert len({row.uid for row in reads}) == 3
    assert all(row.accepted_tick == row.response_tick == row.launch_tick + 2 == row.delivery_tick for row in reads)
    assert reads[0].sources == reads[1].sources
    assert reads[0].sources[0].uid != reads[2].sources[0].uid


async def test_unplanned_read_does_not_acquire_identity_from_equal_old_data(dut_factory):
    async with running(dut_factory) as agent:
        await agent.write(0x21, 15, data=7, code=1)
        agent.read_driver.set(dict(valid=1, setIdx=(0x21,) * 4, waymask=15))
        with pytest.raises(AssertionError):
            await agent._edge()
        with pytest.raises(AssertionError):
            await agent.finish()


async def test_pending_offer_finish_does_not_send_idle_or_consume_the_request(dut_factory):
    async with running(dut_factory) as agent:
        await agent.wait_ready()
        offered = await agent.cycle(BankCycle(read=BankPortRead((0x21,) * 4)))
        tick = agent._execution.backend.tick
        with pytest.raises(AssertionError):
            await agent.finish()
        assert agent._execution.backend.tick == tick
        row = next(row for row in agent.receipt()['inputs'] if row.uid in offered.launched)
        assert row.accepted_tick is None and row.response_tick is None


async def test_closing_a_required_monitor_is_not_an_empty_or_valid_finish(dut_factory):
    async with running(dut_factory) as agent:
        await agent.after_monitor.aclose()
        with pytest.raises(RuntimeError):
            await agent.read(0x21)
        with pytest.raises(RuntimeError):
            await agent.finish()


async def test_reset_cancels_an_unconsumed_offer_but_not_previous_completed_history(databank_agent):
    agent = databank_agent
    await agent.write(0x21, 15, data=7)
    await agent.read(0x21)
    old = agent.receipt()['inputs']
    offered = await agent.cycle(BankCycle(read=BankPortRead((0x21,) * 4)))
    await agent.reset()
    assert all(entry.data == 0 for entry in await agent.read(0x21))
    receipt = await agent.finish()
    assert receipt['inputs'][:len(old)] == old
    cancelled = next(row for row in receipt['inputs'] if row.uid in offered.launched)
    assert cancelled.state == 'reset-cancelled' and cancelled.response_tick is None
    assert receipt['epoch'] > cancelled.planned_epoch


async def test_per_way_addresses_and_zero_masks_are_legal_transaction_inputs(databank_agent):
    agent = databank_agent
    for way in range(4):
        await agent.write(0x21 + way, 1 << way, data=way + 10, code=way & 1)
    await agent.cycle(BankCycle(read=BankPortRead(tuple(range(0x21, 0x25)))))
    value = await agent.cycle()
    assert value.entries.data == (10, 11, 12, 13)
    await agent.write(0x21, 0, data=(1 << 64) - 1, code=1)
    await agent.cycle(BankCycle(read=BankPortRead((0x21,) * 4, 0)))
    empty = await agent.cycle()
    assert empty.responses == () and len(empty.accepted) == 1
    assert (await agent.read(0x21))[0].data == 10


async def test_simultaneous_read_write_preserves_the_unaccepted_read_and_accepted_write_dispositions(databank_agent):
    agent = databank_agent
    await agent.wait_ready()
    offered = await agent.cycle(BankCycle(read=BankPortRead((0x21,) * 4), write=BankWrite(0x21, 15, 7)))
    value = await agent.cycle()
    assert len(value.accepted) == 1 and value.responses == ()
    rows = [row for row in agent.receipt()['inputs'] if row.uid in offered.launched]
    assert [row.state for row in rows] == ['not-accepted', 'written']
    assert (await agent.read(0x21))[0].data == 7


async def test_mbist_beats_preserve_full_word_and_ancestry_without_manual_oracle_writes(databank_agent):
    agent = databank_agent
    word = (0x123456789abcdef0 << 2) | 3
    ack, _ = await agent.bist_command(array=5, readen=0, writeen=1, be=0,
                                    addr=0x44, addr_rd=0x133, indata=word)
    assert ack == 1
    ack, actual = await agent.bist_command(array=5, readen=1, addr_rd=0x33)
    assert ack == 1 and actual == word
    assert (await agent.read(0x33))[1].data == word >> 2
    rows = (await agent.finish())['inputs']
    writes = [row for row in rows if row.kind == 'bist' and row.request.writeen]
    reads = [row for row in rows if row.kind == 'bist' and row.request.readen]
    assert len(writes) == len(reads) == 2 and len({row.uid for row in writes + reads}) == 4
    assert all(row.ack_tick == row.launch_tick + 2 and row.accepted_tick == row.launch_tick + 4 for row in writes + reads)
    assert all(row.response_tick == row.launch_tick + 6 for row in reads)
    source = next(row for row in reversed(rows) if row.kind == 'read').sources[1]
    assert source.kind == 'bist' and source.uid == writes[-1].uid


@pytest.mark.parametrize('field', ('bist_ack', 'bist_outdata'))
async def test_mbist_ack_is_not_a_substitute_for_its_actual_full_word_response(dut_factory, monkeypatch, field):
    async with running(dut_factory) as agent:
        await agent.bist_command(array=4, readen=0, writeen=1, be=1, addr_rd=0x21, indata=7)
        capture, injected = agent.after_monitor.capture, []
        target = agent._execution.backend.tick + (4 if field == 'bist_ack' else 8)
        def wrong(event):
            value = capture(event)
            if event.tick == target:
                value = replace(value, **{field: getattr(value, field) ^ 1})
                injected.append(True)
            return value
        monkeypatch.setattr(agent.after_monitor, 'capture', wrong)
        with pytest.raises(AssertionError):
            await agent.bist_command(array=4, addr_rd=0x21)
        assert injected


async def test_consecutive_mbist_selects_do_not_guess_the_old_response_identity_from_equal_payloads(databank_agent):
    agent = databank_agent
    word = (0x123456789abcdef0 << 2) | 3
    for way in (0, 1):
        await agent.bist_command(array=4 + way, readen=0, writeen=1,
                                 addr_rd=0x21 + way, indata=word)
    first = await agent.cycle(BankCycle(bist=BankBist(array=4, addr_rd=0x21)))
    second = await agent.cycle(BankCycle(bist=BankBist(array=5, addr_rd=0x22)))
    await agent.settle(4)
    rows = agent.receipt()['inputs']
    before = next(row for row in rows if row.uid in first.launched)
    after = next(row for row in rows if row.uid in second.launched)
    assert before.uid != after.uid
    assert before.state == 'bist-result-unselected' and before.response_tick is None
    assert after.state == 'bist-responded' and after.response_tick == second.tick + 6
    assert before.ack_tick == first.tick + 2 and after.ack_tick == second.tick + 2


async def test_functional_fire_overridden_by_a_registered_mbist_command_has_no_false_write_ancestry(databank_agent):
    agent = databank_agent
    await agent.wait_ready()
    word = (0x7777 << 2) | 3
    await agent.cycle(BankCycle(write=BankWrite(0x21, 15, 0x1111),
                               bist=BankBist(array=5, readen=0, writeen=1, addr_rd=0x21, indata=word)))
    shadowed = await agent.cycle(BankCycle(write=BankWrite(0x21, 15, 0x9999)))
    await agent.settle(4)
    values = await agent.read(0x21)
    assert tuple(entry.data for entry in values) == (0x1111, 0x7777, 0x1111, 0x1111)
    rows = agent.receipt()['inputs']
    shadow = next(row for row in rows if row.uid in shadowed.launched)
    assert shadow.state == 'mbist-overridden' and shadow.accepted_tick == shadowed.tick + 2
    assert all(source.uid != shadow.uid for source in rows[-1].sources)


async def test_reset_after_mbist_ack_does_not_promote_ack_to_a_completed_read(databank_agent):
    agent = databank_agent
    await agent.wait_ready()
    offered = await agent.cycle(BankCycle(bist=BankBist(array=4, addr_rd=0x21)))
    acknowledged = await agent.cycle()
    assert acknowledged.bist_ack == 1
    await agent.reset()
    row = next(row for row in agent.receipt()['inputs'] if row.uid in offered.launched)
    assert row.ack_tick is not None and row.response_tick is None and row.state == 'reset-cancelled'
    assert (await agent.read(0x21))[0].data == 0


@pytest.mark.parametrize('field', ('array', 'addr_rd', 'indata'))
async def test_corrupted_mbist_input_is_rejected_even_without_test_or_functional_readback(dut_factory, monkeypatch, field):
    async with running(dut_factory) as agent:
        put, injected = agent.bist_driver.set, []
        def wrong(values):
            if values['req']:
                values = dict(values, **{field: values[field] ^ 1})
                injected.append(True)
            return put(values)
        monkeypatch.setattr(agent.bist_driver, 'set', wrong)
        with pytest.raises(AssertionError):
            await agent.bist_command(array=4, readen=0, writeen=1, addr_rd=0x21, indata=7)
        assert injected


@pytest.mark.parametrize('kind', ('read', 'reset'))
async def test_cancelled_prelaunch_command_cannot_be_executed_by_finish_to_pay_its_debt(dut_factory, monkeypatch, kind):
    async with running(dut_factory) as agent:
        await agent.wait_ready()
        entered, forever = asyncio.Event(), asyncio.Event()
        original = agent._edge if kind == 'read' else agent.reset_driver.send
        async def before_launch(*args, **kwargs):
            entered.set()
            await forever.wait()
        target, method = (agent, '_edge') if kind == 'read' else (agent.reset_driver, 'send')
        monkeypatch.setattr(target, method, before_launch)
        work = asyncio.create_task(agent.cycle(BankCycle(read=BankPortRead((0x21,) * 4)))
                                   if kind == 'read' else agent.reset())
        await entered.wait()
        work.cancel()
        with pytest.raises(asyncio.CancelledError):
            await work
        monkeypatch.setattr(target, method, original)
        tick = agent._execution.backend.tick
        with pytest.raises(AssertionError):
            await agent.finish()
        assert agent._execution.backend.tick == tick, 'finish executed a cancelled input/control plan'
