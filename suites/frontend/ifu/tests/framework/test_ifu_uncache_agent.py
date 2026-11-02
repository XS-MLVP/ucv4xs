"""Top-level uncached composition controls; injections are Python-only, not RTL mutation."""
from dataclasses import replace

import pytest

from suites.frontend.ifu.ifu.types import FetchRequest, Frame
from suites.frontend.ifu.model.cenc import c_addi
from suites.frontend.ifu.model.fetch import build_window
from suites.frontend.ifu.model.isa import addi
from suites.frontend.ifu.uncache_unit.types import BusReply

pytestmark = [pytest.mark.selftest, pytest.mark.feature('IFU-ENV-002')]


def request(address=0x8000, pc=0x4000, **metadata):
    return FetchRequest(build_window([(addi(5, 0, 1), 0)], pc, pbmt0=1, **metadata), address)


async def test_normal_uncached_chain_has_exact_input_bus_reply_and_completion_identity(ifu_agent):
    item = request()
    result = await ifu_agent.read_uncached(item, BusReply(c_addi(10, 5)))
    record = ifu_agent.records[-1]
    assert record.uid == result.uid and record.state == 'completed'
    assert record.unit_accepted_tick < record.issued_tick < record.reply_tick < record.beat_tick
    assert ifu_agent.bus_fires == ifu_agent.reply_fires == ifu_agent.beat_fires == ifu_agent.redirects == 1
    assert result.bus.address == item.physical_address and result.redirect.target == 0x4002


async def test_unknown_early_boolean_and_duplicate_reply_identities_fail_before_a_slot(ifu_agent):
    for uid in (999, -1, True):
        with pytest.raises(ValueError, match='issued UID|positive input-established UID'):
            await ifu_agent.reply(uid, BusReply(c_addi(10, 5)))
    checked = await ifu_agent.cycle(Frame(request=request()))
    uid = checked.accepted_uid
    before = ifu_agent.checked_cycles
    with pytest.raises(ValueError, match='actually issued UID'):
        await ifu_agent.reply(uid, BusReply(c_addi(10, 5)))
    assert ifu_agent.checked_cycles == before
    for _ in range(6):
        checked = await ifu_agent.cycle(Frame(uncache_ready=1))
        if checked.bus_fire_uid == uid:
            break
    assert checked.bus_fire_uid == uid
    await ifu_agent.reply(uid, BusReply(c_addi(10, 5)))
    before = ifu_agent.checked_cycles
    with pytest.raises(ValueError, match='duplicate uncached reply UID'):
        await ifu_agent.reply(uid, BusReply(c_addi(10, 5)))
    assert ifu_agent.checked_cycles == before
    assert (await ifu_agent.collect(uid)).uid == uid


async def test_old_issued_uid_cannot_alias_new_waiting_read_even_with_same_address_and_data(ifu_agent):
    old = await ifu_agent.send_uncached(request())
    await ifu_agent.cancel_pending('peer filters old replies before the next generation')
    new = await ifu_agent.send_uncached(request())
    before = ifu_agent.checked_cycles
    for reply in (ifu_agent.reply, ifu_agent.characterize_reply):
        with pytest.raises(ValueError, match='tagless uncached reply'):
            await reply(old, BusReply(c_addi(10, 5)))
    assert ifu_agent.checked_cycles == before and ifu_agent.beat_fires == 0
    await ifu_agent.reply(new, BusReply(c_addi(10, 5)))
    assert (await ifu_agent.collect(new)).uid == new


@pytest.mark.parametrize('address,response', [
    (0x8000, BusReply(0x113, need_resend=1)),
    (0x8ffe, BusReply(1, need_resend=1)),
    (0x8ffe, BusReply(0x113)),
    (0x8ffe, BusReply(0x113, corrupt=1, need_resend=1)),
])
async def test_real_peer_resend_must_match_clean_full_width_page_final_data(ifu_agent, address, response):
    before = ifu_agent.checked_cycles
    with pytest.raises(ValueError, match='needResend'):
        await ifu_agent.read_uncached(request(address=address), response)
    assert ifu_agent.checked_cycles == before and ifu_agent.req_fires == 0
    assert (await ifu_agent.read_uncached(request(), BusReply(1))).beat is not None


