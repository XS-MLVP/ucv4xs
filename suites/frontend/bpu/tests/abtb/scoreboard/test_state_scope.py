"""Out-of-scope requests fail before requiring a native DUT."""
from pathlib import Path
import pytest

from suites.frontend.bpu.abtb.env.state.counter import CounterScenario
from suites.frontend.bpu.abtb.env.state.replacer import ReplacerScenario
from suites.frontend.bpu.abtb.env.state.priority import ResetPriorityScenario
from suites.frontend.bpu.abtb.env.state.writebuffer import WriteBufferScenario
from suites.frontend.bpu.abtb.coverage.state.supplemental import capacity_coverage
from suites.frontend.bpu.abtb.coverage.state.supplemental import gate_coverage
from suites.frontend.bpu.abtb.coverage.state.supplemental import priority_coverage
from suites.frontend.bpu.abtb.coverage.state.supplemental import replacer_coverage
from suites.frontend.bpu.abtb.coverage.state.supplemental import transition_coverage


@pytest.mark.parametrize('bank', (-1, 4, 1.0, True, '0'))
@pytest.mark.parametrize('factory', (
    lambda bank: CounterScenario(None, Path('.'), bank=bank, sets=(5,)),
    lambda bank: ReplacerScenario(None, Path('.'), bank=bank, same_set=True),
    lambda bank: ResetPriorityScenario(None, Path('.'), bank=bank, way=0, old=2, taken=1, release_phase=0),
    lambda bank: WriteBufferScenario(None, Path('.'), bank=bank, order='ascending', coverage=None),
    lambda bank: transition_coverage(bank, (5,)),
    lambda bank: gate_coverage(bank, (5,)),
    lambda bank: priority_coverage(bank),
    lambda bank: capacity_coverage(bank, ('ascending',)),
    lambda bank: replacer_coverage(bank, True, sets=(5,), victims=(0,)),
))
def test_unsupported_bank_is_rejected(bank, factory):
    with pytest.raises(ValueError, match='bank'):
        factory(bank)


@pytest.mark.parametrize('sets', ((), (-1,), (64,), (5, 5), (1.0,), (True,)))
@pytest.mark.parametrize('factory', (
    lambda sets: CounterScenario(None, Path('.'), bank=0, sets=sets),
    lambda sets: ReplacerScenario(None, Path('.'), bank=0, same_set=True, sets=sets),
    lambda sets: transition_coverage(0, sets),
    lambda sets: gate_coverage(0, sets),
))
def test_invalid_set_axes_are_not_empty_or_inflated_coverage(sets, factory):
    with pytest.raises(ValueError, match='sets'):
        factory(sets)


@pytest.mark.parametrize('field,value', (
    ('way', -1), ('way', 4), ('old', -1), ('old', 4), ('taken', 2),
    ('release_phase', -1), ('release_phase', 4),
))
def test_priority_scope_is_explicit(field, value):
    arguments = dict(bank=0, way=0, old=2, taken=1, release_phase=0)
    arguments[field] = value
    with pytest.raises(ValueError):
        ResetPriorityScenario(None, Path('.'), **arguments)


@pytest.mark.parametrize('orders', ((), ('invalid',), ('ascending', 'ascending')))
def test_capacity_coverage_requires_unique_supported_orders(orders):
    with pytest.raises(ValueError, match='orders'):
        capacity_coverage(0, orders)


@pytest.mark.parametrize('victims', ((), (-1,), (4,), (0, 0)))
def test_replacer_coverage_rejects_invalid_victims(victims):
    with pytest.raises(ValueError, match='ways'):
        replacer_coverage(0, True, sets=(5,), victims=victims)


def test_replacer_relation_cannot_be_an_accidental_truthy_string():
    with pytest.raises(ValueError, match='bool'):
        ReplacerScenario(None, Path('.'), bank=0, same_set='False')


def test_all_four_kind_functional_crosses_have_independent_denominators():
    groups = (transition_coverage(0, range(64)), gate_coverage(0, range(64)),
              priority_coverage(0), capacity_coverage(0, ('ascending','descending','interleaved','boundary')),
              replacer_coverage(0, True, sets=range(64), victims=range(4)))
    for group in groups:
        assert not group.covered
        with pytest.raises(AssertionError):
            group.assert_coverage(100.0)
