"""Independent stack algebra, no register snapshots as expected inputs."""
from dataclasses import replace
from itertools import product
from types import SimpleNamespace

import pytest
from toffee import ScoreboardMismatch

from bpuverify.uras.checker.semantic import UrasSemanticChecker
from bpuverify.uras.model.semantic import Action, Operation, RasEvents, UrasReference, stack_top
from bpuverify.uras.transaction.types import UrasResult
from bpuverify.uras.coverage.semantic import UrasSemanticCoverage, obligations
from bpuverify.uras.coverage.semantic import HELD_PROFILES, HeldCallCoverage
from bpuverify.uras.case.semantic import held_call_repair_program
from bpuverify.uras.checker.semantic import HeldCallRepairChecks
from bpuverify.uras.agent.main import encode_events
from bpuverify.uras.monitor.semantic import decode_events


MAIN = 0x40003456
CALL_A = Operation(Action.CALL, 0x40000802, 3)
CALL_B = Operation(Action.CALL, 0x40001000, 11)
NEUTRAL = Operation()
RETURN = Operation(Action.RETURN)


@pytest.mark.parametrize('profile', HELD_PROFILES)
def test_held_call_lifetime_has_independent_stack_results_and_reversible_encoding(profile):
    from dataclasses import asdict
    coverage = HeldCallCoverage(profile)
    steps = held_call_repair_program(profile)
    checks = HeldCallRepairChecks(profile, steps, coverage)
    model = UrasReference()
    for phase, event, expected in steps:
        sample = SimpleNamespace(inputs=SimpleNamespace(**{
            field: SimpleNamespace(as_int=lambda value=value: value)
            for field, value in asdict(encode_events(event)).items()}),
            reset=SimpleNamespace(as_int=lambda: 0))
        assert decode_events(sample) == event
        actual = model.advance(event)
        assert actual == expected
        checks.observe(phase, event, actual)
        assert model.advance(RasEvents()) == actual  # Withdraw pulse, retain call.
    assert coverage.groups['checked'].coverage == 0.0
    result = checks.finish()
    assert result['status'] == 'PASS' and not result['BPU_parent_reachability_proved']
    assert coverage.groups['checked'].coverage == 25.0
    with pytest.raises(AssertionError, match='single-use'):
        checks.finish()


@pytest.mark.parametrize('profile', HELD_PROFILES)
@pytest.mark.parametrize('bad_phase', ('held-correction', 'withdrawn-hold', 'fresh-consumer', 'return-once'))
def test_stale_or_lost_call_and_duplicate_push_cannot_gain_complete_credit(profile, bad_phase):
    coverage = HeldCallCoverage(profile)
    steps = held_call_repair_program(profile)
    checks = HeldCallRepairChecks(profile, steps, coverage)
    for phase, events, expected in steps:
        if phase == bad_phase:
            actual = UrasResult(1, CALL_B.return_address if phase == 'return-once' else CALL_A.return_address)
            with pytest.raises(ScoreboardMismatch) as caught:
                checks.observe(phase, events, actual)
            assert 'phase' in str(caught.value) and profile in str(caught.value)
            with pytest.raises(AssertionError, match='complete held'):
                checks.finish()
            assert coverage.groups['checked'].coverage == 0.0
            return
        checks.observe(phase, events, expected)
    raise AssertionError('declared fault phase was not exercised')


@pytest.mark.parametrize('profile', HELD_PROFILES)
def test_missing_last_return_or_foreign_original_does_not_qualify(profile):
    coverage = HeldCallCoverage(profile)
    steps = held_call_repair_program(profile)
    checks = HeldCallRepairChecks(profile, steps, coverage)
    for phase, events, expected in steps[:-1]:
        checks.observe(phase, events, expected)
    with pytest.raises(AssertionError, match='complete held'):
        checks.finish()
    assert coverage.groups['checked'].coverage == 0.0
    phase, events, expected = steps[-1]
    with pytest.raises(ScoreboardMismatch):
        checks.observe(phase, replace(events, accept=CALL_A), expected)
    assert coverage.groups['checked'].coverage == 0.0


