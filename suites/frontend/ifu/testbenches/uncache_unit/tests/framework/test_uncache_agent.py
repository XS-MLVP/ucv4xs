"""Producer/port domains, actual UID ledger, sampling and bounded-tail controls.

Python snapshot/expectation injection is checker/runtime evidence, not mutation
of the RTL or additional hardware functionality credit.
"""
import asyncio
from dataclasses import FrozenInstanceError, replace

import pytest
from toffee import MonitorClosedError, SyncSingleCycleDriver

from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import Inputs
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import NC
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import Outputs
from suites.frontend.ifu.testbenches.uncache_unit.checker import RESET
from suites.frontend.ifu.testbenches.uncache_unit.checker import check_outputs
from suites.frontend.ifu.testbenches.uncache_unit.env.ports import UncachePorts
from suites.frontend.ifu.testbenches.uncache_unit.transactions import BusReply
from suites.frontend.ifu.testbenches.uncache_unit.transactions import Frame
from suites.frontend.ifu.testbenches.uncache_unit.transactions import ReadRequest

pytestmark = [pytest.mark.selftest, pytest.mark.feature('IFU-ENV-002')]


async def accept(agent, *, mmio=0):
    checked = await agent.cycle(Inputs(req_valid=1, req_paddr=0x4000, req_is_mmio=mmio,
                                      req_pbmt=NC, to_ready=0))
    return checked.events.accepted_uid


async def issue(agent):
    uid = await accept(agent)
    checked = await agent.cycle(Inputs(to_ready=1))
    assert checked.events.bus_fire_uid == uid
    return uid


@pytest.mark.feature('IFU-ENV-004')
@pytest.mark.parametrize('field,value', [
    ('flush', 2), ('req_valid', -1), ('req_is_mmio', '0'), ('is_first_instr', 1.0),
    ('ifu_stall', 2), ('empty_after', -1), ('to_ready', 2), ('from_valid', 2),
    ('from_corrupt', -1), ('from_denied', 2), ('from_need_resend', 1.0),
    ('req_paddr', -2), ('req_paddr', 1), ('req_paddr', 1 << 48), ('req_paddr', 0.0),
    ('req_pbmt', -1), ('req_pbmt', 4), ('from_data', -1), ('from_data', 1 << 32),
])
def test_input_fields_do_not_use_native_truncation_or_coercion(field, value):
    with pytest.raises(ValueError):
        Inputs(**{field: value})


def test_nested_transactions_and_valid_reply_relationship_are_strict():
    with pytest.raises(ValueError, match='denied.*corrupt'):
        BusReply(0, denied=1)
    with pytest.raises(ValueError):
        ReadRequest(1)
    with pytest.raises(TypeError):
        Inputs(req_address=0)
    with pytest.raises(TypeError):
        Frame(inputs={})
    with pytest.raises(ValueError):
        Frame(reset=2)
    for item, field in ((Inputs(), 'flush'), (ReadRequest(0), 'paddr'), (BusReply(1), 'data')):
        with pytest.raises(FrozenInstanceError):
            setattr(item, field, 1)


def test_address_units_and_upper_bit_are_preserved_only_in_ports():
    request = ReadRequest((1 << 48) - 2)
    encoded = UncachePorts.encode(Frame(Inputs(req_valid=1, req_paddr=request.paddr, req_pbmt=NC)))
    assert encoded['req_paddr'] == (1 << 47) - 1 and request.paddr == (1 << 48) - 2
    with pytest.raises(TypeError):
        UncachePorts.encode({})


@pytest.mark.parametrize('field,value', [('req_ready', 2), ('resp_data', 1 << 32),
                                      ('resp_exception', 8), ('to_paddr', 1)])
def test_complete_typed_outputs_cannot_be_replaced_with_missing_or_invalid_values(field, value):
    with pytest.raises(ValueError):
        replace(RESET, **{field: value})
    with pytest.raises(TypeError, match='complete semantic Outputs'):
        check_outputs(None, RESET, phase='missing')
    with pytest.raises(TypeError, match='override'):
        check_outputs(RESET, RESET, expected={}, phase='wrong-type')


