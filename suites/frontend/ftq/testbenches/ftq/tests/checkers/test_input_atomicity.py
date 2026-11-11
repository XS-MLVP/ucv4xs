"""Strict FTQ inputs reject before any oracle or partial pin write."""
import pytest

from suites.frontend.ftq.testbenches.ftq.transactions.types import BackendRedirect
from suites.frontend.ftq.testbenches.ftq.transactions.types import Consumers
from suites.frontend.ftq.testbenches.ftq.transactions.types import IfuRedirect
from suites.frontend.ftq.testbenches.ftq.transactions.types import Meta
from suites.frontend.ftq.testbenches.ftq.transactions.types import Prediction
from suites.frontend.ftq.testbenches.resolve_queue.transactions.types import ResolveReport
from suites.frontend.ftq.testbenches.shared.env.ports import Pins
from suites.frontend.ftq.testbenches.shared.env.harness import Dut as NativeDut

pytestmark = pytest.mark.selftest


BUILDERS = (
    lambda value: Prediction(0, s2_ptr=value),
    lambda value: Meta(value),
    lambda value: Meta(0, flag=value),
    lambda value: BackendRedirect(value),
    lambda value: BackendRedirect(0, flag=value),
    lambda value: IfuRedirect(value),
    lambda value: IfuRedirect(0, flag=value),
    lambda value: ResolveReport(value, 0, 0, 0),
    lambda value: ResolveReport(0, value, 0, 0),
    lambda value: ResolveReport(0, 0, 0, 0, taken=value),
    lambda value: ResolveReport(0, 0, value, 0),
    lambda value: Consumers(prefetch=value),
    lambda value: Consumers(train=value),
)


@pytest.mark.parametrize('builder', BUILDERS)
@pytest.mark.parametrize('bad', (True, 1.0))
def test_integer_contracts_do_not_silently_accept_bool_or_float(builder, bad):
    with pytest.raises(ValueError):
        builder(bad)


def test_metadata_owns_its_snapshot_rather_than_a_mutable_callers_mapping():
    payload = {'payload': 7}
    meta = Meta(0, fields=payload)
    payload['payload'] = 8
    assert meta.fields['payload'] == 7
    with pytest.raises(TypeError):
        meta.fields['payload'] = 9


@pytest.mark.parametrize('field', ('pc', 'target'))
def test_resolve_halfword_coordinate_cannot_lose_a_fiftieth_bit(field):
    values = dict(index=0, pc=(1 << 49)-1, target=(1 << 49)-1, offset=31)
    report = ResolveReport(**values)
    assert report.pc == report.target == (1 << 49)-1
    values[field] = 1 << 49
    with pytest.raises(ValueError, match=field):
        ResolveReport(**values)


class Signal:
    def __init__(self, width):
        self.width = width
        self.writes = []

    def W(self):
        return self.width

    def Set(self, value):
        self.writes.append(value)


class Dut:
    def __init__(self):
        self._inputs = {'valid': Signal(1), 'value': Signal(6)}

    def output_names(self):
        return {'result'}

    def input(self, name):
        return self._inputs[name]


@pytest.mark.parametrize('bad', (
    {'valid': 1, 'missing': 0},
    {'valid': 1, 'value': 64},
    {'valid': 1, 'value': -1},
    {'valid': 1, 'value': 1.5},
    {'valid': 1, 'value': True},
    {'valid': 1, 'result': 0},
))
def test_bad_group_write_is_atomic_and_cannot_leave_a_valid_prefix_driven(bad):
    dut = Dut()
    pins = Pins(dut, {'valid': 'valid', 'value': 'value', 'result': 'result'}, name='atomic-input')
    with pytest.raises((KeyError, ValueError)):
        pins.set(**bad)
    assert all(not signal.writes for signal in dut._inputs.values())


def test_complete_legal_group_is_driven_without_narrowing_the_six_bit_domain():
    dut = Dut()
    pins = Pins(dut, {'valid': 'valid', 'value': 'value'}, name='legal-input')
    for value in (0, 63):
        pins.set(valid=1, value=value)
    assert dut._inputs['valid'].writes == [1, 1]
    assert dut._inputs['value'].writes == [0, 63]


def claim_subject():
    dut = object.__new__(NativeDut)
    dut._inputs = {'first': Signal(1), 'second': Signal(1)}
    dut._claims = {}
    dut._output_names = frozenset()
    return dut


def test_equal_driver_labels_cannot_hide_a_second_physical_owner():
    dut = claim_subject()
    first = Pins(dut, {'request': 'first'}, name='same-label')
    second = Pins(dut, {'request': 'first'}, name='same-label')
    first.claim('same-label.driver')
    with pytest.raises(RuntimeError, match='already owned'):
        second.claim('same-label.driver')


def test_group_claim_rejection_does_not_leak_an_earlier_free_pin():
    dut = claim_subject()
    dut.claim('first', 'original-driver')
    group = Pins(dut, {'free': 'second', 'conflicting': 'first'}, name='atomic-claim')
    before = dict(dut._claims)
    with pytest.raises(RuntimeError, match='already owned'):
        group.claim('second-driver')
    assert dut._claims == before


def test_two_logical_inputs_cannot_alias_one_claimed_physical_input():
    dut = claim_subject()
    group = Pins(dut, {'one': 'first', 'two': 'first'}, name='aliased-claim')
    with pytest.raises(ValueError, match='duplicate'):
        group.claim('driver')
    assert not dut._claims


def test_disjoint_claims_with_equal_component_labels_remain_legal():
    dut = claim_subject()
    dut.claim('first', 'component')
    dut.claim('second', 'component')
    assert dut._claims == {'first': 'component', 'second': 'component'}
