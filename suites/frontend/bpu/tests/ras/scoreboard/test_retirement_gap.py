"""Hand-derived BOS endpoints and fault-detecting full-state comparisons."""
from copy import deepcopy
from dataclasses import replace
from itertools import product
from types import SimpleNamespace

import pytest
from toffee import Scoreboard, ScoreboardMismatch
from bpuverify.ras.case.retirement_gap import check_gap
from bpuverify.ras.coverage.supplemental import RETIREMENT_GAP_CONTRACTS, ras_retirement_gap_coverage_model
from bpuverify.ras.model.model import Cell
from bpuverify.ras.model.retirement import DistinctSpeculation, QueueCell, Retirement, pointer
from bpuverify.ras.scoreboard.retirement import check_observation


@pytest.mark.parametrize('bos,tosw,expected', (
    (4, 4, 4), (4, 5, 4), (4, 6, 4), (4, 7, 6),
    (15, 17, 15), (15, 18, 17), (31, 1, 31), (31, 2, 1), (30, 1, 0),
))
def test_non_push_distance_boundary_and_pointer_wrap(bos, tosw, expected):
    state = Retirement(head=1, cells=(Cell(), Cell(0x100), Cell(0x200)) + (Cell(),) * 5, bos=bos)
    following = state.accept(1, ssp=3, tosw=tosw)
    assert following.bos == expected and following.head == 2
    assert following.cells == state.cells  # Pop retains every physical cell.
    assert state.bos == bos and pointer(expected) == dict(flag=expected // 16, value=expected % 16)


@pytest.mark.parametrize('bos,tosw', ((4, 7), (15, 18), (31, 2), (30, 1)))
def test_push_priority_allocates_from_metadata_not_old_head(bos, tosw):
    state = Retirement(head=1, cells=(Cell(), Cell(0x100), Cell(0x200), Cell(0x300)) + (Cell(),) * 4, bos=bos)
    following = state.accept(2, ssp=3, tosw=tosw, address=0x400)
    assert following.bos == tosw and following.head == 4
    assert following.cells == state.cells[:4] + (Cell(0x400),) + state.cells[5:]


def test_repeat_repair_updates_counter_only_at_metadata_owner():
    state = Retirement(head=1, cells=(Cell(), Cell(0x100, 3), Cell(0x200, 6)) + (Cell(),) * 5)
    pushed = state.accept(2, ssp=2, tosw=3, address=0x100)
    popped = state.accept(1, ssp=2, tosw=3)
    assert pushed.head == popped.head == 2
    assert pushed.cells[2] == Cell(0x200, 4) and popped.cells[2] == Cell(0x200, 2)
    assert pushed.cells[:2] == popped.cells[:2] == state.cells[:2]
    saturated = replace(state, cells=(Cell(), Cell(0x100, 7)) + state.cells[2:])
    assert saturated.accept(2, ssp=1, tosw=0, address=0x100).cells[2] == Cell(0x100, 0)


@pytest.mark.parametrize('epoch,kind', tuple(product(('same', 'cross'), ('threshold-hold', 'gap-reclaim', 'push-priority'))))
def test_hand_derived_fault_endpoints_and_continued_operation(epoch, kind):
    spec, ret = DistinctSpeculation(), Retirement()

    def operation(action, address=None, commit=True):
        nonlocal spec, ret
        after = spec.act(action, ret, address=address)
        if commit:
            ret = ret.accept(action, ssp=spec.ssp, tosw=spec.write, address=address)
        spec = after

    operation(2, 0x100)
    for _ in range(4 if epoch == 'same' else 15):
        operation(2, 0x200)
        operation(1)
    assert (spec.write, ret.bos) == ((5, 4) if epoch == 'same' else (16, 15))
    operation(2, 0x300, False)
    if kind != 'threshold-hold':
        operation(2, 0x301, False)
    operation(2 if kind == 'push-priority' else 1, 0x400 if kind == 'push-priority' else None)
    expected = {'threshold-hold': (1, 0x100, 4 if epoch == 'same' else 15),
        'gap-reclaim': (2, 0x200, 6 if epoch == 'same' else 17),
        'push-priority': (4, 0x400, 7 if epoch == 'same' else 18)}[kind]
    assert (ret.head, spec.top(ret), ret.bos) == expected
    if kind == 'gap-reclaim':
        operation(1)
        assert ret.head == spec.ssp == 1 and spec.top(ret) == 0x100
    survivor = spec.top(ret), spec.ssp
    operation(2, 0x500)
    operation(1)
    assert (spec.top(ret), spec.ssp) == survivor


@pytest.mark.parametrize('kwargs', (
    dict(action=0, ssp=0, tosw=0), dict(action=3, ssp=0, tosw=0), dict(action=True, ssp=0, tosw=0),
    dict(action=1, ssp=-1, tosw=0), dict(action=1, ssp=8, tosw=0), dict(action=1, ssp=True, tosw=0),
    dict(action=1, ssp=0, tosw=-1), dict(action=1, ssp=0, tosw=32), dict(action=1, ssp=0, tosw=True),
    dict(action=1, ssp=0, tosw=17), dict(action=1, ssp=0, tosw=0, address=0),
    dict(action=2, ssp=0, tosw=0), dict(action=2, ssp=0, tosw=0, address=-1),
    dict(action=2, ssp=0, tosw=0, address=1 << 50), dict(action=2, ssp=0, tosw=0, address=True),
))
def test_invalid_retirement_rejected_without_state_change(kwargs):
    state = Retirement()
    with pytest.raises(ValueError):
        state.accept(**kwargs)
    assert state == Retirement()


def test_invalid_speculation_scope_and_unallocated_live_pointer_fail():
    spec, ret = DistinctSpeculation(), Retirement()
    for action, address in ((0, None), (3, None), (True, None), (1, None), (2, 0), (2, True)):
        with pytest.raises(ValueError):
            spec.act(action, ret, address=address)
    with pytest.raises(ValueError, match='genuine prior allocation'):
        replace(spec, write=1, read=0).top(ret)
    with pytest.raises(ValueError, match='bounded window'):
        replace(spec, write=17).top(ret)
    with pytest.raises(ValueError, match='repeated counters'):
        spec.act(2, replace(ret, cells=(Cell(0, 1),) + ret.cells[1:]), address=0x100)
    with pytest.raises(ValueError, match='capacity rollover'):
        replace(spec, ssp=7).act(2, ret, address=0x100)
    # A full, genuine window still cannot accept a seventeenth entry.
    full = DistinctSpeculation(write=16, cells=tuple(QueueCell(i, i + 1, 31) for i in range(16)))
    with pytest.raises(ValueError, match='bounded queue capacity'):
        full.act(2, ret, address=0x100)


CORRUPTIONS = (('head',), ('bos', 'flag'), ('bos', 'value'),
    *(('cells', slot, field) for slot in range(8) for field in ('address', 'counter')),
    ('public', 'top'), ('public', 'commit_meta', 'ssp'), ('public', 'commit_meta', 'tosw', 'value'),
    ('public', 'redirect_meta', 'tosr', 'flag'), ('public', 'redirect_meta', 'nos', 'value'),
    ('public', 'redirect_meta', 'topRetAddr_addr'), ('reset',), ('enable',), ('redirect', 'valid'),
    ('pending_commit', 'valid'))


def observation():
    spec, ret = DistinctSpeculation(), Retirement()
    row = dict(reset=0, enable=1, redirect=dict(valid=0), public=spec.public(ret),
        pending_commit=dict(valid=0, push=0, pop=0, ssp=0, tosw=pointer(0)), **ret.native())
    return spec, ret, SimpleNamespace(value=row, event=SimpleNamespace(tick=24))


@pytest.mark.parametrize('path', CORRUPTIONS)
def test_every_state_corruption_raises_with_context(path):
    spec, ret, sample = observation()
    original = deepcopy(sample.value)
    current = sample.value
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] ^= 1
    with pytest.raises(ScoreboardMismatch) as caught:
        check_observation(Scoreboard('ras.retirement_gap'), sample, speculation=spec, retired=ret,
            request=dict(phase='injected-fault', corruption=path), sequence=77)
    assert 'injected-fault' in str(caught.value) and '77' in str(caught.value)
    assert original != sample.value


