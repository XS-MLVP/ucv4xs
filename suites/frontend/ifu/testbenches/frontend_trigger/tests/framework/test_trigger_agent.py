"""Strict schema, phase identity and lifecycle controls; not RTL mutation tests."""
import asyncio
from dataclasses import FrozenInstanceError, replace

import pytest
from toffee import MonitorClosedError, SyncSingleCycleDriver

from suites.frontend.ifu.testbenches.frontend_trigger.checker import check_actions
from suites.frontend.ifu.testbenches.frontend_trigger.env.ports import TriggerPorts
from suites.frontend.ifu.testbenches.frontend_trigger.transactions import Actions
from suites.frontend.ifu.testbenches.frontend_trigger.transactions import Frame
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import ACTION_BREAKPOINT
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import ACTION_DEBUG
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import ACTION_NONE
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import Inputs
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import LANES
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import Trigger
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import TriggerModel
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import Update
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import compare
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import consecutive_pcs

pytestmark = [pytest.mark.selftest, pytest.mark.feature('IFU-ENV-002')]


def configured(*, index=0, **fields):
    pcs = consecutive_pcs(0x4000)
    trigger = Trigger(action=ACTION_DEBUG, tdata2=pcs[4])
    return Inputs(Update(1, index, replace(trigger, **fields)), (1, 1, 1, 1), pcs=pcs)


@pytest.mark.feature('IFU-ENV-004')
@pytest.mark.parametrize('field,value', [
    ('match_type', -1), ('match_type', 4), ('match_type', 1.0),
    ('action', -1), ('action', 16), ('tdata2', -1), ('tdata2', 1 << 64),
    ('select', 2), ('chain', -1), ('timing', 1), ('timing', 1.0),
])
def test_trigger_values_are_validated_without_native_coercion(field, value):
    with pytest.raises(ValueError):
        Trigger(**{field: value})


@pytest.mark.parametrize('updates,error', [
    ({'valid': 2}, ValueError), ({'index': -1}, ValueError), ({'index': 4}, ValueError),
    ({'index': 1.0}, ValueError), ({'valid': 1}, ValueError), ({'trigger': {}}, TypeError),
])
def test_configuration_update_requires_a_real_index_and_payload(updates, error):
    with pytest.raises(error):
        Update(**updates)


@pytest.mark.parametrize('updates', [
    {'enable': ()}, {'enable': (0,) * 3}, {'enable': (0,) * 5}, {'enable': (2, 0, 0, 0)},
    {'debug_mode': 2}, {'can_raise_breakpoint': 1.0},
    {'pcs': ()}, {'pcs': (0,) * 35}, {'pcs': (0,) * 37},
    {'pcs': (1,) + (0,) * 35}, {'pcs': (1 << 50,) + (0,) * 35}, {'pcs': ('0',) * 36},
])
def test_live_controls_and_complete_pc_vector_have_strict_domains(updates):
    with pytest.raises(ValueError):
        Inputs(**updates)


def test_unknown_keys_and_mutable_input_aliases_cannot_bypass_the_boundary():
    pcs, enable = list(consecutive_pcs(0x4000)), [1, 0, 0, 0]
    inputs = Inputs(enable=enable, pcs=pcs)
    pcs[0], enable[0] = 0, 0
    assert inputs.pcs[0] == 0x4000 and inputs.enable[0] == 1
    for value, field, altered in ((inputs, 'pcs', ()), (Update(), 'index', 3), (Trigger(), 'action', 0)):
        with pytest.raises(FrozenInstanceError):
            setattr(value, field, altered)
    with pytest.raises(TypeError):
        Inputs(enables=(0, 0, 0, 0))
    with pytest.raises(TypeError):
        Inputs(update={})
    with pytest.raises(ValueError):
        Frame(reset=2)
    with pytest.raises(TypeError):
        Frame(inputs={})


def test_pc_window_overflow_and_alignment_are_not_masked():
    for base in (-1, 1, 1 << 50, (1 << 50) - 2):
        with pytest.raises(ValueError):
            consecutive_pcs(base)
    high = consecutive_pcs((1 << 50) - 2 * LANES)
    assert high[-1] == (1 << 50) - 2


