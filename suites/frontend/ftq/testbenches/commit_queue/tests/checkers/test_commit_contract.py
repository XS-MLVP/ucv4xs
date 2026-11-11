"""Strict ABI and ledger corruption controls; these are pure selftests."""
from types import SimpleNamespace

import pytest

from suites.frontend.ftq.testbenches.commit_queue.env.bundle.ports import CommitQueuePorts
from suites.frontend.ftq.testbenches.commit_queue.checker.transactions import CommitTransactions
from suites.frontend.ftq.testbenches.commit_queue.transactions.types import EMPTY
from suites.frontend.ftq.testbenches.commit_queue.transactions.types import Input
from suites.frontend.ftq.testbenches.commit_queue.transactions.types import Snapshot
from suites.frontend.ftq.testbenches.ftq.model import CallRet

pytestmark = pytest.mark.selftest


class Signal:
    def __init__(self, bits, *, output=False):
        self.bits, self.output = bits, output

    def W(self):
        return self.bits

    def IsInIO(self):
        return not self.output

    def IsOutIO(self):
        return self.output


class Schema:
    def __init__(self):
        self.inputs = {'reset': Signal(1), 'clock': Signal(1)}
        self.outputs = {}
        for lane in range(8):
            self.inputs.update({f'io_backendCommit_{lane}_valid': Signal(1),
                                f'io_backendCommit_{lane}_bits_rasAction': Signal(2),
                                f'io_backendCommit_{lane}_bits_ftqPtr_value': Signal(6)})
        self.outputs.update(io_bpuTrain_valid=Signal(1, output=True),
                            io_bpuTrain_bits_rasAction=Signal(2, output=True),
                            io_bpuTrain_bits_ftqPtr_value=Signal(6, output=True))
        self.refresh()

    def refresh(self):
        self.dut = SimpleNamespace(**self.inputs, **self.outputs)
        self._inputs = {key: value for key, value in self.inputs.items() if key != 'clock'}

    def input_names(self):
        return tuple(self._inputs)

    def output_names(self):
        return frozenset(self.outputs)

    def input(self, name):
        return self._inputs[name]


@pytest.mark.parametrize('name,width,output', (
    ('reset', 2, False), ('clock', 2, False),
    ('io_backendCommit_0_valid', 2, False),
    ('io_backendCommit_7_bits_rasAction', 3, False),
    ('io_backendCommit_7_bits_ftqPtr_value', 7, False),
    ('io_backendCommit_0_valid', 1, True),
    ('io_bpuTrain_bits_ftqPtr_value', 5, True),
    ('io_bpuTrain_valid', 1, False),
))
def test_wrong_physical_width_or_direction_is_not_accepted(name, width, output):
    schema = Schema()
    fields = schema.inputs if name in schema.inputs else schema.outputs
    fields[name] = Signal(width, output=output)
    schema.refresh()
    with pytest.raises(ValueError, match='expected'):
        CommitQueuePorts.bind(schema)


@pytest.mark.parametrize('mutation', ('missing-input', 'extra-input', 'missing-output', 'extra-output'))
def test_unknown_or_missing_physical_field_is_not_an_implicit_zero(mutation):
    schema = Schema()
    if mutation == 'missing-input':
        del schema.inputs['io_backendCommit_7_valid']
    elif mutation == 'extra-input':
        schema.inputs['unknown_input'] = Signal(1)
    elif mutation == 'missing-output':
        del schema.outputs['io_bpuTrain_valid']
    else:
        schema.outputs['unknown_output'] = Signal(1, output=True)
    schema.refresh()
    with pytest.raises((KeyError, ValueError)):
        CommitQueuePorts.bind(schema)


def test_slot_owns_a_frozen_copy_of_the_full_lane_vector():
    rows = [CallRet(63, 3)] + [None] * 7
    frame = Input(1, rows)
    rows[0] = CallRet(0, 0)
    assert frame.rows == (CallRet(63, 3),) + (None,) * 7
    with pytest.raises(AttributeError):
        frame.rows = EMPTY


def test_two_equal_payloads_complete_as_two_ordered_input_identities():
    checker = CommitTransactions()
    value = CallRet(5, 2)
    rows = (value, value) + (None,) * 6
    checker.advance_slot(Input(1, rows), Snapshot(False, rows, None), Snapshot(False, rows, value), 2)
    checker.advance_slot(Input(2), Snapshot(False, EMPTY, value), Snapshot(False, EMPTY, value), 4)
    checker.advance_slot(Input(3), Snapshot(False, EMPTY, value), Snapshot(False, EMPTY, None), 6)
    receipt = checker.receipt()
    assert receipt['accepted'] == ((0, 1, 0), (0, 1, 1))
    assert [(item.action.uid, item.status, item.tick) for item in receipt['terminals']] == [
        ((0, 1, 0), 'completed', 4), ((0, 1, 1), 'completed', 6)]


@pytest.mark.parametrize('mutation', ('lost-pending', 'lost-accepted', 'invented-terminal'))
def test_ledger_cannot_claim_closure_by_erasing_or_inventing_identity(mutation):
    checker = CommitTransactions()
    rows = (CallRet(5, 2),) + (None,) * 7
    checker.advance_slot(Input(1, rows), Snapshot(False, rows, None), Snapshot(False, rows, rows[0]), 2)
    if mutation == 'lost-pending':
        checker.pending.clear()
    elif mutation == 'lost-accepted':
        checker.accepted.clear()
    else:
        checker.terminal(checker.pending[0], 'completed', 2)
    with pytest.raises(AssertionError, match='commit_queue'):
        checker.receipt()
