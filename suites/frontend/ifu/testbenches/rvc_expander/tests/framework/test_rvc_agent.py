"""RVC adapter boundary controls. Python observation/expectation, never RTL, is mutated."""
import asyncio
from dataclasses import FrozenInstanceError, replace

import pytest
from toffee import MonitorClosedError, SyncSingleCycleDriver

from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi
from suites.frontend.ifu.testbenches.rvc_expander.model.rvc import Expansion
from suites.frontend.ifu.testbenches.rvc_expander.model.rvc import expand
from suites.frontend.ifu.testbenches.rvc_expander.checker import check_decoding
from suites.frontend.ifu.testbenches.rvc_expander.env.ports import RvcPorts
from suites.frontend.ifu.testbenches.rvc_expander.transactions import DecodeRequest
from suites.frontend.ifu.testbenches.rvc_expander.transactions import Decoded
from suites.frontend.ifu.testbenches.rvc_expander.transactions import IDLE

pytestmark = [pytest.mark.selftest, pytest.mark.feature('IFU-ENV-002')]


@pytest.mark.feature('IFU-ENV-004')
@pytest.mark.parametrize('word', [-1, 1 << 32, 3.0, '3'])
def test_word_domain_cannot_rely_on_native_truncation(word):
    with pytest.raises(ValueError, match='unsigned 32-bit'):
        DecodeRequest(word)


@pytest.mark.feature('IFU-ENV-004')
@pytest.mark.parametrize('fs', [-1, 2, 1.0, '0'])
def test_fs_control_requires_a_boolean_encoding(fs):
    with pytest.raises(ValueError, match='boolean'):
        DecodeRequest(3, fs)


def test_unknown_fields_and_mutating_a_request_are_rejected():
    with pytest.raises(TypeError):
        DecodeRequest(word=3, fs_off=1)
    request = DecodeRequest(3)
    with pytest.raises(FrozenInstanceError):
        request.word = 0
    with pytest.raises(ValueError, match='unsigned 32-bit'):
        Decoded(1 << 32, False)
    with pytest.raises(ValueError, match='boolean'):
        Decoded(0, 2)


@pytest.mark.parametrize('name', ['io_in', 'io_fsIsOff', 'io_out_bits', 'io_ill'])
def test_missing_ports_are_not_silent_defaults(rvc_expander_factory, monkeypatch, name):
    agent = rvc_expander_factory()
    with monkeypatch.context() as patch:
        patch.delattr(agent.dut, name)
        with pytest.raises(AttributeError):
            RvcPorts(agent.dut)


@pytest.mark.parametrize('name,width', [('io_in', 31), ('io_fsIsOff', 2),
                                      ('io_out_bits', 31), ('io_ill', 2)])
def test_changed_width_requires_an_explicit_migration(rvc_expander_factory, monkeypatch, name, width):
    agent = rvc_expander_factory()
    signal = getattr(agent.dut, name)

    class WrongWidth:
        mWidth = width

        def __getattr__(self, field):
            return getattr(signal, field)

    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), name, WrongWidth())
        with pytest.raises(ValueError, match='native width'):
            RvcPorts(agent.dut)


@pytest.mark.parametrize('name,replacement', [('io_in', 'io_out_bits'), ('io_ill', 'io_fsIsOff')])
def test_wrong_direction_is_a_binding_failure(rvc_expander_factory, monkeypatch, name, replacement):
    agent = rvc_expander_factory()
    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), name, getattr(agent.dut, replacement))
        with pytest.raises(ValueError, match='direction'):
            RvcPorts(agent.dut)


@pytest.mark.parametrize('name', ['new_input', 'clock', 'reset'])
def test_unowned_inputs_cannot_appear_without_a_contract_change(rvc_expander_factory, monkeypatch, name):
    agent = rvc_expander_factory()
    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), name, agent.dut.io_fsIsOff)
        with pytest.raises(ValueError, match='input ownership mismatch|no clock/reset'):
            RvcPorts(agent.dut)


