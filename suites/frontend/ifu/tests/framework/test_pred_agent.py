"""PredChecker schema/runtime controls; injection is in Python, never in RTL."""
import asyncio
from dataclasses import FrozenInstanceError, replace

import pytest
from toffee import MonitorClosedError, SyncSingleCycleDriver

from suites.frontend.ifu.model.pred_checker import DIRECT, Instr, LANES, PC_BITS, Request, SLOTS
from suites.frontend.ifu.pred_checker.ports import PredCheckerPorts
from suites.frontend.ifu.pred_checker.types import Frame

pytestmark = [pytest.mark.selftest, pytest.mark.feature('IFU-ENV-002')]


def fault(pc=0x2000):
    return Request(instrs=(Instr(valid=1, pc=pc, branch_type=DIRECT, jump_offset=0x40),
                           Instr(valid=1, pc=pc + 4)) + (Instr(),) * (SLOTS - 2))


@pytest.mark.feature('IFU-ENV-004')
@pytest.mark.parametrize('field,value', [
    ('valid', 2), ('is_rvc', -1), ('is_pred_taken', '1'), ('invalid_taken', 2),
    ('block_sel', 2), ('is_cross_block', 2), ('end_offset', 32), ('end_offset', -1),
    ('branch_type', 4), ('branch_type', -1), ('ras_action', 4),
    ('pc', 1), ('pc', -2), ('pc', 1 << PC_BITS),
    ('jump_offset', 1), ('jump_offset', -(1 << (PC_BITS - 1)) - 2),
    ('jump_offset', 1 << PC_BITS),
])
def test_instruction_cannot_rely_on_native_truncation(field, value):
    with pytest.raises(ValueError):
        Instr(**{field: value})


@pytest.mark.feature('IFU-ENV-004')
@pytest.mark.parametrize('count', [0, SLOTS - 1, SLOTS + 1])
def test_request_must_name_the_entire_window(count):
    with pytest.raises(ValueError, match='exactly 36'):
        Request(instrs=[Instr()] * count)


@pytest.mark.parametrize('lane,instruction', [
    (34, Instr(is_cross_block=1)), (35, Instr(valid=1)),
    (35, Instr(invalid_taken=1)), (35, Instr(branch_type=DIRECT)), (35, Instr(pc=2)),
])
def test_pruned_instruction_fields_cannot_be_silently_ignored(lane, instruction):
    lanes = [Instr()] * SLOTS
    lanes[lane] = instruction
    with pytest.raises(ValueError, match='structurally zero|tied off'):
        Request(instrs=lanes)


def test_requests_detach_mutable_producer_lists_and_freeze_nested_instructions():
    lanes = [Instr()] * SLOTS
    lanes[0] = Instr(valid=1, pc=0x2000)
    request = Request(instrs=lanes)
    lanes[0] = Instr()
    assert request.instrs[0].valid == 1 and isinstance(request.instrs, tuple)
    with pytest.raises(FrozenInstanceError):
        request.instrs[0].valid = 0
    with pytest.raises(FrozenInstanceError):
        request.valid = 0


def test_unknown_keys_and_untyped_instruction_payloads_fail():
    with pytest.raises(TypeError):
        Instr(jump_offest=2)
    with pytest.raises(TypeError):
        Request(instructions=(Instr(),) * SLOTS)
    with pytest.raises(TypeError, match='Instr transaction'):
        Request(instrs=({},) * SLOTS)
    with pytest.raises(ValueError, match='request valid'):
        Request(valid=2)
    with pytest.raises(TypeError, match='semantic Request'):
        Frame(request={'valid': 1})


@pytest.mark.parametrize('field,value', [('reset', 2), ('padding_pc', 1),
                                       ('padding_pc', 1 << PC_BITS)])
def test_driver_control_domain_is_strict(field, value):
    with pytest.raises(ValueError):
        Frame(**{field: value})


@pytest.mark.parametrize('name', ['io_req_bits_instrVec_0_valid',
    'io_resp_stage2Out_checkerRedirect_bits_target_addr'])
def test_missing_input_or_output_is_a_binding_error(pred_checker_factory, monkeypatch, name):
    agent = pred_checker_factory()
    with monkeypatch.context() as patch:
        patch.delattr(agent.dut, name)
        with pytest.raises(AttributeError):
            PredCheckerPorts(agent.dut)