@pytest.mark.parametrize('name', ['reset', 'io_req_bits_paddr_addr', 'io_fromUncache_resp_valid',
                                 'io_resp_bits_uncacheData', 'io_toUncache_req_bits_memPageTypeNC'])
def test_missing_ports_are_not_zero_defaults(uncache_unit_factory, monkeypatch, name):
    agent = uncache_unit_factory()
    with monkeypatch.context() as patch:
        patch.delattr(agent.dut, name)
        with pytest.raises(AttributeError):
            UncachePorts(agent.dut)


@pytest.mark.parametrize('name,width', [('io_req_bits_paddr_addr', 48), ('io_toUncache_req_bits_addr_addr', 46),
    ('io_resp_bits_uncacheData', 31), ('io_req_bits_pbmt', 3), ('clock', 2)])
def test_changed_width_is_a_migration_error(uncache_unit_factory, monkeypatch, name, width):
    agent = uncache_unit_factory()
    signal = getattr(agent.dut, name)

    class WrongWidth:
        mWidth = width

        def __getattr__(self, key):
            return getattr(signal, key)

    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), name, WrongWidth())
        with pytest.raises(ValueError, match='native width'):
            UncachePorts(agent.dut)


def test_wrong_direction_extra_inputs_and_changed_pruned_ready_fail(uncache_unit_factory, monkeypatch):
    agent = uncache_unit_factory()
    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), 'io_req_valid', agent.dut.io_req_ready)
        with pytest.raises(ValueError, match='direction'):
            UncachePorts(agent.dut)
    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), 'new_input', agent.dut.io_req_valid)
        with pytest.raises(ValueError, match='input ownership'):
            UncachePorts(agent.dut)
    assert agent._ports.response_always_ready is True
    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), 'io_fromUncache_resp_ready', agent.dut.io_req_ready)
        with pytest.raises(ValueError, match='pruned response-ready=1'):
            UncachePorts(agent.dut)


async def test_second_writer_fails_and_owner_can_still_finish_a_real_read(uncache_unit):
    agent = uncache_unit
    competitor = SyncSingleCycleDriver(agent.dut.clock, agent._ports.bits,
        idle=agent._ports.encode(Frame()), encoder=agent._ports.encode, name='competing-uncache-writer')
    try:
        with pytest.raises((ValueError, RuntimeError), match='driver|claim|owner'):
            await competitor.send(Frame())
    finally:
        competitor.close()
    assert (await agent.read(ReadRequest(0x4000), BusReply(1))).cycle.after.resp_valid == 1


@pytest.mark.parametrize('pbmt,mmio', [(0, 0), (3, 0), (3, 1)])
async def test_unreachable_request_types_are_explicit_port_pressure_not_silently_dropped(uncache_unit, pbmt, mmio):
    before = uncache_unit.checked_cycles
    inputs = Inputs(req_valid=1, req_pbmt=pbmt, req_is_mmio=mmio, to_ready=0)
    with pytest.raises(ValueError, match='IFU producer'):
        await uncache_unit.cycle(inputs)
    assert uncache_unit.checked_cycles == before
    checked = await uncache_unit.characterize_cycle(inputs)
    assert checked.events.accepted_uid is not None
    await uncache_unit.cancel_pending('explicitly finish characterized request')


async def test_unknown_duplicate_early_and_boolean_reply_uids_are_rejected(uncache_unit):
    for uid in (-1, 999, True):
        with pytest.raises(ValueError, match='known issued'):
            await uncache_unit.reply(uid, BusReply(1))
    uid = await accept(uncache_unit)
    with pytest.raises(ValueError, match='before.*issued'):
        await uncache_unit.reply(uid, BusReply(1))
    await uncache_unit.cycle(Inputs(to_ready=1))
    await uncache_unit.reply(uid, BusReply(1))
    with pytest.raises(ValueError, match='duplicate'):
        await uncache_unit.reply(uid, BusReply(1))


