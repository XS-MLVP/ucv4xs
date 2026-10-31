"""Reset/priority/reliability properties and complete-life coverage controls."""
from dataclasses import replace
import pytest
from toffee import Scoreboard, ScoreboardMismatch
from suites.frontend.bpu.ubtb.checker.semantic import prediction_value
from suites.frontend.bpu.ubtb.model.semantic import UbtbEvents, UbtbReference
from suites.frontend.bpu.ubtb.transaction.types import PredictRequest
from suites.frontend.bpu.ubtb.model.reset_lifetime import Program, PROFILES, RULES
from suites.frontend.bpu.ubtb.coverage.reset_lifetime import Coverage
from suites.frontend.bpu.ubtb.checker.reset_lifetime import expected


def teach(model, feedback):
    model.advance(UbtbEvents(fast_feedback=feedback))
    model.advance(UbtbEvents())


@pytest.mark.parametrize('profile', PROFILES)
def test_existing_reference_resets_old_learning_and_restarts_new_reliability(profile):
    p, model = Program(profile), UbtbReference()
    for branch in p.old:
        teach(model, branch)
    for _ in range(2):
        teach(model, replace(p.old[0], taken=0))
    assert sorted(e.confidence for e in model.entries if e.confidence) == [1, 3, 3]
    fast = p.fast if profile in ('fast-learning', 'competing-learning') else None
    resolved = p.resolve if profile in ('resolve-learning', 'competing-learning') else None
    model.advance(UbtbEvents(fast_feedback=fast, resolve_feedback=resolved))
    assert (None if model.learning is None else model.learning.feedback) == p.selected
    model.advance(UbtbEvents(reset=True))
    assert model.learning is model.lookup is None
    assert all(e.confidence == 0 for e in model.entries)
    for pc in p.old_pcs:
        model.advance(UbtbEvents(predict=PredictRequest(pc)))
        assert not model.prediction().valid
    teach(model, p.new[0])
    for errors in range(1, 4):
        teach(model, replace(p.new[0], taken=0))
        model.advance(UbtbEvents(predict=PredictRequest(p.new[0].pc)))
        assert bool(model.prediction().valid) == (errors < 3)


@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('missing', RULES)
def test_no_missing_reset_obligation_can_receive_checked_credit(profile, missing):
    coverage = Coverage(Program(profile))
    for rule in RULES:
        if rule != missing:
            coverage.reach(rule)
    with pytest.raises(AssertionError, match='incomplete'):
        coverage.finish()
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('profile', PROFILES)
def test_full_reset_lifetime_earns_checked_once(profile):
    coverage = Coverage(Program(profile))
    for rule in RULES:
        coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage == 25
    with pytest.raises(AssertionError):
        coverage.finish()
    with pytest.raises(ValueError):
        coverage.reach(RULES[0])


@pytest.mark.parametrize('fault', ('target', 'position', 'branch_type', 'ras_action', 'valid', 'taken'))
def test_valid_new_prediction_comparison_rejects_every_corrupted_defined_field(fault):
    prediction = expected(Program('committed').new[0])
    damaged = replace(prediction, **{fault: getattr(prediction, fault) ^ 1})
    board = Scoreboard('ubtb.reset-consumer-control')
    with pytest.raises(ScoreboardMismatch):
        board.check(expected=prediction_value(prediction), actual=prediction_value(damaged))


@pytest.mark.parametrize('profile', ('', 'ready-only', 'slot-0', None, 0, True))
def test_unqualified_profile_is_rejected(profile):
    with pytest.raises(ValueError):
        Program(profile)
