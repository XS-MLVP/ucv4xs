"""Hand vectors and distinguishing wrong-output controls, not native credit."""
from copy import deepcopy

import pytest

from suites.frontend.bpu.testbenches.bpu.checker.parent_primitives import ParentPrimitiveChecker
from suites.frontend.bpu.testbenches.bpu.model.parent_primitives import ENABLES
from suites.frontend.bpu.testbenches.bpu.model.parent_primitives import ParentPrimitiveReference
from suites.frontend.bpu.testbenches.bpu.model.parent_primitives import fetch_extent

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize('pc,target,position', (
    (0, 32, 31), (7, 32, 31), (15, 32, 31), (16, 48, 31),
    (0x7df, 0x7f0, 31), (0x7e0, 0x800, 31), (0x7ef, 0x800, 31),
    (0x7f0, 0x800, 15), (0x7ff, 0x800, 15), (0x800, 0x820, 31),
    ((1 << 49) + 0x7f0, (1 << 49) + 0x800, 15),
    ((1 << 50) - 1, 0, 15)))
def test_page_and_fetch_extent_have_independent_arithmetic_answers(pc, target, position):
    assert fetch_extent(pc) == dict(target=target, position=position)


def controls(**changed):
    return dict.fromkeys(ENABLES, 0) | changed


def test_delay_samples_two_edges_has_no_reset_and_fetch_latch_holds_without_fire():
    model = ParentPrimitiveReference()
    first = controls(ubtb=1, tage=1)
    initial = model.accept(first, fire=0, pc=0x7ff)
    assert initial == {}  # Unreset registers are deliberately not compared.
    second = model.accept(controls(mbtb=1), fire=1, pc=0x7f0)
    assert second['delayed'] == first
    assert second['enabled'] == controls(ubtb=1) | {'utage': 0}
    assert second['fallthrough'] == dict(target=0x800, position=15)
    third = model.accept(controls(abtb=1), fire=0, pc=0x900)
    assert third['delayed'] == controls(mbtb=1)
    assert third['fallthrough'] == second['fallthrough']


@pytest.mark.parametrize('fault', (None, 'early-delay', 'late-delay', 'cross-lane',
    'missing-field', 'ignores-parent-gate', 'bad-hold', 'bad-page', 'bad-guard', 'lost-edge'))
def test_parent_checker_rejects_wrong_timing_aliases_extent_and_suppressed_errors(fault):
    checker = ParentPrimitiveChecker()
    request = dict(controls=controls(ubtb=1, abtb=1, tage=1), fire=1, pc=(1 << 49) + 0x7f0)
    actual = dict(fallthrough=dict(target=(1 << 49) + 0x800, position=15))
    checker.capture(request, actual, pre_tick=1, tick=2)
    checker.raise_failure()
    request = dict(controls=controls(sc=1, mbtb=1), fire=0, pc=0x900)
    actual = dict(delayed=controls(ubtb=1, abtb=1, tage=1),
        enabled=controls(ubtb=1, abtb=1) | {'utage': 1},
        fallthrough=dict(target=(1 << 49) + 0x800, position=15))
    if fault == 'early-delay':
        actual['delayed'] = deepcopy(request['controls'])
    elif fault == 'late-delay':
        actual['delayed'] = controls()
    elif fault == 'cross-lane':
        actual['delayed']['ittage'], actual['delayed']['tage'] = 1, 0
    elif fault == 'missing-field':
        del actual['enabled']['utage']
    elif fault == 'ignores-parent-gate':
        actual['enabled']['tage'] = 1
    elif fault == 'bad-hold':
        actual['fallthrough'] = dict(target=0x920, position=31)
    elif fault == 'bad-page':
        actual['fallthrough']['target'] += 16
    elif fault == 'bad-guard':
        actual['fallthrough']['target'] &= (1 << 49) - 1
    checker.capture(request, actual, pre_tick=3, tick=6 if fault == 'lost-edge' else 4)
    if fault:
        with pytest.raises((AssertionError, KeyError)) as first:
            checker.raise_failure()
        count = checker.counts.copy()
        checker.capture(request, actual, pre_tick=5, tick=6)
        assert checker.counts == count
        with pytest.raises(type(first.value)) as last:
            checker.finish()
        assert first.value is last.value
    else:
        checker.raise_failure()
        checker.capture(request, dict(actual, delayed=request['controls'],
            enabled=request['controls'] | {'utage': 0}), pre_tick=5, tick=6)
        report = checker.finish()
        assert report['counts']['fetch_held'] == 2 and report['counts']['delay_checked'] == 2
        report['lookups'][0]['actual']['target'] = 0
        assert checker.lookups[0]['actual']['target'] != 0


def test_an_unexecuted_primitive_scope_cannot_finish():
    with pytest.raises(AssertionError, match='did not establish'):
        ParentPrimitiveChecker().finish()
