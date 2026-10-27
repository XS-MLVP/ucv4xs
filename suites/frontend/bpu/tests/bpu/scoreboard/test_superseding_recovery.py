"""Adjacent recovery semantics, independent histories and fault discrimination."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest
from toffee import Scoreboard

from bpuverify.bpu.model.common_history import Value
from bpuverify.bpu.model.superseding_recovery import SupersedingRecoveryProgram, PROFILES
from tests.bpu.scoreboard.test_common_query import Harness


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
    assert first.recovered is None and first.lookup == Value(False, 255, 15)
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
        wrong['history'] = replace(p.restored, ghr=(2*p.restored.ghr + 1) % 256,
                                   bw=(2*p.restored.bw + younger_backward) % 16)
    with pytest.raises(AssertionError):
        Scoreboard('superseding-recovery.negative').check(expected=expected, actual=wrong)


@pytest.mark.parametrize('count', (0, 255, -1, True, 256))
def test_the_program_does_not_use_a_saturated_or_invalid_original_to_hide_age(count):
    with pytest.raises(ValueError):
        SupersedingRecoveryProgram(PROFILES[0]).iteration(count)


@pytest.mark.parametrize('identity', ('BPU-INT-034', 'BPU-INT-043', 'BPU-INT-094', 'BPU-INT-099'))
def test_pair_requirement_has_its_own_paired_evidence_and_preserves_the_old_scope(identity):
    plan = json.loads(Path('verification_plan.json').read_text())
    point = next(v for v in plan['features'] if v['id'] == identity)
    requirement = point['metadata']['superseding_recovery_evidence']
    assert requirement['programs'] == 4 and requirement['obligations'] == 32
    assert requirement['old_single_recovery_PASS_is_not_adjacent_pair_proof']
    assert not requirement['full_FTQ_lifetime_proved'] and requirement['old_contract_scope_unchanged']
    assert requirement['case'] in point['evidence']['checks']
    for status in ('reached', 'checked'):
        assert 'kunminghu_v3.bpu.superseding-recovery.'+status in point['evidence']['coverage'][status]
