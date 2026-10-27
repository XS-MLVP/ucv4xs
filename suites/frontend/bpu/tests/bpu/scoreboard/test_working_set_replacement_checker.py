"""A predicted new owner does not count until actual whole-state comparison."""
from dataclasses import replace

import pytest

from tests.bpu.scoreboard.test_ahead_working_set import state_fixture
from bpuverify.bpu.checker.working_set_replacement import Checks



def pending_replacement():
    old, row, events, cycle, model, token, frame = state_fixture()
    checks = Checks(old.program, old.coverage)
    checks.pipeline = old.pipeline
    checks.begin(0, 'warm')
    checks.candidates(row, events, cycle, model, None, None)
    entry = model.sources.ahead.memory[0, 0, 0]
    model.sources.ahead.memory[0, 0, 0] = replace(entry, tag=entry.tag + 1)
    model.sources.ahead.counters[0, 0, 0] = 2
    checks.checked(100)
    cycle.metadata = None
    return checks, row, events, cycle, model, entry


def test_strong_old_identity_reset_needs_a_later_actual_state_confirmation():
    checks, row, events, cycle, model, old = pending_replacement()
    assert not checks.strong_replacement_examples
    assert checks.strong_resets == 0
    row['observed']['ahead_working_state']['counters'] = (2,) + (0,) * 1023
    checks.candidates(row, events, cycle, model, None, None)
    witness, = checks.strong_replacement_examples
    assert witness['old_tag'] == old.tag and witness['tag'] == old.tag + 1
    assert witness['old_counter'] == 3 and witness['observed_new_identity_confidence'] == 2
    assert witness['all_counter_and_recency_state_compared']
    assert checks.strong_resets == 1
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('old-strength-inherited', 'unrelated-counter', 'unrelated-recency'))
def test_target_or_neighbor_corruption_cannot_earn_a_reset_witness(fault):
    checks, row, events, cycle, model, _ = pending_replacement()
    state = row['observed']['ahead_working_state']
    counters = [2] + [0] * 1023
    if fault == 'old-strength-inherited':
        counters[0] = 3
    elif fault == 'unrelated-counter':
        counters[999] = 1
    else:
        state['recency'] = (0,) * 255 + (1,)
    state['counters'] = tuple(counters)
    with pytest.raises(AssertionError):
        checks.candidates(row, events, cycle, model, None, None)
    assert not checks.strong_replacement_examples and checks.strong_resets == 0
    assert checks.coverage.groups['checked'].coverage == 0
