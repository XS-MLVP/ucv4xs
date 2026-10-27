"""Stimulus qualification controls; no DUT or hardware coverage credit."""
from dataclasses import replace

import pytest

from bpuverify.bpu.env.main_service import branch
from bpuverify.bpu.model.selection import Branch, Kind
from bpuverify.bpu.model.main_dynamic_target import (
    Program, PHASES, ORIGINS, PC, EARLIER, LATER, FALLBACK,
    LATER_TARGET, STREAM_PC, VERSIONS, qualified_feedback)




@pytest.mark.parametrize('phase', PHASES)
@pytest.mark.parametrize('origin', ORIGINS)
def test_all_versions_are_the_same_indirect_instruction(phase, origin):
    program = Program(phase, origin)
    effects = [program.effect(version) for version in range(3)]
    assert all(effect['kind'] == 3 and effect['position'] == EARLIER and effect['carry'] == 0 for effect in effects)
    assert len({effect['offset'] for effect in effects}) == 3
    assert program.direction()['values'] == {'0': 2}


def path():
    return (branch(LATER, LATER_TARGET, 1, taken=False), branch(FALLBACK, STREAM_PC, 3))


def test_first_mispredicted_conditional_excludes_later_resolved_branch():
    prediction = Branch(LATER, LATER_TARGET, Kind.CONDITIONAL)
    qualified = qualified_feedback(prediction, path())
    assert len(qualified) == 1 and qualified[0].position == LATER and qualified[0].mispredict == 1


def test_later_missing_indirect_can_be_learned_after_correct_nt_conditional():
    prediction = Branch(15, PC + 16, Kind.NONE, taken=False)
    qualified = qualified_feedback(prediction, path())
    assert tuple((b.position, b.mispredict) for b in qualified) == ((LATER, 0), (FALLBACK, 1))


def test_correct_original_path_does_not_invent_an_entry_correction():
    prediction = Branch(FALLBACK, STREAM_PC, Kind.INDIRECT)
    assert tuple(b.mispredict for b in qualified_feedback(prediction, path())) == (0, 0)


@pytest.mark.parametrize('version', (1, 2))
def test_dynamic_target_mismatch_qualifies_the_same_indirect_instruction(version):
    prediction = Branch(EARLIER, VERSIONS[0], Kind.INDIRECT)
    qualified = qualified_feedback(prediction, (branch(EARLIER, VERSIONS[version], 3),))
    assert len(qualified) == 1 and qualified[0].mispredict == 1 and qualified[0].branch_type == 3


@pytest.mark.parametrize('fault', ('empty', 'duplicate', 'unordered', 'early-taken', 'no-taken', 'phantom'))
def test_unsupported_execution_path_is_rejected_instead_of_claiming_parent_legality(fault):
    prediction = Branch(FALLBACK, STREAM_PC, Kind.INDIRECT)
    outcomes = path()
    if fault == 'empty': outcomes = ()
    elif fault == 'duplicate': outcomes = (outcomes[0], replace(outcomes[1], position=LATER))
    elif fault == 'unordered': outcomes = tuple(reversed(outcomes))
    elif fault == 'early-taken': outcomes = (replace(outcomes[0], taken=1), outcomes[1])
    elif fault == 'no-taken': outcomes = tuple(replace(b, taken=0) for b in outcomes)
    elif fault == 'phantom': prediction = Branch(EARLIER, PC + 0x400, Kind.INDIRECT)
    with pytest.raises(ValueError):
        qualified_feedback(prediction, outcomes)
