"""Normal semantic inputs prove overlap without setting useful/tick state."""
from copy import deepcopy

import pytest

from bpuverify.utage.model.aging_learning import AgingLearningProgram, RULES
from bpuverify.utage.model.semantic import Base, Events, UtageReference
from tests.utage.scoreboard.test_semantic_model import lookup, feedback, learn


PROGRAMS = tuple(AgingLearningProgram(table, rule) for table in (0, 1) for rule in RULES)


def read(model, expected):
    context = expected.context
    prediction = lookup(model, pc=context.pc, history=context.history,
        bases=(Base(True, 5, bool(expected.base), 1), Base(), Base(), Base()))
    provider = prediction.frame.providers()[0]
    counter = None if provider is None else prediction.frame.read.entries[provider].counter
    assert (provider, counter) == (expected.provider, expected.counter), (expected, prediction)
    return prediction


def useful_values(model):
    return tuple(model.useful[table].get(index, 0) for table in range(2) for index in range(512))


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p:p.name)
def test_target_outcome_is_the_declared_allocation_reward_or_error(program):
    expected = {(0, 'allocate'): 0, (0, 'reward'): 0, (0, 'penalty'): 1,
                (1, 'allocate'): 1, (1, 'reward'): 0, (1, 'penalty'): 0}
    assert program.target_learning.actual == expected[program.table, program.rule]


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p:p.name)
def test_real_failed_feedback_and_target_learning_share_one_maintenance_boundary(program):
    model = UtageReference()
    original = []
    for step in program.preparation:
        prediction = read(model, step.source)
        request = feedback(prediction, taken=bool(step.actual))
        original.append((request, deepcopy(request)))
        learn(model, request)
    assert model.low_tick == program.preparation_failures
    target = program.target_learning
    prediction = read(model, target.source)
    target_request = feedback(prediction, taken=bool(target.actual))
    original.append((target_request, deepcopy(target_request)))
    for previous in range(program.ordinary_failures):
        step = program.failed_source(previous)
        prediction = read(model, step.source)
        learn(model, feedback(prediction, taken=bool(step.actual)))
    assert model.low_tick == 127 and useful_values(model) == program.before
    last = program.failed_source(program.ordinary_failures)
    final_request = feedback(read(model, last.source), taken=bool(last.actual))
    observed_overlap = []
    for event in (Events(feedback=final_request), Events(feedback=target_request), Events(), Events()):
        applied = None if model.learning is None else model.learning.feedback
        previous = useful_values(model)
        model.advance(event)
        if model.aged:
            assert applied == target_request
            assert previous == program.before and useful_values(model) == program.after
            observed_overlap.append(model.cycles)
    assert len(observed_overlap) == 1 and model.low_tick == 0
    for consumer in program.consumers:
        read(model, consumer)
    assert useful_values(model) == program.after
    assert all(request == frozen for request, frozen in original)


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p:p.name)
def test_selected_protection_prestate_distinguishes_wrong_local_effect_at_maintenance(program):
    address = program.table * 512 + program.target.index[program.table]
    old = program.before[address]
    if program.rule == 'allocate':
        wrong = program.table + 1  # Initialization incorrectly survives aging.
    else:
        local = old + (1 if program.rule == 'reward' else -1)
        wrong = max(0, local - 1) if program.table == 0 else local // 2
    assert wrong != program.after[address]


def test_context_geometry_is_distinct_and_short_consumer_is_a_real_long_history_alias():
    program = PROGRAMS[0]
    contexts = (program.target, program.neighbor, program.failure)
    for table in range(2):
        assert len({context.index[table] for context in contexts}) == 3
    for context in contexts:
        assert context.index[0] == context.short_alias.index[0]
        assert context.index[1] != context.short_alias.index[1]
    assert len({context.index[1] for origin in contexts for context in (origin, origin.short_alias)}) == 6


@pytest.mark.parametrize('table,rule', ((True, 'reward'), (2, 'reward'), (0, 'random')))
def test_maintenance_program_rejects_physical_or_undefined_event_categories(table, rule):
    with pytest.raises(ValueError):
        AgingLearningProgram(table, rule)
