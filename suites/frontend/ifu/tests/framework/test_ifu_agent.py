"""Real cached transaction chain and Python-observation negative controls."""
import asyncio
from dataclasses import FrozenInstanceError, replace

import pytest
from toffee import MonitorClosedError, SyncSingleCycleDriver

from suites.frontend.ifu.ifu.checker import check_enqueue, check_gpa
from suites.frontend.ifu.ifu.ports import IfuPorts
from suites.frontend.ifu.ifu.types import FetchRequest, Frame
from suites.frontend.ifu.model.cenc import c_addi
from suites.frontend.ifu.model.fetch import build_window
from suites.frontend.ifu.model.isa import addi, jal

pytestmark = [pytest.mark.selftest, pytest.mark.feature('IFU-ENV-002')]


def request(jump=False):
    return FetchRequest(build_window([(jal(1, 0x40) if jump else addi(5, 0, 1), 0),
                                      (c_addi(9, 1), 1)], 0x4000, ftq0=(0, 3)))


@pytest.mark.parametrize('jump', [False, True])
async def test_cached_chain_has_input_identity_and_one_completion(ifu_agent, jump):
    result = await ifu_agent.fetch(request(jump))
    assert result.beat is not None and (result.redirect is not None) == jump
    record = ifu_agent.records[-1]
    assert record.uid == result.uid and record.state == 'completed'
    assert ifu_agent.beat_fires == 1 and ifu_agent.redirects == int(jump)


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_duplicate_output_after_first_result_is_not_hidden_by_fetch(ifu_agent_factory, monkeypatch, phase):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='repeated enqueue'):
        async with agent.running():
            await agent.reset()
            monitor = getattr(agent, '_' + phase)
            capture = monitor.capture
            seen = None

            def duplicate(event):
                nonlocal seen
                value = capture(event)
                if value.beat is not None:
                    seen = value.beat
                elif seen is not None:
                    value = replace(value, beat=seen)
                return value

            monkeypatch.setattr(monitor, 'capture', duplicate)
            await agent.fetch(request())


@pytest.mark.parametrize('field,value', [('size0', 0), ('size0', 33), ('ftq0', (2, 1)),
    ('ftq0', (3, 1)), ('ftq1', (0, 64)), ('start0_pc', 3), ('start0_pc', 1 << 51),
    ('gp0', 1), ('gp1', 1 << 56), ('line_offset0', 1), ('line0', (0,) * 31),
    ('map', 0), ('paddr0', 3), ('exc0', 6), ('pbmt0', 4), ('pmp0', 2)])
def test_request_rejects_invalid_schema_instead_of_native_truncation(field, value):
    with pytest.raises(ValueError):
        FetchRequest(replace(request().window, **{field: value}))


@pytest.mark.parametrize('value', [-2, 1, 1 << 48, 1.0])
def test_full_byte_physical_addresses_are_strict(value):
    with pytest.raises(ValueError):
        FetchRequest(request().window, physical_address=value)


@pytest.mark.parametrize('field,value', [('ibuffer_ready', 2), ('reset', -1), ('backend_empty', '0'),
    ('corruption', (0, 0, 0)), ('cache_hits', (0, 2)), ('bpu_flush', (0, 64)), ('reply_uid', 1)])
def test_frames_reject_missing_or_out_of_domain_controls(field, value):
    with pytest.raises(ValueError):
        Frame(**{field: value})


def test_nested_windows_and_snapshots_do_not_alias_mutable_producer_data():
    item = request()
    with pytest.raises(FrozenInstanceError):
        item.window.size0 = 1
    with pytest.raises(FrozenInstanceError):
        item.window.instructions[0].word = 0
    with pytest.raises(TypeError):
        item.window.line0[0] = 1
    with pytest.raises(TypeError):
        FetchRequest({})
    with pytest.raises(TypeError):
        IfuPorts.encode({})


@pytest.mark.parametrize('name', ['reset', 'io_fromICache_req_bits_info_0_data',
    'io_toIBuffer_bits_instrs_0', 'io_toFtq_wbRedirect_valid', 'io_toBackend_gpAddrMem_wen'])
def test_every_bound_port_is_required(ifu_agent_factory, monkeypatch, name):
    agent = ifu_agent_factory()
    with monkeypatch.context() as patch:
        patch.delattr(agent.dut, name)
        with pytest.raises(AttributeError):
            IfuPorts(agent.dut)