async def test_explicit_peer_port_pressure_keeps_provenance_through_carry_not_just_the_first_reply(ifu_agent):
    word = addi(5, 0, 1)
    first = await ifu_agent.send_uncached(request())
    before = ifu_agent.checked_cycles
    with pytest.raises(ValueError, match='needResend'):
        await ifu_agent.reply(first, BusReply(word & 0xffff, need_resend=1))
    assert ifu_agent.checked_cycles == before
    await ifu_agent.characterize_reply(first, BusReply(word & 0xffff, need_resend=1))
    half = await ifu_agent.collect(first)
    assert half.resend == 1 and half.peer_source == 'port-characterization'
    assert ifu_agent.carry.peer_source == 'port-characterization'
    complete = await ifu_agent.read_uncached(request(pc=0x4002), BusReply(word >> 16))
    assert complete.beat.instrs[0] == word and complete.peer_source == 'port-characterization'


@pytest.mark.parametrize('phase', ['before', 'after'])
@pytest.mark.parametrize('field', ['bus', 'beat', 'redirect'])
async def test_missing_required_channel_is_rejected_by_the_actual_read_chain(ifu_agent_factory, monkeypatch, phase, field):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='bus|missing or repeated'):
        async with agent.running():
            await agent.reset()
            monitor = getattr(agent, '_' + phase)
            capture = monitor.capture
            monkeypatch.setattr(monitor, 'capture', lambda event: replace(capture(event), **{field: None}))
            await agent.read_uncached(request(), BusReply(c_addi(10, 5)))
    assert agent._failed


@pytest.mark.parametrize('phase', ['before', 'after'])
@pytest.mark.parametrize('field', ['bus', 'beat', 'redirect'])
async def test_repeated_channels_are_not_discarded_after_first_uncached_result(ifu_agent_factory, monkeypatch, phase, field):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='bus|missing or repeated'):
        async with agent.running():
            await agent.reset()
            monitor = getattr(agent, '_' + phase)
            capture, seen = monitor.capture, None

            def duplicate(event):
                nonlocal seen
                sample = capture(event)
                if getattr(sample, field) is not None:
                    seen = getattr(sample, field)
                elif seen is not None:
                    sample = replace(sample, **{field: seen})
                return sample

            monkeypatch.setattr(monitor, 'capture', duplicate)
            await agent.read_uncached(request(), BusReply(c_addi(10, 5)))


@pytest.mark.parametrize('field', ['address', 'main_memory', 'noncacheable'])
async def test_wrong_bus_payload_cannot_be_hidden_by_a_successful_issue(ifu_agent_factory, monkeypatch, field):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='bus'):
        async with agent.running():
            await agent.reset()
            capture = agent._before.capture

            def wrong(event):
                sample = capture(event)
                if sample.bus is not None:
                    value = getattr(sample.bus, field) ^ (2 if field == 'address' else 1)
                    sample = replace(sample, bus=replace(sample.bus, **{field: value}))
                return sample

            monkeypatch.setattr(agent._before, 'capture', wrong)
            await agent.read_uncached(request(), BusReply(c_addi(10, 5)))
    assert agent.bus_fires == agent.beat_fires == 0


async def test_wrong_isa_expected_word_fails_the_same_uncached_production_chain(ifu_agent_factory, monkeypatch):
    from suites.frontend.ifu.ifu import checker
    agent = ifu_agent_factory()
    expand = checker.expand

    def wrong(*args, **kwargs):
        result = expand(*args, **kwargs)
        return replace(result, bits=result.bits ^ 1)

    with pytest.raises(AssertionError, match='uncached-enqueue'):
        async with agent.running():
            await agent.reset()
            monkeypatch.setattr(checker, 'expand', wrong)
            await agent.read_uncached(request(), BusReply(c_addi(10, 5)))