@pytest.mark.parametrize('name,width', [('io_req_bits_instrPcVec_0_addr', 49),
    ('io_resp_stage2Out_checkerRedirect_bits_target_addr', 51)])
def test_changed_address_width_requires_a_real_migration(pred_checker_factory, monkeypatch, name, width):
    agent = pred_checker_factory()
    signal = getattr(agent.dut, name)

    class WrongWidth:
        mWidth = width

        def __getattr__(self, field):
            return getattr(signal, field)

    with monkeypatch.context() as patch:
        # Picker rejects replacing an existing XData attribute. This control
        # alters only the Python binding view, not any native signal metadata.
        patch.setitem(vars(agent.dut), name, WrongWidth())
        with pytest.raises(ValueError, match='native width 50'):
            PredCheckerPorts(agent.dut)


def test_wrong_direction_or_unowned_input_is_not_accepted(pred_checker_factory, monkeypatch):
    agent = pred_checker_factory()
    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), 'reset', agent.dut.io_resp_stage1Out_fixedInstrValid_0)
        with pytest.raises(ValueError, match='direction'):
            PredCheckerPorts(agent.dut)
    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), 'new_input', agent.dut.reset)
        with pytest.raises(ValueError, match='input ownership mismatch'):
            PredCheckerPorts(agent.dut)
    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), 'io_req_bits_instrVec_34_isCrossBlockInstr', agent.dut.reset)
        with pytest.raises(ValueError, match='proven pruned constant'):
            PredCheckerPorts(agent.dut)


async def test_second_writer_is_rejected_without_disturbing_the_agent(pred_checker):
    agent = pred_checker
    competitor = SyncSingleCycleDriver(agent.dut.clock, agent._ports.bits,
        idle=agent._ports.encode(Frame()), encoder=agent._ports.encode, name='competing-pred-writer')
    try:
        with pytest.raises((RuntimeError, ValueError), match='driver|owner|claim'):
            await competitor.send(Frame())
    finally:
        competitor.close()
    assert (await agent.cycle(fault())).redirect.target == 0x2040


async def test_every_valid_redirect_field_is_compared(pred_checker):
    from suites.frontend.ifu.model.pred_checker import Redirect, predict
    from suites.frontend.ifu.pred_checker.checker import check_prediction
    scene = fault()
    observed = await pred_checker.cycle(scene)
    expected = predict(scene)
    check_prediction(observed, expected, Redirect())
    for field in ('target', 'taken', 'invalid_taken', 'not_cfi_taken', 'is_rvc', 'block_sel',
                  'branch_type', 'ras_action', 'end_offset', 'is_cross_block'):
        bad_redirect = replace(observed.redirect,
            **{field: getattr(observed.redirect, field) ^ (2 if field == 'target' else 1)})
        with pytest.raises(AssertionError, match='redirect mismatch'):
            check_prediction(replace(observed, redirect=bad_redirect), expected, Redirect())


async def test_task_handoffs_do_not_pre_sample_an_unsupplied_slot(pred_checker):
    first = await pred_checker.cycle(fault())
    for _ in range(12):
        await asyncio.sleep(0)
    second = await pred_checker.cycle(fault(0x3000))
    assert second.previous_redirect == first.redirect
    assert second.redirect.target == 0x3040
    assert second.registered_tick == first.registered_tick + 2
    with pytest.raises(FrozenInstanceError):
        first.redirect.target = 0
    assert first.redirect.target == 0x2040  # Not a reference to the later native payload.


async def test_concurrent_cycles_cannot_misassociate_phase_samples(pred_checker):
    pending = asyncio.create_task(pred_checker.cycle(fault()))
    try:
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match='concurrent'):
            await pred_checker.cycle(fault(0x3000))
    finally:
        first = await pending
    assert first.redirect.target == 0x2040
    assert (await pred_checker.cycle(fault(0x3000))).redirect.target == 0x3040


@pytest.mark.parametrize('phase', ['_before', '_after'])
async def test_stopping_either_monitor_cannot_pass(pred_checker_factory, phase):
    agent = pred_checker_factory()
    with pytest.raises(MonitorClosedError):
        async with agent.running():
            await agent.reset()
            assert (await agent.cycle(fault())).redirect.valid == 1
            await getattr(agent, phase).aclose()
            await agent.cycle(fault(0x3000))