@pytest.mark.parametrize('name,width', [('clock', 2), ('io_fromICache_req_bits_info_0_startVAddr_addr', 51),
    ('io_toFtq_wbRedirect_bits_pc', 51), ('io_toIBuffer_bits_foldpc_34', 11)])
def test_width_changes_are_explicit_migration_errors(ifu_agent_factory, monkeypatch, name, width):
    agent = ifu_agent_factory()
    signal = getattr(agent.dut, name)

    class WrongWidth:
        mWidth = width

        def __getattr__(self, key):
            return getattr(signal, key)

    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), name, WrongWidth())
        with pytest.raises(ValueError, match='native width'):
            IfuPorts(agent.dut)


def test_direction_extra_ports_and_pruned_constant_cannot_silently_change(ifu_agent_factory, monkeypatch):
    agent = ifu_agent_factory()
    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), 'io_fromICache_req_valid', agent.dut.io_fromICache_req_ready)
        with pytest.raises(ValueError, match='direction'):
            IfuPorts(agent.dut)
    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), 'unexpected_input', agent.dut.io_fromICache_req_valid)
        with pytest.raises(ValueError, match='port set changed'):
            IfuPorts(agent.dut)
    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), 'io_toIBuffer_bits_instrEndOffset_35_predTaken', agent.dut.io_fromICache_req_ready)
        with pytest.raises(ValueError, match='pruned'):
            IfuPorts(agent.dut)


async def test_second_writer_is_rejected_without_poisoning_the_legal_owner(ifu_agent):
    competitor = SyncSingleCycleDriver(ifu_agent.dut.clock, ifu_agent._ports.bits,
        idle=ifu_agent._ports.encode(Frame()), encoder=ifu_agent._ports.encode, name='competing-ifu-inputs')
    try:
        with pytest.raises((ValueError, RuntimeError), match='claim|owner|driver'):
            await competitor.send(Frame())
    finally:
        competitor.close()
    assert (await ifu_agent.fetch(request())).beat is not None


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_closed_monitor_is_not_a_passing_slot(ifu_agent_factory, phase):
    agent = ifu_agent_factory()
    with pytest.raises(MonitorClosedError):
        async with agent.running():
            await agent.reset()
            await getattr(agent, '_' + phase).aclose()
            await agent.cycle()


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_missing_snapshot_is_not_an_empty_passing_cycle(ifu_agent_factory, monkeypatch, phase):
    agent = ifu_agent_factory()
    with pytest.raises(TypeError, match='complete immutable phase snapshots'):
        async with agent.running():
            await agent.reset()
            monkeypatch.setattr(getattr(agent, '_' + phase), 'capture', lambda _: None)
            await agent.cycle()


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_stale_tick_cannot_be_reassociated_to_a_new_slot(ifu_agent_factory, monkeypatch, phase):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='stale or missing phase snapshot'):
        async with agent.running():
            await agent.reset()
            monitor = getattr(agent, '_' + phase)
            recv = monitor.recv

            async def stale():
                sample = await recv()
                return replace(sample, event=replace(sample.event, tick=sample.event.tick - 2))

            monkeypatch.setattr(monitor, 'recv', stale)
            await agent.fetch(request())


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_hiding_the_required_completion_fails_at_its_actual_phase(ifu_agent_factory, monkeypatch, phase):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='missing or repeated enqueue'):
        async with agent.running():
            await agent.reset()
            monitor = getattr(agent, '_' + phase)
            capture = monitor.capture
            monkeypatch.setattr(monitor, 'capture', lambda event: replace(capture(event), beat=None))
            await agent.fetch(request())


async def test_zero_acceptance_is_rejected_by_the_actual_fetch_chain(ifu_agent_factory, monkeypatch):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='fetch_ready'):
        async with agent.running():
            await agent.reset()
            capture = agent._before.capture
            monkeypatch.setattr(agent._before, 'capture', lambda event: replace(capture(event), fetch_ready=0))
            await agent.fetch(request())
    assert agent.req_fires == agent.beat_fires == 0