@pytest.mark.parametrize('field', ('push', 'pop', 'ssp', 'tosw'))
def test_pending_commit_payload_corruption_raises(field):
    spec, ret, sample = observation()
    expected = dict(push=0, pop=1, ssp=2, tosw=pointer(3))
    sample.value['pending_commit'] = dict(valid=1, **deepcopy(expected))
    check_observation(Scoreboard('ras.retirement_gap'), sample, speculation=spec, retired=ret,
        request={}, sequence=1, pending=expected)
    if field == 'tosw':
        sample.value['pending_commit'][field]['value'] ^= 1
    else:
        sample.value['pending_commit'][field] ^= 1
    with pytest.raises(ScoreboardMismatch):
        check_observation(Scoreboard('ras.retirement_gap'), sample, speculation=spec, retired=ret,
            request={}, sequence=1, pending=expected)


GAP_ROWS = [dict(epoch=epoch, kind=kind, contract=contract) for epoch, kind, contract in product(
    ('same', 'cross'), ('threshold-hold', 'gap-reclaim', 'push-priority'), RETIREMENT_GAP_CONTRACTS)]


@pytest.mark.parametrize('missing', range(len(GAP_ROWS)))
def test_each_semantic_cross_bin_is_required(missing):
    coverage = ras_retirement_gap_coverage_model()
    for index, row in enumerate(GAP_ROWS):
        if index != missing:
            coverage.sample(row)
    with pytest.raises(AssertionError):
        coverage.assert_coverage(100.0)
    coverage.sample(GAP_ROWS[missing])
    coverage.assert_coverage(100.0)


@pytest.mark.parametrize('epoch,kind', (('bad', 'threshold-hold'), ('same', 'bad')))
async def test_bad_context_rejected_before_reset_or_native_access(epoch, kind):
    with pytest.raises(ValueError, match='semantic context'):
        await check_gap(None, None, epoch=epoch, kind=kind)