async def test_cancelled_uid_cannot_be_invented_for_unissued_work_or_aliased_to_a_new_waiting_read(uncache_unit):
    not_issued = await accept(uncache_unit)
    await uncache_unit.cancel_pending('not issued')
    with pytest.raises(ValueError, match='before.*issued'):
        await uncache_unit.reply(not_issued, BusReply(1))
    old = await issue(uncache_unit)
    await uncache_unit.cancel_pending('issued old generation; peer filters replies')
    new = await issue(uncache_unit)
    before = uncache_unit.checked_cycles
    with pytest.raises(ValueError, match='tagless response'):
        await uncache_unit.reply(old, BusReply(1))
    assert uncache_unit.checked_cycles == before
    assert (await uncache_unit.reply(new, BusReply(1))).events.completed_uid == new


async def test_old_characterized_request_is_not_promoted_to_producer_provenance(uncache_unit):
    checked = await uncache_unit.characterize_cycle(Inputs(req_valid=1, req_pbmt=3, to_ready=0))
    uid = checked.events.accepted_uid
    await uncache_unit.characterize_cycle(Inputs(to_ready=1))
    with pytest.raises(ValueError, match='no producer reply provenance'):
        await uncache_unit.reply(uid, BusReply(1))
    await uncache_unit.cancel_pending('characterization complete')


async def test_tagless_producer_input_cannot_infer_its_own_uid_from_live_state(uncache_unit):
    uid = await issue(uncache_unit)
    before = uncache_unit.checked_cycles
    with pytest.raises(ValueError, match='explicit issued UID'):
        await uncache_unit.cycle(Inputs(from_valid=1, from_data=1))
    assert uncache_unit.checked_cycles == before
    assert (await uncache_unit.reply(uid, BusReply(1))).events.completed_uid == uid


@pytest.mark.parametrize('address,reply', [(0x4000, BusReply(0x113, need_resend=1)),
    (0x4FFE, BusReply(1, need_resend=1)), (0x4FFE, BusReply(0x113)),
    (0x4FFE, BusReply(0x113, corrupt=1, need_resend=1))])
async def test_invalid_peer_resend_relationship_is_rejected_before_starting_read(uncache_unit, address, reply):
    before = uncache_unit.checked_cycles
    with pytest.raises(ValueError, match='needResend'):
        await uncache_unit.read(ReadRequest(address), reply)
    assert uncache_unit.checked_cycles == before and uncache_unit.status.accepted == 0
    await uncache_unit.read(ReadRequest(0x4000), BusReply(1))


async def test_valid_payload_comparisons_cannot_be_hidden_by_observed_or_override_valid(uncache_unit):
    await accept(uncache_unit)
    oracle = uncache_unit._model.outputs(Inputs(to_ready=0))
    observed = (await uncache_unit.cycle(Inputs(to_ready=0))).before
    check_outputs(observed, oracle, phase='legal-control')
    for field in ('req_ready', 'to_valid', 'to_paddr', 'to_mem_back_mm', 'to_mem_page_nc'):
        wrong = replace(observed, **{field: getattr(observed, field) ^ (2 if field == 'to_paddr' else 1)})
        with pytest.raises(AssertionError):
            check_outputs(wrong, oracle, phase='wrong-bus-payload')
    bad = replace(observed, to_valid=0, to_paddr=observed.to_paddr ^ 2)
    with pytest.raises(AssertionError, match='to_paddr'):
        check_outputs(bad, oracle, expected=replace(oracle, to_valid=0), phase='mask-override')
    await uncache_unit.cycle(Inputs(to_ready=1))
    uid = uncache_unit.status.active_uid
    completed = (await uncache_unit.reply(uid, BusReply(0x113))).after
    for field in ('resp_valid', 'resp_data', 'resp_exception', 'resp_need_resend'):
        with pytest.raises(AssertionError):
            check_outputs(replace(completed, **{field: getattr(completed, field) ^ 1}), completed, phase='wrong-response')


def test_only_contractually_invalid_payload_is_ignored_and_zero_reset_is_separate():
    altered = replace(RESET, to_paddr=0x4000, to_mem_back_mm=0, to_mem_page_nc=1,
                      resp_data=0x123, resp_exception=3, resp_need_resend=1)
    check_outputs(altered, RESET, phase='inactive-legal-payload')
    for field in ('req_ready', 'to_valid', 'resp_valid'):
        with pytest.raises(AssertionError):
            check_outputs(replace(altered, **{field: getattr(altered, field) ^ 1}), RESET, phase='wrong-valid')