def test_width_and_units_do_not_truncate_tdata2_or_shift_the_semantic_pc():
    inputs = configured(tdata2=(1 << 64) - 1)
    encoded = TriggerPorts.encode(Frame(inputs))
    assert encoded['tdata2'] == (1 << 64) - 1
    assert encoded['pcs'][0] == inputs.pcs[0] >> 1
    assert inputs.pcs[0] == 0x4000


@pytest.mark.parametrize('values', [(), (0,) * 35, (16,) * 36, (1.0,) * 36])
def test_incomplete_or_invalid_action_snapshots_are_rejected(values):
    with pytest.raises(ValueError):
        Actions(values)


@pytest.mark.parametrize('name', ['reset', 'io_pc_35_addr', 'io_frontendTrigger_tUpdate_bits_tdata_tdata2',
                                 'io_triggered_35'])
def test_required_ports_are_not_defaulted(frontend_trigger_factory, monkeypatch, name):
    agent = frontend_trigger_factory()
    with monkeypatch.context() as patch:
        patch.delattr(agent.dut, name)
        with pytest.raises(AttributeError):
            TriggerPorts(agent.dut)


@pytest.mark.parametrize('name,width', [('io_pc_0_addr', 50), ('io_triggered_0', 3),
    ('io_frontendTrigger_tUpdate_bits_tdata_tdata2', 50), ('clock', 2)])
def test_changed_native_width_is_a_migration_error(frontend_trigger_factory, monkeypatch, name, width):
    agent = frontend_trigger_factory()
    signal = getattr(agent.dut, name)

    class WrongWidth:
        mWidth = width

        def __getattr__(self, field):
            return getattr(signal, field)

    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), name, WrongWidth())
        with pytest.raises(ValueError, match='native width'):
            TriggerPorts(agent.dut)


@pytest.mark.parametrize('name,alias', [('reset', 'io_frontendTrigger_debugMode'),
                                      ('io_triggered_0', 'io_frontendTrigger_tUpdate_bits_tdata_action')])
def test_direction_and_unowned_inputs_are_not_hidden(frontend_trigger_factory, monkeypatch, name, alias):
    agent = frontend_trigger_factory()
    with monkeypatch.context() as patch:
        if name == 'reset':
            # Alias a same-width output using a wrapper, so direction is tested.
            class Output:
                mWidth = 0

                def IsInIO(self):
                    return False

                def IsOutIO(self):
                    return True
            replacement = Output()
        else:
            replacement = getattr(agent.dut, alias)
        patch.setitem(vars(agent.dut), name, replacement)
        with pytest.raises(ValueError, match='direction'):
            TriggerPorts(agent.dut)
    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), 'new_timing_input', agent.dut.io_frontendTrigger_debugMode)
        with pytest.raises(ValueError, match='input ownership mismatch'):
            TriggerPorts(agent.dut)


@pytest.mark.parametrize('index,fields', [(0, {'match_type': 1}), (0, {'select': 1}),
                                        (0, {'action': 2}), (0, {'action': 15})])
async def test_csr_domain_rejects_reserved_values_but_port_characterization_remains_explicit(frontend_trigger, index, fields):
    agent = frontend_trigger
    before = agent.checked_cycles
    inputs = configured(index=index, **fields)
    with pytest.raises(ValueError, match='CSR producer'):
        await agent.cycle(inputs)
    assert agent.checked_cycles == before
    await agent.characterize_cycle(inputs)
    assert agent.checked_cycles == before + 1  # Actual port evaluation, not just admission.
    with pytest.raises(ValueError, match='CSR producer'):
        await agent.cycle(replace(inputs, update=Update()))
    await agent.reset()  # Genuine reset, not an artificial shadow-table rewind.
    await agent.cycle(configured())


async def test_adjacent_chain_history_cannot_masquerade_as_a_legal_csr_sequence(frontend_trigger):
    await frontend_trigger.cycle(configured(chain=1))
    before = frontend_trigger.checked_cycles
    with pytest.raises(ValueError, match='adjacent chain bits'):
        await frontend_trigger.cycle(configured(index=1, chain=1))
    assert frontend_trigger.checked_cycles == before
    await frontend_trigger.characterize_cycle(configured(index=1, chain=1))
    await frontend_trigger.reset()
    await frontend_trigger.cycle(configured(index=1))


