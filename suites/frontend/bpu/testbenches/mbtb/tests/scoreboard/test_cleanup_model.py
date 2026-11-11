"""Hand-derived cleanup expectations and agent-owned phase controls."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from suites.frontend.bpu.testbenches.mbtb.env.agent.main import MbtbAgent
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbEntry
from suites.frontend.bpu.testbenches.mbtb.model.cleanup import expected_mbtb_cleanup_states
from suites.frontend.bpu.testbenches.mbtb.model.cleanup import expected_mbtb_cleanup_dual
from suites.frontend.bpu.testbenches.mbtb.model.cleanup import cleanup_way_plan
from suites.frontend.bpu.testbenches.mbtb.model.cleanup import observed_mbtb_cleanup_dual
from suites.frontend.bpu.testbenches.bpu.model.configuration import MAIN_WAYS
from suites.frontend.bpu.testbenches.bpu.model.configuration import MAIN_RETAINED
from suites.frontend.bpu.testbenches.mbtb.env.monitor.entry import ENTRY_FIELDS
from suites.frontend.bpu.testbenches.mbtb.model.vectors import BranchVector
from suites.frontend.bpu.testbenches.mbtb.checker.lookup_inputs import LookupInputs


def stub_planned_training(agent):
    """Phase-only selftests replace the validated input service, not live IO."""
    async def issue(transactions,*,encoded=None):
        await agent.training_driver.send(encoded[0] if encoded is not None else agent._encode_training(transactions[0]))
        return ()
    agent._issue_training=issue
    agent._mark_training_drained=lambda inputs:None


def profiles(align):
    entries = tuple(MbtbEntry(0, 0, 0x40000000, index // 5 * 16, 0, 0) for index in range(10))
    metadata = [[dict(rawHit=0, position=bank * 16, counter_value=0,
        attribute=dict(branchType=0, rasAction=0)) for _ in range(5)] for bank in range(2)]
    for way in range(2):
        metadata[align][way].update(rawHit=1, position=5 + align * 16, counter_value=2,
            attribute=dict(branchType=3, rasAction=0))
    entries = tuple(replace(entry, valid=1, taken=1, target=0x40002740 - (index % 5) * 0x400,
                            position=5 + align * 16, branch_type=3) if index // 5 == align and index % 5 < 2 else entry
                    for index, entry in enumerate(entries))
    duplicate = dict(entries=entries, meta_entries=metadata)
    neighbor = deepcopy(duplicate)
    neighbor['entries'] = tuple(replace(entry, target=0x40003360 + (index % 5) * 0x200,
        position=6 + align * 16 - index % 5) if index // 5 == align and index % 5 < 2 else entry
        for index, entry in enumerate(entries))
    for way in range(2):
        neighbor['meta_entries'][align][way]['position'] = 6 + align * 16 - way
    return duplicate, neighbor


@pytest.mark.parametrize('align', (0, 1))
@pytest.mark.parametrize('way', (0, 1))
def test_cleanup_preserves_counters_and_neighbor_profiles_without_mutation(align, way):
    duplicate, neighbor = profiles(align)
    before = deepcopy((duplicate, neighbor))
    cleaned, updated = expected_mbtb_cleanup_states(duplicate, neighbor, 0x40000820, align, 0, 1, way, 0x40005560)
    assert (duplicate, neighbor) == before
    assert cleaned['entries'][align * 5] == duplicate['entries'][align * 5]
    cleared = cleaned['entries'][align * 5 + 1]
    assert (cleared.valid, cleared.taken, cleared.target, cleared.position, cleared.branch_type, cleared.ras_action) == (
        0, 1, 0x40000000, align * 16, 0, 0)
    assert [item['counter_value'] for item in cleaned['meta_entries'][align]] == [2, 2, 0, 0, 0]
    assert cleaned['meta_entries'][align][1]['attribute'] == dict(branchType=0, rasAction=0)
    assert updated['entries'][align * 5 + way].target == 0x40005560
    assert updated['entries'][align * 5 + 1 - way] == neighbor['entries'][align * 5 + 1 - way]
    assert updated['meta_entries'] == neighbor['meta_entries']
    cleaned['meta_entries'][align][0]['counter_value'] = 0
    assert (duplicate, neighbor) == before


@pytest.mark.parametrize('kind', ('missing', 'position', 'type', 'saturated', 'neighbor'))
def test_cleanup_reference_rejects_unsupported_preconditions(kind):
    duplicate, neighbor = profiles(0)
    if kind in ('missing', 'position', 'type'):
        field, value = {'missing': ('valid', 0), 'position': ('position', 6), 'type': ('branch_type', 1)}[kind]
        duplicate['entries'] = (replace(duplicate['entries'][0], **{field: value}), *duplicate['entries'][1:])
    elif kind == 'saturated':
        duplicate['meta_entries'][0][0]['counter_value'] = 3
    else:
        neighbor['meta_entries'][0][0]['counter_value'] = 1
    with pytest.raises(ValueError):
        expected_mbtb_cleanup_states(duplicate, neighbor, 0x40000820, 0, 0, 1, 0, 0x40005560)


@pytest.mark.parametrize('depth', (0, 1))
@pytest.mark.parametrize('shadow_state', ('dirty', 'clean'))
def test_native_reference_distinguishes_both_depths_and_clear_dirtiness(depth, shadow_state):
    first = BranchVector(0x40000820, 0x40002340, 5, 3)
    changed = replace(first, target=0x40002740)
    extra = replace(first, pc=0x40000860, target=0x40003560, position=6)
    updated = replace(extra, target=0x40003D60)
    wanted = expected_mbtb_cleanup_dual(first, changed, extra, updated, depth, shadow_state)
    plan = cleanup_way_plan()
    update, clear = plan['extra'], plan['clear']
    assert (update, clear) == (2, 3)
    assert len(wanted['ports']) == len(wanted['before']) == len(wanted['after']) == MAIN_WAYS
    assert all(len(row) == MAIN_RETAINED for row in wanted['before'])
    assert wanted['before'][clear][0]['dirty'] == int(shadow_state == 'dirty')
    assert wanted['ports'][clear]['read_valid'] == int(shadow_state == 'dirty')
    assert wanted['ports'][clear]['write_tag'] == wanted['ports'][clear]['write_position'] == 0
    assert wanted['ports'][update]['write_lower'] == 0x3D60
    assert wanted['after'][update][depth]['lower'] == 0x3D60
    assert wanted['after'][update][depth]['dirty'] == 1
    assert wanted['after'][clear] == wanted['before'][clear]
    assert not any(port['write_valid'] for port in wanted['ports'][:2])


@pytest.mark.parametrize('shadow_state', ('dirty', 'clean'))
async def test_agent_owns_cleanup_phase_sequence(monkeypatch, shadow_state):
    log = []
    agent = object.__new__(MbtbAgent)
    agent._started = True
    agent._finished = False
    agent._multi_hit_cleanup_scope_active = agent._defer_multi_hit_cleanup = True
    agent.dut = SimpleNamespace(clock='clock')
    agent.lookup_driver = SimpleNamespace(quiesce=lambda: None)
    agent.consume_driver = SimpleNamespace(quiesce=lambda: None)
    agent.consume_driver = SimpleNamespace(quiesce=lambda: log.append(('s2', not agent._defer_multi_hit_cleanup)))
    agent._encode_training = lambda tx: dict(payload=tx)
    async def send(tx):
        log.append(('train', tx))
    async def cycles(clock, count):
        assert clock == 'clock'
        log.append(('cycles', count))
    agent.training_driver = SimpleNamespace(send=send)
    stub_planned_training(agent)
    async def idle(*groups):
        assert groups == ('pipeline', 'writes')
        log.append(('idle', agent._defer_multi_hit_cleanup))
    agent.training_activity = SimpleNamespace(wait_idle=idle)
    monkeypatch.setattr('suites.frontend.bpu.testbenches.mbtb.env.agent.main.ClockCycles', cycles)
    await agent.train_during_multi_hit_cleanup('feedback', shadow_state=shadow_state)
    expected = [('s2', True), ('cycles', 1), ('s2', False), ('idle', True)] if shadow_state == 'clean' else []
    assert log == expected + [('s2', True), ('train', dict(payload='feedback')),
                              ('s2', False), ('idle', True), ('s2', True)]
    assert agent._multi_hit_cleanup_scope_active and not agent._defer_multi_hit_cleanup


@pytest.mark.parametrize('condition', ('inactive', 'resumed', 'state', 'feedback'))
async def test_agent_rejects_invalid_cleanup_before_driving(condition):
    agent = object.__new__(MbtbAgent)
    agent._started = True
    agent._finished = False
    agent._multi_hit_cleanup_scope_active = condition != 'inactive'
    agent._defer_multi_hit_cleanup = condition != 'resumed'
    def encode(_tx):
        raise ValueError('invalid feedback')
    agent._encode_training = encode
    with pytest.raises((RuntimeError, ValueError)):
        await agent.train_during_multi_hit_cleanup('feedback', shadow_state='bad' if condition == 'state' else 'clean')
    assert agent._defer_multi_hit_cleanup == (condition != 'resumed')


async def test_cleanup_scope_cannot_be_nested_after_resume(monkeypatch):
    agent = object.__new__(MbtbAgent)
    agent.lookup_inputs=LookupInputs()
    agent._started = True
    agent._finished = False
    agent._multi_hit_cleanup_scope_active = agent._defer_multi_hit_cleanup = False
    agent.dut = SimpleNamespace(clock='clock')
    agent.lookup_driver = SimpleNamespace(quiesce=lambda: None)
    agent.consume_driver = SimpleNamespace(quiesce=lambda: None)
    async def cycles(_clock, _count):
        pass
    monkeypatch.setattr('suites.frontend.bpu.testbenches.mbtb.env.agent.main.ClockCycles', cycles)
    async def idle(*_groups):
        pass
    agent.training_activity = SimpleNamespace(wait_idle=idle)
    async with agent.defer_multi_hit_cleanup():
        agent._defer_multi_hit_cleanup = False
        with pytest.raises(RuntimeError, match='already deferred'):
            async with agent.defer_multi_hit_cleanup():
                raise AssertionError('nested scope was admitted')
    assert not agent._multi_hit_cleanup_scope_active and not agent._defer_multi_hit_cleanup


async def test_failed_clean_pulse_restores_deferred_gate(monkeypatch):
    agent = object.__new__(MbtbAgent)
    agent._started = True
    agent._finished = False
    agent._multi_hit_cleanup_scope_active = agent._defer_multi_hit_cleanup = True
    agent.dut = SimpleNamespace(clock='clock')
    agent.lookup_driver = SimpleNamespace(quiesce=lambda: None)
    agent.consume_driver = SimpleNamespace(quiesce=lambda: None)
    agent._encode_training = lambda value: value
    async def cycles(_clock, _count):
        raise RuntimeError('interrupted pulse')
    monkeypatch.setattr('suites.frontend.bpu.testbenches.mbtb.env.agent.main.ClockCycles', cycles)
    with pytest.raises(RuntimeError, match='interrupted pulse'):
        await agent.train_during_multi_hit_cleanup('feedback', shadow_state='clean')
    assert agent._multi_hit_cleanup_scope_active and agent._defer_multi_hit_cleanup


def test_reset_lru_plan_is_four_way_and_independent_of_observed_metadata():
    assert cleanup_way_plan() == dict(original=3, displacer=3, changed=2, extra=2, keep=2, clear=3)


@pytest.mark.parametrize('active', ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3), (0, 2, 3)))
@pytest.mark.parametrize('foreign', (False, True))
def test_partial_way_collision_preserves_every_active_port_and_foreign_write(active, foreign):
    def port(enabled):
        fields = {direction + '_' + name: 0 for name, _ in ENTRY_FIELDS for direction in ('write', 'read')}
        return fields | dict(write_valid=int(enabled), read_valid=0, read_ready=1)
    banks = tuple(tuple(tuple(port(way in active if (align, bank) == (0, 0)
        else foreign and (align, bank, way) == (1, 2, 3)) for way in range(MAIN_WAYS))
        for bank in range(4)) for align in range(2))
    frame = SimpleNamespace(event=SimpleNamespace(tick=10), value={'banks': banks})
    found = observed_mbtb_cleanup_dual((frame,), (), 0, 0)
    assert len(found) == 1
    value = found[0]['value']
    assert len(value['ports']) == MAIN_WAYS
    assert [index for index, payload in enumerate(value['ports']) if payload['write_valid']] == list(active)
    assert value['foreign_writes'] == ([(1, 2, 3)] if foreign else [])
    assert all(('write_tag' in payload) == bool(payload['write_valid']) for payload in value['ports'])