@pytest.mark.parametrize('stage', ['accepted', 'send', 'wait_response'])
async def test_finish_cannot_invent_a_reply_or_cancel_an_uncached_obligation(ifu_agent_factory, stage):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='outstanding fetch UIDs'):
        async with agent.running():
            await agent.reset()
            uid = (await agent.cycle(Frame(request=request()))).accepted_uid
            if stage == 'send':
                await agent.idle(4)
            if stage == 'wait_response':
                for _ in range(6):
                    if (await agent.cycle(Frame(uncache_ready=1))).bus_fire_uid == uid:
                        break
    assert agent.records[-1].state == 'pending' and agent.reply_fires == agent.beat_fires == 0


async def test_resend_is_not_final_scenario_completion_and_finish_does_not_flush_it(ifu_agent_factory):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='incomplete carry'):
        async with agent.running():
            await agent.reset()
            result = await agent.read_uncached(request(address=0x8ffe, pc=0x4ffe), BusReply(0x293, need_resend=1))
            assert result.resend == 1 and result.beat is None
    assert agent.records[-1].state == 'resend' and agent.carry is not None


async def test_reset_keeps_issued_history_and_late_reply_cannot_complete_a_new_uid(ifu_agent):
    old = await ifu_agent.send_uncached(request())
    with pytest.raises(ValueError, match='explicit reason'):
        await ifu_agent.reset()
    await ifu_agent.reset(reason='explicit old generation cancellation coordinated with peer')
    assert next(record for record in ifu_agent.records if record.uid == old).state == 'cancelled'
    await ifu_agent.reply(old, BusReply(c_addi(10, 5)))
    new = await ifu_agent.read_uncached(request(), BusReply(c_addi(10, 5)))
    assert new.uid != old and ifu_agent.ignored_replies == 1 and ifu_agent.beat_fires == 1


async def test_zero_bus_issue_does_not_satisfy_send_uncached(ifu_agent_factory):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='was not issued within 5 cycles'):
        async with agent.running():
            await agent.reset()
            await agent.send_uncached(request(), max_cycles=5, frame=Frame(uncache_ready=0))
    assert agent.req_fires == 1 and agent.bus_fires == 0


async def test_collect_watchdog_does_not_complete_without_peer_data(ifu_agent_factory):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='did not complete within 2 cycles'):
        async with agent.running():
            await agent.reset()
            uid = await agent.send_uncached(request())
            await agent.collect(uid, max_cycles=2)
    assert agent.bus_fires == 1 and agent.reply_fires == agent.beat_fires == 0


async def test_swallowed_uncached_compare_error_is_sticky_after_restoring_capture(ifu_agent_factory, monkeypatch):
    agent = ifu_agent_factory()
    with pytest.raises(RuntimeError, match='unreconciled sampled slot'):
        async with agent.running():
            await agent.reset()
            uid = await agent.send_uncached(request())
            with monkeypatch.context() as patch:
                capture = agent._after.capture
                patch.setattr(agent._after, 'capture', lambda event: replace(capture(event), beat=None))
                with pytest.raises(AssertionError, match='missing or repeated enqueue'):
                    await agent.reply(uid, BusReply(c_addi(10, 5)))


async def test_reply_argument_rejections_do_not_advance_or_poison_the_valid_request(ifu_agent):
    uid = await ifu_agent.send_uncached(request())
    before = ifu_agent.checked_cycles
    with pytest.raises(TypeError, match='semantic BusReply'):
        await ifu_agent.reply(uid, {})
    for budget in (0, -1, 1.5, True):
        with pytest.raises(ValueError):
            await ifu_agent.collect(uid, max_cycles=budget)
    with pytest.raises(ValueError):
        Frame(reply=BusReply(1), reply_uid=uid, reply_source='unknown')
    with pytest.raises(ValueError):
        Frame(reply_source='port-characterization')
    assert ifu_agent.checked_cycles == before
    await ifu_agent.reply(uid, BusReply(c_addi(10, 5)))
    assert (await ifu_agent.collect(uid)).uid == uid


