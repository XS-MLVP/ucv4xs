"""Expanded logical stack, existing independent models and negative controls."""
from collections import Counter
import pytest
from toffee import Scoreboard, ScoreboardMismatch
from suites.frontend.bpu.ras.model.model import advance
from suites.frontend.bpu.ras.model.semantic import Events, RasReference, Retirement
from suites.frontend.bpu.bpu.model.ras.layered_recursion import Program, PROFILES, RULES, LAYERS, ROOT_RETURN
from suites.frontend.bpu.bpu.coverage.ras_layered_recursion import Coverage
from suites.frontend.bpu.bpu.checker.ras.layered_recursion import compare_returns


@pytest.mark.parametrize('calls', PROFILES)
def test_expanded_logical_stack_and_committed_groups_preserve_each_outer_repeat_count(calls):
    program, returned = Program(calls), 0
    expanded = list(program.call_addresses())
    state = program.committed()
    assert Counter(expanded) == {ROOT_RETURN: 1, LAYERS[0]+16: 3, LAYERS[1]+16: 2, LAYERS[2]+16: calls}
    for target in program.return_targets:
        assert target == expanded.pop() == state.projection()['top']
        state = advance(state, 1)
        returned += 1
        assert state == program.committed(returned=returned)
        assert state.projection()['top'] == (expanded[-1] if expanded else 0)
    assert len(state.groups) == 1 and state.head == 0 and not state.evicted
    with pytest.raises(ValueError, match='bottom/empty'):
        advance(state, 1)


@pytest.mark.parametrize('calls', PROFILES)
def test_existing_semantic_reference_agrees_with_program_without_native_state_input(calls):
    program, model = Program(calls), RasReference()
    for address in program.call_addresses():
        before = model.program
        model.advance(Events(2, 2*address)); model.advance()
        model.advance(Events(retirement=Retirement(*before.commit_key(), 2))); model.advance()
    for target in program.return_targets:
        assert model.projection['top'] == target
        before = model.program
        model.advance(Events(1)); model.advance()
        model.advance(Events(retirement=Retirement(*before.commit_key(), 1))); model.advance()
    assert len(model.program.frames) == 1 and model.program.head.address == 0
    assert model.retirements == 2*len(program.call_addresses())


@pytest.mark.parametrize('calls', PROFILES)
@pytest.mark.parametrize('missing', RULES)
def test_no_partial_lifetime_can_obtain_checked_credit(calls, missing):
    coverage = Coverage(Program(calls))
    for rule in RULES:
        if rule != missing: coverage.reached(rule)
    with pytest.raises(AssertionError, match='incomplete'): coverage.finish()
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('calls', PROFILES)
def test_complete_lifetime_can_receive_credit_only_once(calls):
    coverage = Coverage(Program(calls))
    for rule in RULES: coverage.reached(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage == 50
    with pytest.raises(AssertionError): coverage.finish()
    with pytest.raises(ValueError): coverage.reached(RULES[0])


@pytest.mark.parametrize('calls', PROFILES)
@pytest.mark.parametrize('damage', ('wrong-outer-target', 'wrong-owner-PC', 'missing-return', 'duplicate-return'))
def test_return_chain_checker_rejects_wrong_owner_count_and_target(calls, damage):
    program, board = Program(calls), Scoreboard('layered-return-control')
    pcs, targets = list(program.return_pcs), list(program.return_targets)
    if damage == 'wrong-outer-target': targets[calls] = targets[0]
    elif damage == 'wrong-owner-PC': pcs[-1] = pcs[0]
    elif damage == 'missing-return': pcs.pop(); targets.pop()
    else: pcs.append(pcs[-1]); targets.append(targets[-1])
    def check(expected, actual, **context): board.check(expected=expected, actual=actual)
    with pytest.raises(ScoreboardMismatch): compare_returns(check, program, pcs, targets)


@pytest.mark.parametrize('calls', (0, 7, 9, 11, True))
def test_unqualified_or_bool_profile_is_rejected(calls):
    with pytest.raises(ValueError): Program(calls)