async def test_competing_driver_fails_without_corrupting_the_owner(frontend_trigger):
    agent = frontend_trigger
    competitor = SyncSingleCycleDriver(agent.dut.clock, agent._ports.bits,
        idle=agent._ports.encode(Frame()), encoder=agent._ports.encode, name='competing-trigger-writer')
    try:
        with pytest.raises((RuntimeError, ValueError), match='driver|owner|claim'):
            await competitor.send(Frame())
    finally:
        competitor.close()
    assert (await agent.cycle(configured())).after.actions[4] == ACTION_DEBUG


async def test_both_phase_comparisons_check_every_lane(frontend_trigger):
    observed = await frontend_trigger.cycle(configured())
    for phase in ('before', 'after'):
        snapshot = getattr(observed, phase)
        check_actions(snapshot, snapshot.actions, phase='legal-control')
        for lane in range(LANES):
            wrong = list(snapshot.actions)
            wrong[lane] ^= 1
            with pytest.raises(AssertionError, match='frontend_trigger'):
                check_actions(replace(snapshot, actions=wrong), snapshot.actions, phase=phase)
    with pytest.raises(TypeError, match='complete Actions'):
        check_actions(None, (ACTION_NONE,) * LANES, phase='missing')
    with pytest.raises(ValueError):
        check_actions(observed.before, (), phase='short-expected')


def test_old_none_action_reset_oracle_is_rejected_by_a_fixed_zero_reset_answer():
    model = TriggerModel()
    inputs = Inputs(enable=(1, 0, 0, 0))
    model.tick(inputs)
    correct = (ACTION_BREAKPOINT,) + (ACTION_NONE,) * (LANES - 1)
    check_actions(Actions(model.lane_actions(inputs)), correct, phase='reset-contract')
    model.triggers[0] = Trigger()  # Frozen old mistake: reset action=None, not0.
    with pytest.raises(AssertionError):
        check_actions(Actions(model.lane_actions(inputs)), correct, phase='wrong-reset-model')


def test_truncated_tdata2_oracle_cannot_accept_the_architecturally_wrong_hit():
    pc, high_target = 0x4008, (1 << 50) | 0x4008
    assert not compare(pc, high_target, 0)
    assert compare(pc, high_target & ((1 << 50) - 1), 0)  # Wrong historical truncation.
    legal = Actions((ACTION_NONE,) * LANES)
    check_actions(legal, legal.actions, phase='full-width-control')
    wrong = replace(legal, actions=(ACTION_DEBUG,) + legal.actions[1:])
    with pytest.raises(AssertionError):
        check_actions(wrong, legal.actions, phase='wrong-truncated-oracle')


async def test_task_handoffs_preserve_phase_identity_and_frozen_observations(frontend_trigger):
    first = await frontend_trigger.cycle(configured())
    for _ in range(12):
        await asyncio.sleep(0)
    second = await frontend_trigger.cycle(replace(configured(), update=Update(), debug_mode=1))
    assert second.sequence == first.sequence + 1 and second.after_tick == first.after_tick + 2
    assert second.before_tick + 1 == second.after_tick
    assert first.after.actions[4] == ACTION_DEBUG and second.before.actions[4] == ACTION_NONE
    with pytest.raises(FrozenInstanceError):
        first.after.actions = second.before.actions


async def test_concurrent_cycles_cannot_cross_associate_inputs(frontend_trigger):
    pending = asyncio.create_task(frontend_trigger.cycle(configured()))
    try:
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match='concurrent'):
            await frontend_trigger.cycle(Inputs())
    finally:
        await pending


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_closed_phase_monitor_cannot_pass(frontend_trigger_factory, phase):
    agent = frontend_trigger_factory()
    with pytest.raises(MonitorClosedError):
        async with agent.running():
            await agent.reset()
            await getattr(agent, '_' + phase).aclose()
            await agent.cycle(configured())


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_stale_phase_tick_is_rejected_even_for_an_identical_action(frontend_trigger_factory, monkeypatch, phase):
    agent = frontend_trigger_factory()
    with pytest.raises(AssertionError, match='stale or missing phase snapshot'):
        async with agent.running():
            await agent.reset()
            monitor = getattr(agent, '_' + phase)
            recv = monitor.recv

            async def stale():
                observed = await recv()
                return replace(observed, event=replace(observed.event, tick=observed.event.tick - 2))

            monkeypatch.setattr(monitor, 'recv', stale)
            await agent.cycle(Inputs())


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_missing_phase_payload_is_not_a_passing_empty_action(frontend_trigger_factory, monkeypatch, phase):
    agent = frontend_trigger_factory()
    with pytest.raises(TypeError, match='complete Actions'):
        async with agent.running():
            await agent.reset()
            monkeypatch.setattr(getattr(agent, '_' + phase), 'capture', lambda _: None)
            await agent.cycle(Inputs())