async def test_live_ftq_identity_cannot_be_reused_to_disguise_an_uncached_generation(ifu_agent):
    uid = await ifu_agent.send_uncached(request())
    before = ifu_agent.checked_cycles
    with pytest.raises(ValueError, match='live FTQ identity'):
        await ifu_agent.cycle(Frame(request=request(pc=0x5000)))
    assert ifu_agent.checked_cycles == before
    await ifu_agent.reply(uid, BusReply(c_addi(10, 5)))
    await ifu_agent.collect(uid)
    # Reuse after the complete response/tail is a distinct UID, not a duplicate.
    next_read = await ifu_agent.read_uncached(request(pc=0x5000), BusReply(c_addi(10, 5)))
    assert next_read.uid != uid


async def test_ledger_audit_rejects_a_lost_issue_even_after_a_correct_completion(ifu_agent):
    await ifu_agent.read_uncached(request(), BusReply(c_addi(10, 5)))
    ifu_agent._audit()  # Legal control, actual observed history.
    ifu_agent.bus_fires += 1
    try:
        with pytest.raises(AssertionError, match='issued_tick event/UID accounting'):
            ifu_agent._audit()
    finally:
        ifu_agent.bus_fires -= 1


async def test_same_slot_bus_fire_and_backend_cancel_keep_issue_but_never_invent_completion(ifu_agent):
    uid = (await ifu_agent.cycle(Frame(request=request()))).accepted_uid
    for _ in range(6):
        checked = await ifu_agent.cycle()
        if checked.after.bus is not None:
            break
    assert checked.after.bus is not None and ifu_agent.bus_fires == 0
    flushed = await ifu_agent.cycle(Frame(uncache_ready=1, backend_redirect=1))
    assert flushed.bus_fire_uid == uid and ifu_agent.flushed_bus_fires == 1
    record = next(record for record in ifu_agent.records if record.uid == uid)
    assert record.issued_tick is not None and record.state == 'cancelled'
    await ifu_agent.reply(uid, BusReply(c_addi(10, 5)))
    assert ifu_agent.ignored_replies == 1 and ifu_agent.beat_fires == ifu_agent.redirects == 0
    assert (await ifu_agent.read_uncached(request(), BusReply(c_addi(10, 5)))).uid != uid


async def test_same_slot_reply_and_backend_cancel_cannot_create_an_enqueue_or_redirect(ifu_agent):
    uid = await ifu_agent.send_uncached(request())
    checked = await ifu_agent.reply(uid, BusReply(c_addi(10, 5)), frame=Frame(backend_redirect=1))
    assert checked.after.beat is checked.after.redirect is None
    assert ifu_agent.reply_fires == ifu_agent.ignored_replies == 1
    assert ifu_agent.beat_fires == ifu_agent.redirects == 0
    assert (await ifu_agent.read_uncached(request(), BusReply(c_addi(10, 5)))).uid != uid


async def test_uncached_completion_cancels_both_a_younger_stage_and_same_slot_offer(ifu_agent):
    uid = await ifu_agent.send_uncached(request())
    younger = FetchRequest(build_window([(c_addi(9, 1), 1)], 0x5000, ftq0=(0, 2)))
    accepted = await ifu_agent.cycle(Frame(request=younger))
    assert accepted.accepted_uid is not None
    await ifu_agent.reply(uid, BusReply(c_addi(10, 5)))
    newest = FetchRequest(build_window([(c_addi(9, 1), 1)], 0x6000, ftq0=(0, 3)))
    same_slot = await ifu_agent.cycle(Frame(request=newest))
    assert same_slot.beat_uid == same_slot.redirect_uid == uid
    assert same_slot.req_fire_uid is not None and same_slot.accepted_uid is None
    assert next(record for record in ifu_agent.records if record.uid == accepted.accepted_uid).state == 'cancelled'
    assert ifu_agent.records[-1].state == 'cancelled-on-fire'
    await ifu_agent.collect(uid)
    assert ifu_agent.beat_fires == ifu_agent.redirects == 1
