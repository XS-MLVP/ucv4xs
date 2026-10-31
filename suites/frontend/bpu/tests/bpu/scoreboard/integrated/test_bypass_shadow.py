"""Pure input-driven oracle checks, including the known dirty-copy hazard."""
from copy import deepcopy
import pytest
from suites.frontend.bpu.bpu.model.bypass.model import BypassReference
from suites.frontend.bpu.bpu.model.bypass.model import saturate


def boundary(**changes):
    value = dict(read_index=0, train_index=0, tag=0, allocate=0, allocate_taken=0,
        allocate_position=0, update=0, update_taken=0, update_position=0,
        update_counter=0, useful_valid=0, useful_increase=0, age=0)
    value.update(changes)
    return value


@pytest.mark.parametrize('counter', range(8))
@pytest.mark.parametrize('increase', (0, 1))
def test_counter_arithmetic_independent_boundary(counter, increase):
    reference = BypassReference(0)
    reference.advance(boundary(train_index=17))
    event = reference.advance(boundary(train_index=18, update=1, update_counter=counter,
        update_taken=increase, tag=11, update_position=4))
    expected = counter + (1 if increase else -1)
    expected = 0 if expected < 0 else 7 if expected > 7 else expected
    assert event['source'] == 'captured_counter'
    assert reference.cells[0]['counter'] == expected
    assert reference.cells[0]['index'] == 17
    assert reference.cells[0]['position'] == 4


@pytest.mark.parametrize('table', (0, 1))
@pytest.mark.parametrize('taken', (0, 1))
def test_allocate_and_adjacent_same_index_forward(table, taken):
    reference = BypassReference(table)
    reference.advance(boundary(train_index=41))
    first = reference.advance(boundary(train_index=41, allocate=1, allocate_taken=taken, tag=33))
    assert (first['counter'], first['same_index_forward']) == (4 if taken else 3, 1)
    assert reference.useful[41] == table + 1
    second = reference.advance(boundary(train_index=99, update=1, update_taken=taken,
        update_counter=0 if taken else 7, tag=33))
    assert second['source'] == 'resident'
    assert second['prior_counter'] == first['counter']
    assert second['counter'] == (5 if taken else 2)
    assert reference.status[0]['dirty'] == 0
    assert reference.status[1]['dirty'] == 1


@pytest.mark.parametrize('table', (0, 1))
def test_tag_mismatch_uses_captured_not_other_resident_counter(table):
    reference = BypassReference(table)
    reference.advance(boundary(train_index=8))
    reference.advance(boundary(train_index=8, allocate=1, tag=10, allocate_taken=1))
    event = reference.advance(boundary(train_index=8, update=1, tag=11, update_taken=0, update_counter=7))
    assert (event['source'], event['prior_counter'], event['counter']) == ('captured_counter', 7, 6)
    assert reference.cells[1]['tag'] == 11


@pytest.mark.parametrize('table', (0, 1))
def test_useful_age_wins_over_allocation_and_uses_preedge_value(table):
    reference = BypassReference(table)
    reference.advance(boundary(train_index=7))
    reference.advance(boundary(train_index=7, allocate=1))
    original = table + 1
    reference.advance(boundary(train_index=8, allocate=1, age=1))
    assert reference.useful[7] == (original - 1 if table == 0 else original // 2)
    assert reference.useful[8] == 0


def test_wrap_priority_group_keeps_unwritten_old_cells_available():
    reference = BypassReference(1)
    for index in range(8):
        reference.advance(boundary(train_index=index))
        reference.advance(boundary(train_index=100, allocate=1, tag=index))
    assert (reference.enq, reference.mask) == (8, 255)
    reference.advance(boundary(train_index=9))
    reference.advance(boundary(train_index=100, allocate=1, tag=90))
    assert (reference.enq, reference.mask) == (9, 1)
    assert reference.select(2) == (4, 0, 2)
    reference.advance(boundary(read_index=2))
    assert reference.outputs(boundary())['response']['tag'] == 2
    assert reference.outputs(boundary())['response']['hit'] == 1


def test_same_slot_retirement_must_not_erase_new_dirty_copy():
    reference = BypassReference(0)
    for index in range(8):
        reference.advance(boundary(train_index=index))
        reference.advance(boundary(train_index=100, allocate=1, tag=index))
    reference.advance(boundary(train_index=0))
    event = reference.advance(boundary(train_index=100, update=1, update_taken=1, tag=0))
    assert event['same_slot_retirement'] == 1
    assert reference.cells[0]['counter'] == 4
    assert reference.status[0]['dirty'] == 1  # known RTL bug must fail this contract


def test_write_success_is_bank_derived_not_injected_as_an_input():
    reference = BypassReference(0)
    reference.advance(boundary(train_index=3))
    reference.advance(boundary(train_index=0, allocate=1))
    assert reference.outputs(boundary(read_index=3))['write_success'] == 0
    assert reference.outputs(boundary(read_index=0))['write_success'] == 1
    assert reference.outputs(boundary(read_index=0))['write']['index'] == 3


def test_reset_clears_all_state_without_observed_seed():
    reference = BypassReference(1)
    reference.advance(boundary(allocate=1))
    reference.advance(boundary(), reset=True)
    assert reference.state() == BypassReference(1).state()


def test_conflicting_boundary_is_rejected_without_state_mutation():
    reference = BypassReference(0)
    prior = deepcopy(reference.state())
    with pytest.raises(ValueError, match='mutually exclusive'):
        reference.advance(boundary(allocate=1, update=1))
    assert reference.state() == prior
