"""Adjacent recovery semantics, independent histories and fault discrimination."""
from copy import deepcopy
from dataclasses import replace

import pytest
from toffee import Scoreboard

from suites.frontend.bpu.testbenches.bpu.model.common_history import Value
from suites.frontend.bpu.testbenches.bpu.model.superseding_recovery import SupersedingRecoveryProgram
from suites.frontend.bpu.testbenches.bpu.model.superseding_recovery import PROFILES
from suites.frontend.bpu.testbenches.bpu.tests.scoreboard.test_common_query import Harness


@pytest.mark.parametrize('profile', PROFILES)
def test_two_actual_model_boundaries_apply_distinct_originals_without_adding_prefixes(profile):
    p = SupersedingRecoveryProgram(profile)
    h = Harness()
    older, old = h.learned_loop()
    h.step()
    younger = next(reversed(h.pipeline.published.values()))
    young = h.query.snapshot(younger)
    assert old.owner is not young.owner and old.sequence < young.sequence and old.loop < young.loop < 255
    frozen = deepcopy((old.metadata, young.metadata))
    first, _ = h.step(ready=False, recovery=(young, p.younger))
    assert first.recovered is None and first.lookup == Value(False, 65535, 255)
    assert first.iteration.after == p.iteration(young.loop, younger=True)
    second, _ = h.step(ready=False, recovery=(old, p.older))
    assert second.recovered == p.intermediate and h.query.value == p.intermediate
    assert second.iteration.after == p.iteration(old.loop)
    third, _ = h.step(ready=False)
    assert third.recovered == p.restored and h.query.value == p.restored
    assert h.query.iterations.cursor == p.iteration(old.loop)
    assert (old.metadata, young.metadata) == frozen
    assert h.query.snapshot(older).metadata == old.metadata
    assert h.query.snapshot(younger).metadata == young.metadata


@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('fault', ('drop-final', 'use-younger-iteration', 'reverse-outcomes', 'merge-prefixes'))
def test_semantic_pair_distinguishes_wrong_winner_or_combined_history(profile, fault):
    p = SupersedingRecoveryProgram(profile)
    expected = dict(history=p.restored, iteration=p.iteration(16))
    wrong = dict(expected)
    if fault in ('drop-final', 'reverse-outcomes'):
        wrong = dict(history=p.intermediate, iteration=p.iteration(17, younger=True))
    elif fault == 'use-younger-iteration':
        # A non-loop outcome clears either iteration; its history must also
        # detect a copied younger recovery. Backward recovery exposes age.
        wrong = dict(history=p.intermediate, iteration=p.iteration(17))
    else:
        # Erroneously append the cancelled younger outcome *after* the
        # winning older prefix. Forward/backward bits must follow that
        # actual younger outcome; all-ones plus one is not discriminating.
        younger_backward = int(p.younger.target < 0x40000801)
        wrong['history'] = replace(p.restored, ghr=(2*p.restored.ghr + 1) % 65536,
                                   bw=(2*p.restored.bw + younger_backward) % 256)
    with pytest.raises(AssertionError):
        Scoreboard('superseding-recovery.negative').check(expected=expected, actual=wrong)


@pytest.mark.parametrize('count', (0, 255, -1, True, 256))
def test_the_program_does_not_use_a_saturated_or_invalid_original_to_hide_age(count):
    with pytest.raises(ValueError):
        SupersedingRecoveryProgram(PROFILES[0]).iteration(count)
