"""A focused pure control for the native-discovered guarded lookup omission."""
from dataclasses import replace

import pytest

from suites.frontend.bpu.testbenches.bpu.model.pipeline import Redirect
from suites.frontend.bpu.testbenches.bpu.model.path_history import path_contribution
from suites.frontend.bpu.testbenches.bpu.tests.scoreboard.test_semantic_pipeline import PC, boot, published


@pytest.mark.parametrize('guard', (0, 1))
@pytest.mark.parametrize('sign', (0, 1))
@pytest.mark.parametrize('taken', (False, True))
def test_guarded_redirect_lookup_and_owned_state_use_the_same_virtual_pc(guard, sign, taken):
    model, event = boot()
    source = published(model, event)
    cfi = (guard << 49) + (sign << 48) + PC + 4
    target = PC + 0x100
    event = replace(event, redirect=Redirect(source.history, cfi, target, taken))
    cycle = model.evaluate(event)
    before = model.history.history, model.history.taken_edges, dict(model.history.owned)
    preview = model.lookup_history(event, cycle)
    contribution = ((cfi % 512) * 16) ^ ((target // 2) % 32768)
    expected = ((source.history.history * 4) ^ contribution) % (1 << 532) if taken else source.history.history
    assert preview.history == expected
    assert preview.taken_edges == source.history.taken_edges + int(taken)
    assert (model.history.history, model.history.taken_edges, dict(model.history.owned)) == before
    model.advance(event)
    assert model.history.history == preview.history
    assert model.stages[0].history.folds() == preview.folds()
    assert event.redirect.cfi_pc == cfi


def test_history_algorithm_itself_still_rejects_unprojected_guarded_input():
    with pytest.raises(ValueError, match='halfword PC contract'):
        path_contribution((1 << 49) + PC + 4, PC + 0x100)
