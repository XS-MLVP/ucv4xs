"""Optional A0 context must not replace the previous A1 logical request."""
from types import SimpleNamespace

import pytest

from bpuverify.common.model.folded_history import folded_history_values
from bpuverify.utage.agent.main import UtageAgent
from bpuverify.utage.model.split_context import contexts, neighbor_context
from bpuverify.utage.transaction.types import UtageLookup


def test_same_context_defaults_preserve_legacy_positional_construction():
    request = UtageLookup(123, 6, 1, None, None, 456, None)
    assert request.read_pc == request.pc == 123
    assert request.read_history == request.folded_history == 456


def test_explicit_zero_context_is_not_replaced_by_default_pc_or_history():
    request = UtageLookup(123, 6, 1, folded_history=456, index_pc=0, index_history=0)
    assert request.read_pc == request.read_history == 0


@pytest.mark.parametrize('which', ('index_pc', 'index_history'))
@pytest.mark.parametrize('value', (-1, True, 1.5, '12'))
def test_invalid_context_is_rejected_before_any_driver_state(which, value):
    with pytest.raises(ValueError, match=which):
        UtageLookup(0x40010006, 6, 0, **{which: value})


@pytest.mark.parametrize('which,value', (('index_pc', 1 << 49), ('index_history', 1 << 532)))
def test_oversized_context_is_rejected(which, value):
    with pytest.raises(ValueError, match=which):
        UtageLookup(0x40010006, 6, 0, **{which: value})


def test_index_and_tag_history_are_independently_staged_for_adjacent_requests():
    profiles = contexts()
    requests = [UtageLookup(profile.pc, 6, int(i == 1), folded_history=profile.tag_history,
        index_pc=profile.index_pc, index_history=profile.index_history)
        for i, profile in enumerate(profiles.values())]
    agent = SimpleNamespace(_last_a0_lookup=None, _history_count=33,
        _ahead_btb=lambda request: dict(fastPositions=(request.position, request.base_taken)))
    first = UtageAgent._encode_lookup(agent, requests[0])
    second = UtageAgent._encode_lookup(agent, requests[1])
    assert first['start_pc'] == requests[0].index_pc != first['new_start_pc'] == requests[0].pc
    assert second['start_pc'] == requests[1].index_pc
    assert second['normal_history'] == folded_history_values(requests[1].index_history, 33)
    assert second['new_start_pc'] == requests[0].pc
    assert second['s1_history'] == folded_history_values(requests[0].folded_history, 33)
    assert second['s1_history'] != second['normal_history']
    assert second['ahead_btb']['fastPositions'] == (6, 0)
    assert second['override_history'] == folded_history_values(requests[1].folded_history, 33)
    assert agent._last_a0_lookup is requests[1]


def test_geometry_agrees_with_independent_integrated_full_history_and_pipeline_model():
    from bpuverify.bpu.model.bypass.sparse import phase_contexts, joint_proof
    program = dict(nodes=(0x40010006, 0x40010016, 0x40010080, 0x400101e2), pc=0x40010006)
    program['positive'] = phase_contexts(program, True)
    program['negative'] = phase_contexts(program, False)
    assert joint_proof(program) == 1104
    for phase, profile in contexts().items():
        integrated = program[phase][program['pc']]
        assert profile.pc == program['pc']
        assert profile.index_pc == integrated['index_pc']
        assert profile.indices == integrated['indices']
        assert profile.tag_history == integrated['tag_history'] & ((1 << 532) - 1)
        assert profile.index_history == program[phase][program['nodes'][2]]['history'] & ((1 << 532) - 1)
        assert profile.lower_tag == integrated['tags'][0] == 112


def test_neighbor_geometry_is_distinct_in_both_pc_and_physical_index():
    neighbor = neighbor_context()
    assert neighbor.pc != contexts()['positive'].pc
    assert neighbor.index_pc != neighbor.pc
    assert neighbor.indices == (46, 366)
    assert neighbor.lower_tag == 116 < 256


@pytest.mark.parametrize('kwargs', (
    dict(index_pc=-1), dict(index_pc=1 << 49), dict(index_history=-1),
    dict(index_history=1 << 532), dict(folded_history=1 << 532, index_history=0),
))
def test_invalid_submit_does_not_queue_or_change_a0_context(kwargs):
    submitted = []
    previous = object()
    agent = SimpleNamespace(_last_a0_lookup=previous, _history_count=33, _result_tasks=set(),
        _ahead_btb=lambda request: None,
        prediction_scoreboard=SimpleNamespace(submit=lambda *args, **kwargs: submitted.append(args)))
    with pytest.raises(ValueError):
        UtageAgent.submit_predict(agent, 0x40010006, 6, 0, **kwargs)
    assert not submitted
    assert agent._last_a0_lookup is previous
    assert not agent._result_tasks
