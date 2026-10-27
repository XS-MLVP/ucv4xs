"""Program and coverage controls cannot earn hardware coverage credit."""
import ast
from dataclasses import replace
from pathlib import Path

import pytest

from bpuverify.bpu.model.ahead_working_set import expected_branch, strong_counter
from bpuverify.bpu.coverage.working_set_replacement import Coverage
from bpuverify.bpu.model.working_set_replacement import (
    KINDS, Program, geometry, logical_histories,
)



@pytest.mark.parametrize('kinds', KINDS)
def test_five_natural_working_sets_contend_in_Ahead_but_fit_Main_together(kinds):
    program = Program(kinds)
    proof = geometry(program)
    assert proof['total_identities'] == 80 and proof['maximum_Main_residents'] == 1
    assert proof['Ahead_groups'] == 16 and proof['Ahead_identity_counts'] == [5] * 16
    for identities in proof['Ahead_identities'].values():
        assert {row['cohort'] for row in identities} == set(range(5))
        assert len({row['tag'] for row in identities}) == 5
    assert proof['runtime_index_and_replacement_effects_NOT_proved']


@pytest.mark.parametrize('kinds', KINDS)
@pytest.mark.parametrize('cohort', range(5))
def test_each_declared_edge_and_history_has_a_logical_owner(kinds, cohort):
    program = Program(kinds)
    edges = program.edges(cohort)
    assert len(edges) == len({edge.pc for edge in edges}) == 16
    assert tuple(edge.target for edge in edges) == tuple(edge.pc for edge in edges[1:] + edges[:1])
    assert edges[-1].kind == 3
    assert all(edge.pc <= edge.cfi_pc < edge.pc + 8 for edge in edges)
    assert all(logical_histories(program, cohort))
    assert any(edge.kind == 2 for edge in edges) == (kinds == 'mixed')
    assert any(edge.kind == 1 for edge in edges)


@pytest.mark.parametrize('kinds', KINDS)
def test_address_distinctness_is_not_just_a_tag_or_position_relabel(kinds):
    program = Program(kinds)
    pcs = [edge.pc for cohort in range(5) for edge in program.edges(cohort)]
    assert len(pcs) == len(set(pcs)) == 80
    assert program.state()['physical_enumeration'] is False
    assert program.state()['full_FTQ_reachability_proved'] is False


@pytest.mark.parametrize('kind,confidence', ((1, 3), (2, 2), (3, 2)))
def test_strengthening_is_conditional_not_a_generic_taken_reward(kind, confidence):
    edge = replace(Program('mixed').edges(0)[1], kind=kind)
    assert strong_counter(edge) == confidence
    assert expected_branch(edge) == dict(taken=True, position=7, target=edge.target, kind=kind, action=0)


@pytest.mark.parametrize('kinds', KINDS)
def test_reached_does_not_grant_checked_credit(kinds):
    program = Program(kinds)
    coverage = Coverage(program)
    for rule in program.rules:
        coverage.record('reached', rule, source='synthetic-control')
    assert coverage.groups['reached'].coverage == 50
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('status,rule', (('checked', 'unknown'), ('unknown', 'original-discoveries')))
def test_unknown_obligations_cannot_silently_increase_coverage(status, rule):
    with pytest.raises(ValueError, match='unknown branch-identity'):
        Coverage(Program('mixed')).record(status, rule)


@pytest.mark.parametrize('invalid', (True, False, -1, 5, '0', None))
def test_invalid_cohort_is_not_a_new_owner(invalid):
    with pytest.raises(ValueError, match='cohort'):
        Program('conditional').edges(invalid)


@pytest.mark.parametrize('invalid', ('', 'bank0', 'all', None))
def test_program_profiles_are_semantic_not_physical(invalid):
    with pytest.raises(ValueError, match='kind profile'):
        Program(invalid)


def test_dut_case_uses_existing_model_driver_and_monitor_composition():
    source = (Path(__file__).resolve().parents[1] / 'testcase/test_working_set_replacement.py').read_text()
    tree = ast.parse(source)
    forbidden = {'FallingEdge', 'RisingEdge', 'ClockCycles', 'set_', 'get', 'gather', 'create_task', 'sleep'}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not forbidden.intersection(names | attrs)
    assert 'check_ahead_identity_replacement' in names