async def test_same_payload_wrong_ftq_and_valid_mask_cannot_hide_missing_checks(ifu_agent):
    item = request()
    result = await ifu_agent.fetch(item)
    check_enqueue(result.beat, item, 0)
    for changed in (replace(result.beat, valid=0), replace(result.beat, enq=0),
            replace(result.beat, ftq=((1, 3),) + result.beat.ftq[1:])):
        with pytest.raises(AssertionError):
            check_enqueue(changed, item, 0)


async def test_gpa_payload_and_presence_use_the_same_production_checker(ifu_agent):
    item = FetchRequest(replace(request().window, exc0=2, gp0=0x1234))
    result = await ifu_agent.fetch(item)
    check_gpa(result.gpa, item, 0)
    for changed in (None, replace(result.gpa, address=0x1236), replace(result.gpa, ftq_index=4),
                    replace(result.gpa, for_vs=1)):
        with pytest.raises(AssertionError):
            check_gpa(changed, item, 0)


async def test_task_handoffs_keep_exact_phase_and_uid_slots(ifu_agent):
    first = await ifu_agent.cycle()
    for _ in range(12):
        await asyncio.sleep(0)
    second = await ifu_agent.cycle()
    assert second.after_tick == first.after_tick + 2 and second.sequence == first.sequence + 1
    with pytest.raises(FrozenInstanceError):
        second.before.fetch_ready = 0


async def test_concurrent_cycles_do_not_reuse_an_input_slot(ifu_agent):
    pending = asyncio.create_task(ifu_agent.cycle())
    try:
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match='concurrent'):
            await ifu_agent.cycle()
    finally:
        await pending


@pytest.mark.parametrize('operation', ['cycle', 'reset', 'cancel'])
async def test_swallowed_errors_stay_unreconciled_after_capture_is_restored(ifu_agent_factory, monkeypatch, operation):
    agent = ifu_agent_factory()
    with pytest.raises(RuntimeError, match='unreconciled sampled slot'):
        async with agent.running():
            await agent.reset()
            with monkeypatch.context() as patch:
                capture = agent._after.capture
                patch.setattr(agent._after, 'capture', lambda event: replace(capture(event), fetch_ready=0))
                with pytest.raises(AssertionError):
                    if operation == 'reset':
                        await agent.reset()
                    elif operation == 'cancel':
                        await agent.cancel_pending('explicit control')
                    else:
                        await agent.cycle()


async def test_cancelled_python_operation_cannot_be_finished_as_clean(ifu_agent_factory):
    agent = ifu_agent_factory()
    with pytest.raises(RuntimeError, match='unreconciled sampled slot'):
        async with agent.running():
            await agent.reset()
            pending = asyncio.create_task(agent.cycle())
            await asyncio.sleep(0)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending


async def test_incomplete_carry_requires_completion_or_explicit_cancellation(ifu_agent_factory):
    agent = ifu_agent_factory()
    program = [(c_addi(8, 1), 1)] * 31 + [(addi(5, 0, 1), 0)]
    item = FetchRequest(build_window(program, 0x8000, truncate=1))
    with pytest.raises(AssertionError, match='incomplete carry'):
        async with agent.running():
            await agent.reset()
            await agent.fetch(item)


async def test_explicit_carry_cancel_and_reset_preserve_history_without_automatic_debt_clear(ifu_agent):
    program = [(c_addi(8, 1), 1)] * 31 + [(addi(5, 0, 1), 0)]
    await ifu_agent.fetch(FetchRequest(build_window(program, 0x8000, truncate=1)))
    assert ifu_agent.carry is not None
    with pytest.raises(ValueError, match='explicit reason'):
        await ifu_agent.reset()
    await ifu_agent.cancel_pending('scenario intentionally ends before the upper half')
    assert ifu_agent.carry is None
    old = await ifu_agent.cycle(Frame(request=request(), ibuffer_ready=0))
    await ifu_agent.reset(reason='reset the explicitly accepted fetch')
    assert next(record for record in ifu_agent.records if record.uid == old.accepted_uid).state == 'cancelled'
    assert (await ifu_agent.fetch(request())).uid != old.accepted_uid


async def test_watchdog_finish_and_invalid_budgets_are_not_zero_work_success(ifu_agent_factory):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='did not complete within 1 cycles'):
        async with agent.running():
            await agent.reset()
            await agent.fetch(request(), max_cycles=1)
    assert agent.req_fires == 1 and agent.beat_fires == 0