async def test_reset_retains_uid_history_and_requires_a_reason_for_active_work(uncache_unit):
    old = await issue(uncache_unit)
    epoch = uncache_unit.status.epoch
    with pytest.raises(ValueError, match='cancellation reason'):
        await uncache_unit.reset()
    await uncache_unit.reset(reason='test explicitly resets accepted work')
    assert uncache_unit.status.epoch == epoch + 1 and uncache_unit.status.cancelled == 1
    late = await uncache_unit.reply(old, BusReply(1))
    assert late.events.completed_uid is None and uncache_unit.status.completed == 0
    new = await uncache_unit.read(ReadRequest(0x4000), BusReply(1))
    assert new.uid != old and uncache_unit.status.completed == 1


async def test_task_handoffs_do_not_advance_or_cross_associate_phase_samples(uncache_unit):
    first = await uncache_unit.cycle()
    for _ in range(12):
        await asyncio.sleep(0)
    second = await uncache_unit.cycle()
    assert second.after_tick == first.after_tick + 2 and second.before_tick + 1 == second.after_tick
    assert second.sequence == first.sequence + 1
    with pytest.raises(FrozenInstanceError):
        first.before.req_ready = 0


async def test_concurrent_requests_are_rejected_without_reusing_uid_slots(uncache_unit):
    pending = asyncio.create_task(uncache_unit.cycle())
    try:
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match='concurrent'):
            await uncache_unit.cycle()
    finally:
        await pending


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_closed_phase_monitor_cannot_return_a_passing_cycle(uncache_unit_factory, phase):
    agent = uncache_unit_factory()
    with pytest.raises(MonitorClosedError):
        async with agent.running():
            await agent.reset()
            await getattr(agent, '_' + phase).aclose()
            await agent.cycle()


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_stale_tick_is_rejected_even_for_the_same_value(uncache_unit_factory, monkeypatch, phase):
    agent = uncache_unit_factory()
    with pytest.raises(AssertionError, match='stale or missing phase snapshot'):
        async with agent.running():
            await agent.reset()
            monitor = getattr(agent, '_' + phase)
            recv = monitor.recv

            async def stale():
                observed = await recv()
                return replace(observed, event=replace(observed.event, tick=observed.event.tick - 2))

            monkeypatch.setattr(monitor, 'recv', stale)
            await agent.cycle()


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_missing_snapshot_is_not_a_passing_idle_cycle(uncache_unit_factory, monkeypatch, phase):
    agent = uncache_unit_factory()
    with pytest.raises(TypeError, match='complete semantic Outputs'):
        async with agent.running():
            await agent.reset()
            monkeypatch.setattr(getattr(agent, '_' + phase), 'capture', lambda _: None)
            await agent.cycle()


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_stale_payload_cannot_replace_the_current_bus_phase(uncache_unit_factory, monkeypatch, phase):
    agent = uncache_unit_factory()
    with pytest.raises(AssertionError, match='uncache_unit'):
        async with agent.running():
            await agent.reset()
            before = (await agent.cycle()).before
            if phase == 'before':
                await accept(agent)
            monkeypatch.setattr(getattr(agent, '_' + phase), 'capture', lambda _: before)
            if phase == 'before':
                await agent.cycle(Inputs(to_ready=0))
            else:
                await accept(agent)


@pytest.mark.parametrize('phase', ['waiting', 'send', 'issued'])
async def test_finish_cannot_invent_replies_or_reset_outstanding_work(uncache_unit_factory, phase):
    agent = uncache_unit_factory()
    with pytest.raises(AssertionError, match='outstanding request'):
        async with agent.running():
            await agent.reset()
            uid = await accept(agent, mmio=int(phase == 'waiting'))
            if phase == 'issued':
                await agent.cycle(Inputs(to_ready=1))
    assert agent.status.active_uid == uid and agent.status.completed == agent.status.cancelled == 0