async def test_last_redirect_cannot_disappear_without_a_following_request(pred_checker_factory, monkeypatch):
    from suites.frontend.ifu.model.pred_checker import Redirect
    agent = pred_checker_factory()
    with pytest.raises(AssertionError, match='redirect valid'):
        async with agent.running():
            await agent.reset()
            assert (await agent.cycle(fault())).redirect.valid == 1
            monkeypatch.setattr(agent._after, 'capture', lambda _: Redirect())
            await agent.cycle(fault(0x3000))  # Fails here, not only at some later call.


async def test_corrupt_combinational_truncation_is_detected(pred_checker_factory, monkeypatch):
    agent = pred_checker_factory()
    with pytest.raises(AssertionError, match='fixed_instr_valid mismatch'):
        async with agent.running():
            await agent.reset()
            assert (await agent.cycle(fault())).fixed_instr_valid[:2] == (1, 0)
            capture = agent._before.capture
            monkeypatch.setattr(agent._before, 'capture',
                lambda event: replace(capture(event), fixed_instr_valid=(0,) * LANES))
            await agent.cycle(fault())


async def test_stale_previous_payload_cannot_stand_in_for_a_new_response(pred_checker_factory, monkeypatch):
    agent = pred_checker_factory()
    with pytest.raises(AssertionError, match='redirect mismatch'):
        async with agent.running():
            await agent.reset()
            old = await agent.cycle(fault())
            new = await agent.cycle(fault(0x3000))
            assert old.redirect.target != new.redirect.target
            monkeypatch.setattr(agent._after, 'capture', lambda _: old.redirect)
            await agent.cycle(fault(0x3000))


async def test_old_phase_tick_is_rejected_even_with_the_right_payload(pred_checker_factory, monkeypatch):
    agent = pred_checker_factory()
    with pytest.raises(AssertionError, match='stale or missing phase snapshot'):
        async with agent.running():
            await agent.reset()
            assert (await agent.cycle(fault())).redirect.valid == 1
            recv = agent._before.recv

            async def stale():
                transfer = await recv()
                return replace(transfer, event=replace(transfer.event, tick=transfer.event.tick - 2))

            monkeypatch.setattr(agent._before, 'recv', stale)
            await agent.cycle(fault())


async def test_finish_detects_a_repeated_final_redirect(pred_checker_factory, monkeypatch):
    agent = pred_checker_factory()
    with pytest.raises(AssertionError, match='redirect valid'):
        async with agent.running():
            await agent.reset()
            last = await agent.cycle(fault())
            monkeypatch.setattr(agent._after, 'capture', lambda _: last.redirect)
            # Context's finish must check the idle slots, not just close queues.


async def test_cancelled_input_cannot_be_reported_as_a_clean_finished_stream(pred_checker_factory):
    agent = pred_checker_factory()
    with pytest.raises(RuntimeError, match='unreconciled input slot'):
        async with agent.running():
            await agent.reset()
            pending = asyncio.create_task(agent.cycle(fault()))
            await asyncio.sleep(0)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            # Even if the caller swallowed cancellation, finish is not success.


async def test_swallowed_reset_failure_cannot_finish_cleanly(pred_checker_factory, monkeypatch):
    from suites.frontend.ifu.model.pred_checker import Redirect
    agent = pred_checker_factory()
    with pytest.raises(RuntimeError, match='unreconciled input slot'):
        async with agent.running():
            await agent.reset()  # Real legal reset remains a passing control.
            with monkeypatch.context() as patch:
                patch.setattr(agent._after, 'capture', lambda _: Redirect(valid=1))
                with pytest.raises(AssertionError, match='reset did not cancel'):
                    await agent.reset()
            # Restoring the monitor must not erase the failed reset obligation.


async def test_lifecycle_and_rejected_untyped_work_do_not_advance_slots(pred_checker_factory):
    agent = pred_checker_factory()
    with pytest.raises(RuntimeError, match='fixture-managed Execution'):
        await agent.cycle()
    async with agent.running():
        await agent.reset()
        first = await agent.cycle(fault())
        with pytest.raises(TypeError, match='semantic Request'):
            await agent.cycle({'valid': 1})
        second = await agent.cycle(fault())
        assert second.registered_tick == first.registered_tick + 2
        await agent.finish()
        await agent.finish()  # Idempotent, without inserting more unchecked slots.
        with pytest.raises(RuntimeError, match='finished'):
            await agent.cycle()
    with pytest.raises(RuntimeError, match='fixture-managed Execution'):
        await agent.cycle()