@pytest.mark.parametrize('phase', ['before', 'after'])
async def test_stale_payload_cannot_replace_the_current_pc_comparison(frontend_trigger_factory, monkeypatch, phase):
    agent = frontend_trigger_factory()
    with pytest.raises(AssertionError, match='frontend_trigger'):
        async with agent.running():
            await agent.reset()
            first = await agent.cycle(configured())
            first = await agent.cycle(replace(configured(), update=Update()))
            old = getattr(first, phase)
            monkeypatch.setattr(getattr(agent, '_' + phase), 'capture', lambda _: old)
            await agent.cycle(replace(configured(), update=Update(), debug_mode=1))


async def test_finish_checks_final_configuration_and_then_disabled_quiet(frontend_trigger_factory, monkeypatch):
    agent = frontend_trigger_factory()
    with pytest.raises(AssertionError, match='frontend_trigger.before'):
        async with agent.running():
            await agent.reset()
            before = (await agent.cycle(configured())).before
            monkeypatch.setattr(agent._before, 'capture', lambda _: before)


async def test_reset_error_is_sticky_even_after_the_monitor_is_restored(frontend_trigger_factory, monkeypatch):
    agent = frontend_trigger_factory()
    with pytest.raises(RuntimeError, match='unreconciled input slot'):
        async with agent.running():
            await agent.reset()
            with monkeypatch.context() as patch:
                patch.setattr(agent._after, 'capture', lambda _: Actions((ACTION_DEBUG,) * LANES))
                with pytest.raises(AssertionError, match='frontend_trigger.reset'):
                    await agent.reset()


async def test_cancelled_cycle_cannot_be_swallowed_then_finished(frontend_trigger_factory):
    agent = frontend_trigger_factory()
    with pytest.raises(RuntimeError, match='unreconciled input slot'):
        async with agent.running():
            await agent.reset()
            pending = asyncio.create_task(agent.cycle(configured()))
            await asyncio.sleep(0)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending


async def test_restoring_capture_after_swallowed_failure_does_not_erase_the_slot(frontend_trigger_factory, monkeypatch):
    agent = frontend_trigger_factory()
    with pytest.raises(RuntimeError, match='unreconciled input slot'):
        async with agent.running():
            await agent.reset()
            with monkeypatch.context() as patch:
                patch.setattr(agent._after, 'capture', lambda _: Actions((ACTION_DEBUG,) * LANES))
                with pytest.raises(AssertionError):
                    await agent.cycle(Inputs())


async def test_rejected_work_and_reset_budgets_do_not_advance_the_clock(frontend_trigger):
    first = await frontend_trigger.cycle(Inputs())
    for budget in (0, -1, 1.5):
        with pytest.raises(ValueError, match='positive cycle budget'):
            await frontend_trigger.reset(budget)
    with pytest.raises(TypeError, match='semantic Inputs'):
        await frontend_trigger.cycle({})
    second = await frontend_trigger.cycle(Inputs())
    assert second.after_tick == first.after_tick + 2


async def test_lifecycle_cannot_submit_before_start_or_restart_after_finish(frontend_trigger_factory):
    agent = frontend_trigger_factory()
    with pytest.raises(RuntimeError, match='fixture-managed Execution'):
        await agent.cycle(Inputs())
    async with agent.running():
        await agent.reset()
        await agent.cycle(Inputs())
        await agent.finish()
        await agent.finish()
        with pytest.raises(RuntimeError, match='finished'):
            await agent.cycle(Inputs())
    with pytest.raises(RuntimeError, match='cannot be restarted'):
        async with agent.running():
            pass