async def test_promised_read_with_too_small_budget_fails_not_zero_acceptance_success(uncache_unit_factory):
    agent = uncache_unit_factory()
    with pytest.raises(AssertionError, match='did not complete within1 cycles|did not complete within 1 cycles'):
        async with agent.running():
            await agent.reset()
            await agent.read(ReadRequest(0x4000), BusReply(1), max_cycles=1)
    assert agent.status.accepted == 1 and agent.status.completed == 0


async def test_zero_acceptance_fault_is_rejected_by_the_actual_read_chain(uncache_unit_factory, monkeypatch):
    agent = uncache_unit_factory()
    with pytest.raises(AssertionError, match='req_ready'):
        async with agent.running():
            await agent.reset()
            capture = agent._before.capture
            monkeypatch.setattr(agent._before, 'capture', lambda event: replace(capture(event), req_ready=0))
            await agent.read(ReadRequest(0x4000), BusReply(1))
    assert agent._failed and agent._ledger.accepted == agent._ledger.completed == 0


async def test_hiding_final_completion_is_rejected_at_its_actual_response(uncache_unit_factory, monkeypatch):
    agent = uncache_unit_factory()
    with pytest.raises(AssertionError, match='resp_valid'):
        async with agent.running():
            await agent.reset()
            uid = await issue(agent)
            capture = agent._after.capture
            monkeypatch.setattr(agent._after, 'capture', lambda event: replace(capture(event), resp_valid=0))
            await agent.reply(uid, BusReply(1))
    assert agent._ledger.completed == 0


async def test_finish_detects_a_repeated_completion_instead_of_closing_the_monitor(uncache_unit_factory, monkeypatch):
    agent = uncache_unit_factory()
    with pytest.raises(AssertionError, match='resp_valid'):
        async with agent.running():
            await agent.reset()
            read = await agent.read(ReadRequest(0x4000), BusReply(1))
            monkeypatch.setattr(agent._after, 'capture', lambda _: read.cycle.after)


async def test_reset_assertion_failure_is_sticky_after_capture_is_restored(uncache_unit_factory, monkeypatch):
    agent = uncache_unit_factory()
    with pytest.raises(RuntimeError, match='unreconciled input slot'):
        async with agent.running():
            await agent.reset()
            with monkeypatch.context() as patch:
                patch.setattr(agent._after, 'capture', lambda _: replace(RESET, resp_data=1))
                with pytest.raises(AssertionError, match='uncache_unit.reset'):
                    await agent.reset()


async def test_cancelled_cycle_cannot_be_swallowed_and_then_finished(uncache_unit_factory):
    agent = uncache_unit_factory()
    with pytest.raises(RuntimeError, match='unreconciled input slot'):
        async with agent.running():
            await agent.reset()
            pending = asyncio.create_task(agent.cycle())
            await asyncio.sleep(0)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending


async def test_swallowed_compare_error_cannot_be_erased_by_restoring_capture(uncache_unit_factory, monkeypatch):
    agent = uncache_unit_factory()
    with pytest.raises(RuntimeError, match='unreconciled input slot'):
        async with agent.running():
            await agent.reset()
            with monkeypatch.context() as patch:
                patch.setattr(agent._before, 'capture', lambda _: replace(RESET, req_ready=0))
                with pytest.raises(AssertionError):
                    await agent.cycle()


async def test_invalid_work_and_budgets_do_not_advance_slots_and_finish_is_strict(uncache_unit):
    first = await uncache_unit.cycle()
    for budget in (0, -1, 1.5):
        with pytest.raises(ValueError):
            await uncache_unit.reset(budget)
        with pytest.raises(ValueError):
            await uncache_unit.read(ReadRequest(0x4000), BusReply(1), max_cycles=budget)
    with pytest.raises(TypeError):
        await uncache_unit.cycle({})
    with pytest.raises(ValueError):
        await uncache_unit.cancel_pending('')
    second = await uncache_unit.cycle()
    assert second.after_tick == first.after_tick + 2
    await uncache_unit.finish()
    await uncache_unit.finish()
    with pytest.raises(RuntimeError, match='finished'):
        await uncache_unit.cycle()