async def test_valid_input_after_rejected_arguments_and_strict_finish_once(ifu_agent):
    for budget in (0, -1, 1.5, True):
        with pytest.raises(ValueError):
            await ifu_agent.fetch(request(), max_cycles=budget)
        with pytest.raises(ValueError):
            await ifu_agent.reset(budget)
    with pytest.raises(TypeError):
        await ifu_agent.cycle({})
    with pytest.raises(ValueError):
        await ifu_agent.cancel_pending('')
    await ifu_agent.fetch(request())
    await ifu_agent.finish()
    await ifu_agent.finish()
    with pytest.raises(RuntimeError, match='finished'):
        await ifu_agent.cycle()


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_repeated_redirect_after_its_first_result_is_not_an_allowed_tail(ifu_agent_factory, monkeypatch, phase):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='missing or repeated redirect'):
        async with agent.running():
            await agent.reset()
            monitor = getattr(agent, '_' + phase)
            capture, seen = monitor.capture, None

            def duplicate(event):
                nonlocal seen
                value = capture(event)
                if value.redirect is not None:
                    seen = value.redirect
                elif seen is not None:
                    value = replace(value, redirect=seen)
                return value

            monkeypatch.setattr(monitor, 'capture', duplicate)
            await agent.fetch(request(True))


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_same_tick_wrong_payload_is_rejected_by_the_actual_fetch_chain(ifu_agent_factory, monkeypatch, phase):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='ifu.top.enqueue'):
        async with agent.running():
            await agent.reset()
            monitor = getattr(agent, '_' + phase)
            capture = monitor.capture

            def wrong(event):
                value = capture(event)
                if value.beat is not None:
                    payload = (value.beat.instrs[0] ^ 1,) + value.beat.instrs[1:]
                    value = replace(value, beat=replace(value.beat, instrs=payload))
                return value

            monkeypatch.setattr(monitor, 'capture', wrong)
            await agent.fetch(request())


async def test_incorrect_expected_payload_is_rejected_by_the_same_production_fetch(ifu_agent_factory, monkeypatch):
    from suites.frontend.ifu.ifu import checker
    agent = ifu_agent_factory()
    oracle = checker.cached_expectation

    def wrong(*args, **kwargs):
        expected, *other = oracle(*args, **kwargs)
        words = list(expected.instrs)
        words[0] ^= 1
        return (replace(expected, instrs=words), *other)

    with pytest.raises(AssertionError, match='ifu.top.enqueue'):
        async with agent.running():
            await agent.reset()
            monkeypatch.setattr(checker, 'cached_expectation', wrong)
            await agent.fetch(request())


async def test_unrelated_carry_metadata_is_rejected_before_a_physical_slot(ifu_agent):
    first = await ifu_agent.cycle()
    word = addi(5, 0, 1)
    invented = FetchRequest(build_window([(c_addi(9, 1), 1)], 0x9000, carry_word=word))
    with pytest.raises(ValueError, match='carry history'):
        await ifu_agent.fetch(invented)
    assert (await ifu_agent.cycle()).after_tick == first.after_tick + 2
    await ifu_agent.fetch(request())


async def test_ecc_is_one_post_acceptance_pulse_and_input_payload_is_withdrawn(ifu_agent, monkeypatch):
    frames = []
    send = ifu_agent._driver.send

    async def record(frame):
        frames.append(frame)
        return await send(frame)

    monkeypatch.setattr(ifu_agent._driver, 'send', record)
    result = await ifu_agent.fetch(request(), corruption=(1, 0, 0, 0))
    assert result.beat.exception_type == 5
    assert [index for index, frame in enumerate(frames) if any(frame.corruption)] == [1]
    assert frames[0].request is not None and all(frame.request is None for frame in frames[1:])


async def test_promised_fetch_cancelled_on_fire_is_not_reoffered_as_an_accepted_uid(ifu_agent_factory):
    agent = ifu_agent_factory()
    with pytest.raises(AssertionError, match='cancelled on fire, not accepted'):
        async with agent.running():
            await agent.reset()
            await agent.fetch(request(), frame=Frame(backend_redirect=1))
    assert agent.req_fires == agent.cancelled_on_fire == 1 and agent.beat_fires == 0
