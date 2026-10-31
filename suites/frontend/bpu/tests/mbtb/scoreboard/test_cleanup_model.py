"""Hand-derived cleanup expectations and agent-owned phase controls."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from suites.frontend.bpu.mbtb.agent.main import MbtbAgent
from suites.frontend.bpu.mbtb.transaction.types import MbtbEntry
from suites.frontend.bpu.mbtb.model.cleanup import expected_mbtb_cleanup_states
from suites.frontend.bpu.mbtb.model.cleanup import expected_mbtb_cleanup_dual
from suites.frontend.bpu.mbtb.case.definitions import BranchVector


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
    cleaned, updated = expected_mbtb_cleanup_states(duplicate, neighbor, 0x40000820, align, way, 0x40005560)
    assert (duplicate, neighbor) == before
    assert cleaned['entries'][align * 5] == duplicate['entries'][align * 5]
    cleared = cleaned['entries'][align * 5 + 1]
    assert (cleared.valid, cleared.taken, cleared.target, cleared.position, cleared.branch_type, cleared.ras_action) == (
        0, 1, 0x40000000, align * 16, 0, 0)
    assert [item['counter_value'] for item in cleaned['meta_entries'][align]] == [2, 2, 0, 0, 0]
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
        expected_mbtb_cleanup_states(duplicate, neighbor, 0x40000820, 0, 0, 0x40005560)


@pytest.mark.parametrize('depth', (0, 1))
@pytest.mark.parametrize('shadow_state', ('dirty', 'clean'))
def test_native_reference_distinguishes_both_depths_and_clear_dirtiness(depth, shadow_state):
    first = BranchVector(0x40000820, 0x40002340, 5, 3)
    changed = replace(first, target=0x40002740)
    extra = replace(first, pc=0x40000860, target=0x40003560, position=6)
    updated = replace(extra, target=0x40003D60)
    wanted = expected_mbtb_cleanup_dual(first, changed, extra, updated, depth, shadow_state)
    assert wanted['before'][1][0]['dirty'] == int(shadow_state == 'dirty')
    assert wanted['ports'][1]['read_valid'] == int(shadow_state == 'dirty')
    assert wanted['ports'][1]['write_tag'] == wanted['ports'][1]['write_position'] == 0
    assert wanted['ports'][0]['write_lower'] == 0x3D60
    assert wanted['after'][0][depth]['lower'] == 0x3D60
    assert wanted['after'][0][depth]['dirty'] == 1
    assert wanted['after'][1] == wanted['before'][1]


@pytest.mark.parametrize('shadow_state', ('dirty', 'clean'))
async def test_agent_owns_cleanup_phase_sequence(monkeypatch, shadow_state):
    log = []
    agent = object.__new__(MbtbAgent)
    agent._started = True
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
    async def idle(*groups):
        assert groups == ('pipeline', 'writes')
        log.append(('idle', agent._defer_multi_hit_cleanup))
    agent.training_activity = SimpleNamespace(wait_idle=idle)
    monkeypatch.setattr('suites.frontend.bpu.mbtb.agent.main.ClockCycles', cycles)
    await agent.train_during_multi_hit_cleanup('feedback', shadow_state=shadow_state)
    expected = [('s2', True), ('cycles', 1), ('s2', False), ('idle', True)] if shadow_state == 'clean' else []
    assert log == expected + [('s2', True), ('train', dict(payload='feedback')),
                              ('s2', False), ('idle', True), ('s2', True)]
    assert agent._multi_hit_cleanup_scope_active and not agent._defer_multi_hit_cleanup


@pytest.mark.parametrize('condition', ('inactive', 'resumed', 'state', 'feedback'))
async def test_agent_rejects_invalid_cleanup_before_driving(condition):
    agent = object.__new__(MbtbAgent)
    agent._started = True
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
    agent._started = True
    agent._multi_hit_cleanup_scope_active = agent._defer_multi_hit_cleanup = False
    agent.dut = SimpleNamespace(clock='clock')
    agent.lookup_driver = SimpleNamespace(quiesce=lambda: None)
    agent.consume_driver = SimpleNamespace(quiesce=lambda: None)
    async def cycles(_clock, _count):
        pass
    monkeypatch.setattr('suites.frontend.bpu.mbtb.agent.main.ClockCycles', cycles)
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
    agent._multi_hit_cleanup_scope_active = agent._defer_multi_hit_cleanup = True
    agent.dut = SimpleNamespace(clock='clock')
    agent.lookup_driver = SimpleNamespace(quiesce=lambda: None)
    agent.consume_driver = SimpleNamespace(quiesce=lambda: None)
    agent._encode_training = lambda value: value
    async def cycles(_clock, _count):
        raise RuntimeError('interrupted pulse')
    monkeypatch.setattr('suites.frontend.bpu.mbtb.agent.main.ClockCycles', cycles)
    with pytest.raises(RuntimeError, match='interrupted pulse'):
        await agent.train_during_multi_hit_cleanup('feedback', shadow_state='clean')
    assert agent._multi_hit_cleanup_scope_active and agent._defer_multi_hit_cleanup