@pytest.mark.parametrize('profile', HELD_PROFILES)
def test_truncated_program_cannot_redefine_a_complete_lifetime(profile):
    with pytest.raises(ValueError, match='complete declared'):
        HeldCallRepairChecks(profile, held_call_repair_program(profile)[:-1], HeldCallCoverage(profile))


def test_semantic_encoding_requires_reset_through_the_reset_driver():
    with pytest.raises(ValueError, match='use reset'):
        encode_events(RasEvents(reset=True))


def reverse_oracle(main, operations):
    """Independent cancellation algebra: walk youngest→oldest, not a stack."""
    unmatched_returns = 0
    for operation in reversed(operations):
        if operation.action in (Action.CALL, Action.RETURN_AND_CALL):
            if unmatched_returns == 0:
                return UrasResult(1, (operation.pc - operation.pc % 8 + operation.position + 1) % (1 << 50))
            unmatched_returns -= 1
        if operation.action in (Action.RETURN, Action.RETURN_AND_CALL):
            unmatched_returns += 1
    return UrasResult(0, 0) if unmatched_returns else UrasResult(1, main)


@pytest.mark.parametrize('actions', tuple(product(tuple(Action), repeat=3)))
def test_age_order_matches_independent_reverse_cancellation(actions):
    operations = tuple(Operation(action, 0x40001000 + age * 0x40, age * 3)
                       for age, action in enumerate(actions))
    model = UrasReference()
    model.advance(RasEvents(accept=operations[0], main_top=MAIN))
    model.advance(RasEvents(advance=True, main_top=MAIN))
    model.advance(RasEvents(accept=operations[1], main_top=MAIN))
    actual = model.advance(RasEvents(accept=operations[2], main_top=MAIN))
    assert actual == reverse_oracle(MAIN, operations)


@pytest.mark.parametrize('old,corrected', tuple(product(tuple(Action), repeat=2)))
def test_pending_correction_replaces_younger_but_retains_older(old, corrected):
    model = UrasReference()
    older = Operation(old, CALL_A.pc, CALL_A.position)
    correction = Operation(corrected, CALL_B.pc, CALL_B.position)
    model.advance(RasEvents(accept=older, main_top=MAIN))
    model.advance(RasEvents(advance=True, main_top=MAIN))
    model.advance(RasEvents(accept=CALL_A, main_top=MAIN))
    actual = model.advance(RasEvents(correct_pending=correction, accept=CALL_A, main_top=MAIN))
    assert actual == reverse_oracle(MAIN, (older, correction))
    assert model.younger == correction and model.older == older


@pytest.mark.parametrize('corrected', tuple(Action))
def test_retiring_correction_discards_both_younger_operations(corrected):
    model = UrasReference()
    model.advance(RasEvents(accept=CALL_A, main_top=MAIN))
    model.advance(RasEvents(advance=True, main_top=MAIN))
    model.advance(RasEvents(accept=CALL_B, main_top=MAIN))
    correction = Operation(corrected, CALL_B.pc, CALL_B.position)
    actual = model.advance(RasEvents(accept=CALL_A, correct_pending=CALL_A,
                                    correct_retiring=correction, main_top=MAIN,
                                    advance=True, retire=True))
    assert actual == reverse_oracle(MAIN, (correction,))
    assert model.younger is None and model.older is None


def test_push_pop_hand_calculations_and_unknown_depth():
    assert stack_top(MAIN, (CALL_A, CALL_B, RETURN)) == UrasResult(1, 0x40000804)
    assert stack_top(MAIN, (RETURN, CALL_B, RETURN)) == UrasResult(0, 0)
    assert stack_top(MAIN, (CALL_A, RETURN)) == UrasResult(1, MAIN)
    assert stack_top(MAIN, (RETURN, CALL_B)) == UrasResult(1, 0x4000100C)
    assert stack_top(MAIN, (RETURN, RETURN, CALL_A)) == UrasResult(1, 0x40000804)
    # Zero is a known address, not the absence of knowledge.
    assert stack_top(0, (NEUTRAL,)) == UrasResult(1, 0)


