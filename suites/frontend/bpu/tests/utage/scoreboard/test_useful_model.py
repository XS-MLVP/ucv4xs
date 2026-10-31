"""Pure model contracts; fabricated inputs here never drive a DUT."""
from copy import deepcopy

import pytest
from suites.frontend.bpu.utage.transaction.types import UtageTraining
from suites.frontend.bpu.utage.checker.checking import UtageUsefulChecker
from suites.frontend.bpu.utage.model.model import UtageUsefulReference
from suites.frontend.bpu.utage.coverage.supplemental import utage_useful_update_coverage_model


def payload(*, table=1, index=0, increase=True, hit=1, base=None):
    predicted, actual = 0, 0 if increase else 1
    base = 1 if base is None else base
    slot = dict(valid=1, cfiPosition=5, hit=hit, tableId=table,
                baseTaken=base, predTaken=predicted)
    return dict(start_pc=0x40000000, meta=dict(readIndex=[index, index],
        abtbResult=[slot, *[dict(slot, valid=0, cfiPosition=position) for position in (6, 7, 8)]]),
        branch=dict(position=5, branch_type=1, ras_action=0, taken=actual, mispredict=int(not increase)))


@pytest.mark.parametrize('table', (0, 1))
@pytest.mark.parametrize('index', (0, 1, 3, 4, 127, 128, 255, 256, 511))
@pytest.mark.parametrize('old', range(4))
@pytest.mark.parametrize('increase', (False, True))
def test_direction_saturation_address_and_latency(table, index, old, increase):
    reference = UtageUsefulReference()
    reference.values[table * 512 + index] = old
    if table == 0:
        reference.values[512 + index] = 3  # block escalation in this arithmetic unit check
    before = list(reference.values)
    cycles = [reference.advance(tick, payload(table=table, index=index, increase=increase) if tick == 10 else None)
              for tick in (10, 12, 14, 16)]
    expected = min(3, old + 1) if increase else max(0, old - 1)
    before[table * 512 + index] = expected
    assert reference.values == before and reference.pending == 0
    assert cycles[0].controls is None and cycles[1].controls is None
    assert cycles[2].controls[table].index == index and cycles[2].controls[table].update == 1
    assert cycles[3].controls is None and len(cycles[3].effects) == 1
    effect = cycles[3].effects[0]
    assert (effect.table, effect.index, effect.before, effect.after) == (table, index, old, expected)
    assert [cycle.sampled for cycle in cycles] == [True, False, True, True]


def test_adjacent_allocation_uses_earlier_useful_read_not_current_state():
    reference = UtageUsefulReference()
    reference.values[0] = 3
    request = payload(table=0, increase=False)
    cycles = {tick: reference.advance(tick, request if tick in (0, 2, 4, 6) else None)
              for tick in range(0, 14, 2)}
    assert [cycles[tick].controls[1].allocate for tick in (4, 6, 8, 10)] == [1, 1, 0, 0]
    assert (reference.values[0], reference.values[512], reference.failed_allocations) == (0, 2, 2)
    assert reference.pending == 0


@pytest.mark.parametrize('table', (0, 1))
@pytest.mark.parametrize('old', range(4))
def test_base_agreement_leaves_useful_unqualified_and_unchanged(table, old):
    reference = UtageUsefulReference()
    reference.values[table * 512 + 127] = old
    before = list(reference.values)
    cycles = [reference.advance(tick, payload(table=table, index=127, increase=True, base=0) if tick == 0 else None)
              for tick in (0, 2, 4, 6)]
    assert cycles[2].controls[table].update == 1 and cycles[2].controls[table].useful_valid == 0
    assert all(not cycle.effects for cycle in cycles) and reference.values == before
    assert [cycle.sampled for cycle in cycles] == [True, False, False, False]


@pytest.mark.parametrize('kind', ('negative-index', 'large-index', 'missing-index', 'bool-index',
    'two-slots', 'mismatched-position', 'nonconditional', 'ras-action', 'bad-table', 'bad-direction'))
def test_bad_scope_rejected_before_reference_changes(kind):
    request = payload()
    if kind == 'negative-index': request['meta']['readIndex'][0] = -1
    elif kind == 'large-index': request['meta']['readIndex'][1] = 512
    elif kind == 'missing-index': request['meta']['readIndex'].pop()
    elif kind == 'bool-index': request['meta']['readIndex'][0] = True
    elif kind == 'two-slots': request['meta']['abtbResult'][1]['valid'] = 1
    elif kind == 'mismatched-position': request['branch']['position'] = 6
    elif kind == 'nonconditional': request['branch']['branch_type'] = 3
    elif kind == 'ras-action': request['branch']['ras_action'] = 2
    elif kind == 'bad-table': request['meta']['abtbResult'][0]['tableId'] = 2
    elif kind == 'bad-direction': request['branch']['taken'] = 2
    reference = UtageUsefulReference()
    with pytest.raises(ValueError): reference.advance(0, request)
    assert reference.last_tick is None and reference.pending == 0 and reference.values == [0] * 1024


def test_invalid_final_transaction_does_not_partially_plan_burst():
    checker = UtageUsefulChecker(mode='adjacent')
    valid = payload()
    good = UtageTraining(valid['start_pc'], 5, 0, valid['meta'])
    bad = UtageTraining(valid['start_pc'], 5, 0, deepcopy(valid['meta']), branch_type=3)
    with pytest.raises(ValueError): checker.plan((good, bad), phase='atomic-input-validation')
    assert not checker._planned and checker.reference.pending == 0


def test_full_update_coverage_keeps_all_blocked_cross_bins_required():
    coverage = utage_useful_update_coverage_model()
    for mode in ('serial', 'adjacent'):
        for table, size in ((0, 128), (1, 512)):
            for index in range(size):
                for role in ('increase', 'increase_hold', 'decrease', 'decrease_hold'):
                    coverage.sample(dict(mode=mode, table=table, index=index, role=role))
    assert coverage.cross_coverage('all_dimensions') == 62.5
    with pytest.raises(AssertionError): coverage.assert_coverage(100.0)
    for mode in ('serial', 'adjacent'):
        for index in range(128, 512):
            for role in ('increase', 'increase_hold', 'decrease', 'decrease_hold'):
                coverage.sample(dict(mode=mode, table=0, index=index, role=role))
    coverage.assert_coverage(100.0)

