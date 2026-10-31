"""A planned history switch is not a reached hardware event."""
from types import SimpleNamespace

import pytest

from suites.frontend.bpu.tage.case.semantic import POSITION, PC, PROFILES, accepted_learning, pipelined_readback
from suites.frontend.bpu.tage.coverage.semantic import SemanticCoverage
from suites.frontend.bpu.tage.model.semantic import Branch, Context, Feedback, coordinate


def test_four_profiles_are_distinguishing_in_every_table_not_a_physical_sweep():
    for table in range(4):
        cells = {coordinate(PC, Context.from_recent(history), table) for history, _ in PROFILES}
        assert len(cells) == len(PROFILES) == 4
        assert {bank for bank, _, _ in cells} == {0}


@pytest.mark.parametrize('qualified', (False, True))
async def test_training_failure_preserves_only_observed_qualified_reached_credit(qualified):
    coverage = SemanticCoverage()
    request = Feedback(PC, Context(), (Branch(POSITION, True, 1, True, qualified),))
    async def train(_):
        agent.reference.accepted_feedback.append((2, request))
        raise AssertionError('learning/output comparison failed')
    agent = SimpleNamespace(reference=SimpleNamespace(input_tick=0, accepted_feedback=[]), train=train)
    with pytest.raises(AssertionError, match='learning/output comparison'):
        await accepted_learning(agent, 0, 1, SimpleNamespace(meta={}), coverage, allocate=True)
    assert coverage.groups['reached'].coverage == (25 if qualified else 0)
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('accepted_count', (0, 1, 4, 8))
async def test_pipeline_failure_never_credits_planned_or_unchecked_restoration(accepted_count):
    coverage = SemanticCoverage()
    submitted = []
    def submit(*args, **kwargs):
        slot = len(submitted)
        accepted = SimpleNamespace(tick=2 * slot) if slot < accepted_count else None
        transfer = SimpleNamespace(accepted_event=accepted)
        submitted.append(transfer)
        return transfer
    async def drain():
        raise AssertionError('independent output mismatch')
    agent = SimpleNamespace(submit_predict=submit, drain_predictions=drain)
    with pytest.raises(AssertionError, match='independent output mismatch'):
        await pipelined_readback(agent, coverage)
    assert coverage.groups['reached'].coverage == (50 if accepted_count == 8 else 0)
    assert coverage.groups['checked'].coverage == 0