def test_coroutine_is_pop_then_push_not_neutral_or_push_then_pop():
    coroutine = replace(CALL_B, action=Action.RETURN_AND_CALL)
    assert stack_top(MAIN, (coroutine,)) == UrasResult(1, CALL_B.return_address)
    assert stack_top(MAIN, (CALL_A, coroutine, RETURN)) == UrasResult(1, MAIN)
    assert stack_top(MAIN, (RETURN, coroutine, RETURN)) == UrasResult(0, 0)


def test_concurrent_accept_advance_and_retire_preserve_age_identity():
    model = UrasReference()
    model.advance(RasEvents(accept=CALL_A, main_top=MAIN))
    result = model.advance(RasEvents(accept=CALL_B, advance=True, retire=True, main_top=MAIN))
    assert result == UrasResult(1, CALL_B.return_address)
    assert (model.older, model.younger) == (CALL_A, CALL_B)
    result = model.advance(RasEvents(accept=RETURN, advance=True, retire=True, main_top=MAIN))
    assert result == UrasResult(1, CALL_A.return_address)
    assert (model.older, model.younger) == (CALL_B, RETURN)


def test_correction_and_advance_move_corrected_not_stale_operation():
    model = UrasReference()
    model.advance(RasEvents(accept=CALL_A, main_top=MAIN))
    model.advance(RasEvents(correct_pending=CALL_B, accept=CALL_A, advance=True, main_top=MAIN))
    assert model.older == CALL_B and model.younger is None
    assert model.advance(RasEvents(accept=NEUTRAL, main_top=MAIN)).target == CALL_B.return_address


def test_stall_holds_result_and_retirement_does_not_invent_new_prediction():
    model = UrasReference()
    model.advance(RasEvents(accept=CALL_A, main_top=MAIN))
    expected = model.result
    for main in (0, MAIN, MAIN + 0x100):
        assert model.advance(RasEvents(main_top=main)) == expected
    assert model.advance(RasEvents(advance=True, main_top=MAIN)) == expected
    assert model.advance(RasEvents(retire=True, main_top=MAIN)) == expected
    assert model.older is None
    assert model.advance(RasEvents(accept=NEUTRAL, main_top=MAIN)) == UrasResult(1, MAIN)


def test_redirect_flush_priority_bubble_and_reset_cancel_events():
    model = UrasReference()
    model.advance(RasEvents(accept=CALL_A, main_top=MAIN))
    assert model.advance(RasEvents(redirect=True, accept=CALL_B,
                                   correct_pending=CALL_A, correct_retiring=CALL_B)) == UrasResult(0, 0)
    assert model.younger is None and model.older is None and not model.main_trusted
    assert model.advance(RasEvents(accept=NEUTRAL, main_top=MAIN)) == UrasResult(0, 0)
    assert model.advance(RasEvents(accept=NEUTRAL, main_top=MAIN)) == UrasResult(1, MAIN)
    model.advance(RasEvents(accept=CALL_B, main_top=MAIN))
    assert model.advance(RasEvents(reset=True, accept=CALL_A)) == UrasResult(0, 0)
    assert model.younger is None and model.older is None


@pytest.mark.parametrize('correction_stage,expected', [('pending', UrasResult(0, 0)),
                                                      ('retiring', UrasResult(1, MAIN))])
def test_recovery_authority_is_part_of_the_event_contract(correction_stage, expected):
    model = UrasReference()
    model.advance(RasEvents(redirect=True))
    event = RasEvents(main_top=MAIN, **{f'correct_{correction_stage}': NEUTRAL})
    assert model.advance(event) == expected


def test_call_can_establish_known_top_during_main_recovery():
    model = UrasReference()
    model.advance(RasEvents(redirect=True))
    assert model.advance(RasEvents(accept=CALL_A, main_top=MAIN)) == UrasResult(1, CALL_A.return_address)


@pytest.mark.parametrize('pc,position,target', [(0, 0, 1), (0x7FFFFFFF, 15, 0x80000008),
                                               ((1 << 50) - 1, 15, 8)])