async def test_competing_driver_is_rejected_without_corrupting_the_next_decode(rvc_expander):
    agent = rvc_expander
    competitor = SyncSingleCycleDriver(agent._clock, agent._ports.bits,
        idle=agent._ports.encode(IDLE), encoder=agent._ports.encode, name='competing-rvc-writer')
    try:
        with pytest.raises((RuntimeError, ValueError), match='driver|claim|owner'):
            await competitor.send(IDLE)
    finally:
        competitor.close()
    assert (await agent.decode(IDLE)).result == Decoded(0x13, False)


async def test_hint_override_cannot_hide_a_defined_wrong_instruction_word(rvc_expander):
    request = DecodeRequest(c_addi(10, 1))
    observed = (await rvc_expander.decode(request)).result
    expected = expand(request.word)
    check_decoding(request, observed, expected)
    with pytest.raises(AssertionError, match='bits mismatch'):
        check_decoding(request, observed, replace(expected, bits=expected.bits ^ 1, hint=True))


async def test_contractually_unspecified_bits_remain_legal_but_ill_is_always_checked(rvc_expander):
    for request in (DecodeRequest(c_addi(0, 5)), DecodeRequest(0)):
        observed = (await rvc_expander.decode(request)).result
        check_decoding(request, observed)
        check_decoding(request, replace(observed, bits=0xDEADBEEF))  # Legal unconstrained payload.
        with pytest.raises(AssertionError, match='ill mismatch'):
            check_decoding(request, replace(observed, ill=not observed.ill))


def test_expected_domain_and_missing_snapshot_are_not_coerced_to_valid_values():
    for expected in (Expansion(0x13, 2), Expansion(-1, False), Expansion(0x13, False, hint=2)):
        with pytest.raises(ValueError, match='encoding domain'):
            check_decoding(IDLE, Decoded(0x13, False), expected)
    with pytest.raises(TypeError, match='complete Decoded snapshot'):
        check_decoding(IDLE, None)


async def test_task_handoffs_preserve_slot_identity_and_snapshots(rvc_expander):
    first = await rvc_expander.decode(DecodeRequest(c_addi(10, 1)))
    for _ in range(12):
        await asyncio.sleep(0)
    second = await rvc_expander.decode(DecodeRequest(c_addi(11, 1)))
    assert second.sequence == first.sequence + 1 and second.sample_tick == first.sample_tick + 2
    assert first.result.bits != second.result.bits
    with pytest.raises(FrozenInstanceError):
        first.result.bits = second.result.bits
    assert first.result.bits == expand(c_addi(10, 1)).bits


async def test_concurrent_decodes_cannot_cross_associate_observations(rvc_expander):
    pending = asyncio.create_task(rvc_expander.decode(DecodeRequest(c_addi(10, 1))))
    try:
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match='concurrent'):
            await rvc_expander.decode(DecodeRequest(c_addi(11, 1)))
    finally:
        first = await pending
    assert first.result.bits == expand(c_addi(10, 1)).bits
    assert (await rvc_expander.decode(DecodeRequest(c_addi(11, 1)))).result.bits == expand(c_addi(11, 1)).bits


async def test_closed_monitor_cannot_report_a_passing_decode(rvc_expander_factory):
    agent = rvc_expander_factory()
    with pytest.raises(MonitorClosedError):
        async with agent.running():
            assert not (await agent.decode(IDLE)).result.ill
            await agent._monitor.aclose()
            await agent.decode(IDLE)


@pytest.mark.parametrize('field', ['bits', 'ill'])
async def test_corrupted_final_observation_fails_at_that_decode(rvc_expander_factory, monkeypatch, field):
    agent = rvc_expander_factory()
    with pytest.raises(AssertionError, match=f'{field} mismatch'):
        async with agent.running():
            request = DecodeRequest(c_addi(10, 1))
            assert not (await agent.decode(request)).result.ill
            capture = agent._monitor.capture

            def corrupt(event):
                observed = capture(event)
                return replace(observed, **{field: getattr(observed, field) ^ 1})

            monkeypatch.setattr(agent._monitor, 'capture', corrupt)
            await agent.decode(request)  # No subsequent request needed to notice the loss.


