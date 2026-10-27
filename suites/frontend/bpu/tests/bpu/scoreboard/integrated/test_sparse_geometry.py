"""Sparse input contracts do not use selected hardware payloads as filters."""
from copy import deepcopy

import pytest

from bpuverify.bpu.model.bypass.sparse import recipe, phase_contexts, joint_proof, qualifies_return_request
from bpuverify.bpu.model.phr.model import folds


@pytest.mark.parametrize('which', ('old', 'second'))
def test_full_history_and_index_pipeline_agree_across_direction_changes(which):
    plan = recipe()
    assert plan['MainBTB_residents'] == 10
    assert plan['maximum_MainBTB_residents_per_group'] == 1
    assert joint_proof(plan[which]) == 224
    context = plan[which]['positive'][plan[which]['pc']]
    assert context['index_pc'] != plan[which]['pc']
    assert context['index_pc'] == plan[which]['nodes'][3]


def test_programs_and_direction_phases_have_distinct_upper_input_keys():
    plan = recipe()
    contexts = [plan[p][phase][plan[p]['pc']] for p in ('old', 'second') for phase in ('positive', 'negative')]
    assert len({context['indices'][1] for context in contexts}) == 4
    assert len({context['indices'][0] for context in contexts}) == 2
    assert [context['tags'] for context in contexts] == [(248, 125), (248, 75), (222, 67), (222, 117)]
    assert all(context['tag_history'] != context['history'] for context in contexts)


def test_high_lower_index_does_not_imply_a_high_prediction_tag_when_pcs_differ():
    # Input-only counterexample to the SAME-PC tag-width argument being used
    # as a global reachability proof. This does not claim a DUT useful update.
    program = dict(nodes=(0x40010006, 0x40010016, 0x40010080, 0x400101e2), pc=0x40010006)
    program['positive'] = phase_contexts(program, True)
    program['negative'] = phase_contexts(program, False)
    assert joint_proof(program) == 224
    for phase in ('positive', 'negative'):
        context = program[phase][program['pc']]
        assert context['indices'][0] == 462
        assert context['tags'][0] == 208 < 256
        assert context['index_pc'] != program['pc']


@pytest.mark.parametrize('fault', (None, 'stale', 'index_pc', 'index_folds', 'indices',
                                  'tag_pc', 'tag_folds', 'redirect_valid', 's2_override', 's3_override'))
@pytest.mark.parametrize('phase', ('positive', 'negative'))
def test_return_qualification_separates_index_and_tag_ancestry(fault, phase):
    program = recipe()['old']
    context = program[phase][program['pc']]
    token = dict(source_tick=11, pc=context['index_pc'], folds=context['index_folds'], indices=context['indices'])
    physical = dict(new_pc=program['pc'], s1_folds=tuple(folds(context['tag_history'])[i] for i in (1, 2, 7, 8)),
                    redirect_valid=0, s2_override=0, s3_override=0)
    before = deepcopy((token, physical))
    if fault == 'stale': token['source_tick'] = 10
    elif fault == 'index_pc': token['pc'] = program['pc']
    elif fault == 'index_folds': token['folds'] = (0, 0)
    elif fault == 'indices': token['indices'] = (0, 0)
    elif fault == 'tag_pc': physical['new_pc'] = context['index_pc']
    elif fault == 'tag_folds': physical['s1_folds'] = (0, 0, 0, 0)
    elif fault is not None: physical[fault] = 1
    assert qualifies_return_request(token, physical, program=program, after_tick=10, phase=phase) == (fault is None)
    if fault is None:
        assert (token, physical) == before