def test_return_address_uses_semantic_halfword_geometry_and_wrap(pc, position, target):
    assert Operation(Action.CALL, pc, position).return_address == target


@pytest.mark.parametrize('actual', [UrasResult(0, 0), UrasResult(1, 0xDEAD)])
def test_wrong_actual_fails_without_reseeding_model(actual):
    checker = UrasSemanticChecker()
    checker.capture_input(SimpleNamespace(tick=0), RasEvents(reset=True))
    checker.capture_output(SimpleNamespace(tick=1), UrasResult(0, 0))
    events = RasEvents(accept=CALL_A, main_top=MAIN)
    checker.capture_input(SimpleNamespace(tick=2), events)
    before = checker.model.state()
    checker.capture_output(SimpleNamespace(tick=3), actual)
    with pytest.raises(ScoreboardMismatch) as caught:
        checker.raise_failure()
    assert 'sequence_id: 3' in str(caught.value) and 'state' in str(caught.value)
    assert checker.model.state() == before
    checker.raise_unobserved_failure()  # No duplicate teardown ERROR.


def test_unusable_target_is_unqualified_and_missing_clock_is_an_error():
    checker = UrasSemanticChecker()
    checker.capture_input(SimpleNamespace(tick=0), RasEvents(reset=True))
    checker.capture_output(SimpleNamespace(tick=1), UrasResult(0, (1 << 50) - 1))
    checker.raise_failure()
    checker.capture_output(SimpleNamespace(tick=3), UrasResult(0, 0))
    with pytest.raises(AssertionError, match='input boundary'):
        checker.raise_failure()


def test_failed_coroutine_gets_reached_but_never_checked_credit():
    coverage = UrasSemanticCoverage()
    checker = UrasSemanticChecker(coverage=coverage)
    checker.capture_input(SimpleNamespace(tick=0), RasEvents(reset=True))
    checker.capture_output(SimpleNamespace(tick=1), UrasResult(0, 0))
    operation = replace(CALL_B, action=Action.RETURN_AND_CALL)
    checker.capture_input(SimpleNamespace(tick=2), RasEvents(accept=operation, main_top=MAIN))
    checker.capture_output(SimpleNamespace(tick=3), UrasResult(1, MAIN))
    with pytest.raises(ScoreboardMismatch):
        checker.raise_failure()
    reached = coverage.groups['reached'].report()['points'][0]
    checked = coverage.groups['checked'].report()['points'][0]
    assert reached['counts']['MRAS.OP.POP_PUSH_ACCEPT'] == 1
    assert checked['counts']['MRAS.OP.POP_PUSH_ACCEPT'] == 0
    provenance, = reached['provenance']['MRAS.OP.POP_PUSH_ACCEPT'].values()
    assert provenance['first']['input_tick'] == 2 and provenance['last']['output_tick'] == 3


def test_suppressed_lower_priority_requests_get_no_acceptance_credit():
    model = UrasReference()
    coroutine = replace(CALL_B, action=Action.RETURN_AND_CALL)
    before = model.state()
    event = RasEvents(redirect=True, accept=coroutine,
                      correct_pending=coroutine, correct_retiring=coroutine)
    assert obligations(event, before, model.advance(event)) == ('MRAS.REDIRECT.FLUSH',)
    event = RasEvents(accept=coroutine, correct_pending=coroutine,
                      correct_retiring=NEUTRAL, main_top=MAIN)
    rules = obligations(event, model.state(), model.advance(event))
    assert rules == ('MRAS.CORRECTION.FLUSH_YOUNGER',)


@pytest.mark.parametrize('factory,error', [
    (lambda: Operation(Action.CALL, -1, 0), ValueError),
    (lambda: Operation(Action.CALL, 1 << 50, 0), ValueError),
    (lambda: Operation(Action.CALL, 0, 16), ValueError),
    (lambda: Operation(2), TypeError),
    (lambda: RasEvents(main_top=-1), ValueError),
    (lambda: RasEvents(advance=1), TypeError),
    (lambda: RasEvents(accept=2), TypeError),
])
def test_invalid_semantic_inputs_are_explicit_errors(factory, error):
    with pytest.raises(error):
        factory()
