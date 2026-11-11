"""PerfAnalysis framework/schema controls; not functional RTL mutations."""
from dataclasses import FrozenInstanceError
import asyncio

import pytest

from suites.frontend.ifu.testbenches.perf_analysis.model.perf import FTQ_BITS
from suites.frontend.ifu.testbenches.perf_analysis.model.perf import Inputs
from suites.frontend.ifu.testbenches.perf_analysis.env.ports import Frame
from suites.frontend.ifu.testbenches.perf_analysis.env.ports import PerfPorts

pytestmark = [pytest.mark.selftest, pytest.mark.feature("IFU-ENV-002")]


@pytest.mark.feature("IFU-ENV-004")
@pytest.mark.parametrize('field', ['icache_miss', 'itlb_miss', 'backend_redirect',
    'control_flow_redirect', 'memory_violation_redirect', 'tage_miss', 'ittage_miss',
    'ras_miss', 'ifu_wb_redirect'])
def test_reason_controls_reject_non_boolean_encodings(field):
    with pytest.raises(ValueError, match='must be a boolean'):
        Inputs(**{field: 2})


@pytest.mark.feature("IFU-ENV-004")
@pytest.mark.parametrize('bits', [-1, 1, 1 << 4, 1 << 75])
def test_ftq_reason_domain_cannot_silently_discard_unsupported_bits(bits):
    with pytest.raises(ValueError, match='unsupported or negative'):
        Inputs(ftq_bits=bits)


def test_semantic_request_is_frozen_and_unknown_fields_fail():
    inputs = Inputs(ftq_bits=1 << FTQ_BITS[0])
    with pytest.raises(FrozenInstanceError):
        inputs.ftq_bits = 0
    with pytest.raises(TypeError):
        Inputs(backed_redirect=1)


def test_missing_port_is_a_binding_failure_not_a_zero_observation():
    with pytest.raises(AttributeError):
        PerfPorts(object())


async def test_second_driver_cannot_claim_the_agent_inputs(perf_analysis):
    from toffee import SyncSingleCycleDriver
    agent = perf_analysis
    competitor = SyncSingleCycleDriver(agent.dut.clock, agent._ports.bits,
        idle=agent._ports.encode(Frame()), encoder=agent._ports.encode, name='competing-perf-writer')
    try:
        with pytest.raises((RuntimeError, ValueError), match='driver|owner|claim'):
            await competitor.send(Frame())
    finally:
        competitor.close()
    assert await agent.cycle() == 0


async def test_stopped_monitor_cannot_make_the_agent_pass(perf_analysis_factory):
    from toffee import MonitorClosedError
    agent = perf_analysis_factory()
    with pytest.raises(MonitorClosedError):
        async with agent.running():
            await agent.reset()
            await agent._monitor.aclose()
            await agent.cycle()


async def test_missing_last_reason_is_detected_by_finish(perf_analysis_factory, monkeypatch):
    agent = perf_analysis_factory()
    real_nonzero = []
    with pytest.raises(AssertionError, match='PerfAnalysis cycle'):
        async with agent.running():
            await agent.reset()
            await agent.cycle(Inputs(ftq_bits=1 << 2))
            capture = agent._monitor.capture

            def drop(event):
                observed = capture(event)
                if observed:
                    real_nonzero.append(observed)
                return 0

            monkeypatch.setattr(agent._monitor, 'capture', drop)
    assert real_nonzero == [1 << 2], 'control must reach the real final pipeline reason'


async def test_swallowed_comparison_cannot_become_a_clean_finish(perf_analysis_factory, monkeypatch):
    agent = perf_analysis_factory()
    with pytest.raises(RuntimeError, match='unreconciled input slot'):
        async with agent.running():
            await agent.reset()
            with monkeypatch.context() as patch:
                patch.setattr(agent._monitor, 'capture', lambda _: 1 << 2)
                with pytest.raises(AssertionError):
                    await agent.cycle()


async def test_explicit_slots_survive_suspending_the_pytest_producer(perf_analysis):
    await perf_analysis.cycle(Inputs(ftq_bits=1 << 2))
    for _ in range(12):
        await asyncio.sleep(0)
    # No imaginary idle clock slots were supplied by the caller; the original
    # three-stage reason must still appear at its independently expected slot.
    await perf_analysis.cycle()
    assert await perf_analysis.cycle() == 0
    assert await perf_analysis.cycle() == 1 << 2