async def test_stale_tick_is_rejected_even_when_the_result_is_identical(rvc_expander_factory, monkeypatch):
    agent = rvc_expander_factory()
    with pytest.raises(AssertionError, match='stale or missing snapshot'):
        async with agent.running():
            await agent.decode(IDLE)
            recv = agent._monitor.recv

            async def stale():
                transfer = await recv()
                return replace(transfer, event=replace(transfer.event, tick=transfer.event.tick - 2))

            monkeypatch.setattr(agent._monitor, 'recv', stale)
            await agent.decode(IDLE)


async def test_stale_payload_cannot_replace_the_current_instruction(rvc_expander_factory, monkeypatch):
    agent = rvc_expander_factory()
    with pytest.raises(AssertionError, match='bits mismatch'):
        async with agent.running():
            old = await agent.decode(DecodeRequest(c_addi(10, 1)))
            new = await agent.decode(DecodeRequest(c_addi(11, 1)))
            assert old.result.bits != new.result.bits
            monkeypatch.setattr(agent._monitor, 'capture', lambda _: old.result)
            await agent.decode(DecodeRequest(c_addi(11, 1)))


async def test_a_missing_capture_is_not_a_passing_zero_result(rvc_expander_factory, monkeypatch):
    agent = rvc_expander_factory()
    with pytest.raises(TypeError, match='complete Decoded snapshot'):
        async with agent.running():
            await agent.decode(IDLE)
            monkeypatch.setattr(agent._monitor, 'capture', lambda _: None)
            await agent.decode(IDLE)


async def test_finish_checks_the_withdrawn_idle_frame(rvc_expander_factory, monkeypatch):
    agent = rvc_expander_factory()
    with pytest.raises(AssertionError, match='bits mismatch'):
        async with agent.running():
            old = await agent.decode(DecodeRequest(c_addi(10, 1)))
            monkeypatch.setattr(agent._monitor, 'capture', lambda _: old.result)
            # The context must evaluate/check NOP, not only discard the monitor.


async def test_cancelled_evaluation_cannot_finish_cleanly(rvc_expander_factory):
    agent = rvc_expander_factory()
    with pytest.raises(RuntimeError, match='unreconciled evaluation'):
        async with agent.running():
            await agent.decode(IDLE)
            pending = asyncio.create_task(agent.decode(DecodeRequest(c_addi(10, 1))))
            await asyncio.sleep(0)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending


async def test_swallowing_a_compare_failure_cannot_erase_it(rvc_expander_factory, monkeypatch):
    agent = rvc_expander_factory()
    with pytest.raises(RuntimeError, match='unreconciled evaluation'):
        async with agent.running():
            await agent.decode(IDLE)
            with monkeypatch.context() as patch:
                patch.setattr(agent._monitor, 'capture', lambda _: Decoded(0, False))
                with pytest.raises(AssertionError, match='bits mismatch'):
                    await agent.decode(IDLE)
            # The restored good monitor cannot make finish hide the failure.


async def test_bad_work_does_not_advance_and_finish_is_strict(rvc_expander_factory):
    agent = rvc_expander_factory()
    with pytest.raises(RuntimeError, match='fixture-managed Execution'):
        await agent.decode(IDLE)
    async with agent.running():
        first = await agent.decode(IDLE)
        with pytest.raises(TypeError, match='semantic DecodeRequest'):
            await agent.decode({'word': 3})
        with pytest.raises(TypeError, match='Expansion'):
            await agent.decode(IDLE, expected={'bits': 0x13})
        second = await agent.decode(IDLE)
        assert second.sample_tick == first.sample_tick + 2
        await agent.finish()
        await agent.finish()
        with pytest.raises(RuntimeError, match='finished'):
            await agent.decode(IDLE)
    with pytest.raises(RuntimeError, match='fixture-managed Execution'):
        await agent.decode(IDLE)