@pytest.mark.parametrize('name', ['reset', 'io_topdownOut_topdown_reasons_75'])
def test_changed_port_width_or_direction_requires_migration(perf_analysis_factory, monkeypatch, name):
    agent = perf_analysis_factory()
    signal = getattr(agent.dut, name)

    class Wide:
        mWidth = 2

        def __getattr__(self, key):
            return getattr(signal, key)

    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), name, Wide())
        with pytest.raises(ValueError, match='native width'):
            PerfPorts(agent.dut)
    with monkeypatch.context() as patch:
        alias = agent.dut.io_topdownOut_topdown_reasons_2 if name == 'reset' else agent.dut.reset
        patch.setitem(vars(agent.dut), name, alias)
        with pytest.raises(ValueError, match='direction'):
            PerfPorts(agent.dut)


def test_unowned_input_cannot_appear_silently(perf_analysis_factory, monkeypatch):
    agent = perf_analysis_factory()
    monkeypatch.setitem(vars(agent.dut), 'new_reason', agent.dut.reset)
    with pytest.raises(ValueError, match='input ownership'):
        PerfPorts(agent.dut)


def test_frame_schema_has_no_implicit_conversion_or_unknown_keys():
    with pytest.raises(TypeError):
        Frame(inputs={})
    for value in (2, -1, '1', 1.0):
        with pytest.raises(ValueError, match='boolean'):
            Frame(reset=value)
    with pytest.raises(TypeError):
        Frame(resett=True)


async def test_cancelled_input_slot_remains_unreconciled(perf_analysis_factory):
    agent = perf_analysis_factory()
    with pytest.raises(RuntimeError, match='unreconciled input slot'):
        async with agent.running():
            await agent.reset()
            task = asyncio.create_task(agent.cycle(Inputs(ftq_bits=1 << 2)))
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


async def test_swallowed_reset_compare_failure_remains_unreconciled(perf_analysis_factory, monkeypatch):
    agent = perf_analysis_factory()
    with pytest.raises(RuntimeError, match='unreconciled input slot'):
        async with agent.running():
            await agent.reset()
            with monkeypatch.context() as patch:
                patch.setattr(agent._monitor, 'capture', lambda _: 1 << 2)
                with pytest.raises(AssertionError, match='PerfAnalysis reset'):
                    await agent.reset()


async def test_old_tick_is_not_accepted_just_because_payload_is_equal(perf_analysis_factory, monkeypatch):
    from dataclasses import replace
    agent = perf_analysis_factory()
    with pytest.raises(AssertionError, match='stale or missing'):
        async with agent.running():
            await agent.reset()
            recv = agent._monitor.recv

            async def stale():
                observed = await recv()
                return replace(observed, event=replace(observed.event, tick=observed.event.tick - 2))

            monkeypatch.setattr(agent._monitor, 'recv', stale)
            await agent.cycle()


async def test_concurrent_reset_cannot_interleave_with_a_cycle(perf_analysis):
    task = asyncio.create_task(perf_analysis.cycle())
    try:
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match='concurrent'):
            await perf_analysis.reset()
    finally:
        await task


async def test_bad_budget_does_not_advance_and_finished_agent_cannot_restart(perf_analysis_factory):
    agent = perf_analysis_factory()
    with pytest.raises(RuntimeError, match='fixture-managed'):
        await agent.cycle()
    async with agent.running():
        await agent.reset()
        before = agent._last_tick
        for budget in (0, -1, 1.5):
            with pytest.raises(ValueError, match='positive cycle budget'):
                await agent.reset(budget)
        with pytest.raises(TypeError):
            await agent.cycle({})
        await agent.cycle()
        assert agent._last_tick == before + 2
        await agent.finish()
        await agent.finish()
        with pytest.raises(RuntimeError, match='finished'):
            await agent.cycle()
    with pytest.raises(RuntimeError, match='cannot be restarted'):
        async with agent.running():
            pass


@pytest.mark.parametrize('value', [None, 0.0, -1, 1 << 76])
def test_reason_checker_requires_complete_integer_snapshots(value):
    from suites.frontend.ifu.testbenches.perf_analysis.checker import check_reasons
    check_reasons(0, 0)
    with pytest.raises(TypeError, match='observation'):
        check_reasons(value, 0)
    with pytest.raises(TypeError, match='expectation'):
        check_reasons(0, value)
