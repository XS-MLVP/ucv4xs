"""Refine existing pending semantics without broadening useful initialization."""
import ast
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('identity',('BPU-UTAGE-015','BPU-UTAGE-016'))
def test_pending_version_ownership_has_explicit_existing_point_and_paired_proof(identity):
    plan=json.loads((ROOT/'verification_plan.json').read_text())
    catalog=json.loads((ROOT/'docs/functional-events.json').read_text())
    point=next(row for row in plan['features'] if row['id']==identity)
    assert len(plan['features'])==363
    assert 'pending.rewrite' in point['metadata']['semantic_event_refs']
    assert identity in catalog['events']['pending.rewrite']['features']['utage']
    assert point['contract']!=point['metadata']['previous_pre_learning_persistence_contract']
    assert point['metadata']['learning_persistence_qualification']['old_PASS_is_not_native_service_proof']
    for status in ('reached','checked'):
        assert 'kunminghu_v3.utage.learning-persistence.'+status in point['evidence']['coverage'][status]
    assert all((ROOT/path).is_file() for role in ('model','checks') for path in point['evidence'][role])


def test_useful_initialization_is_not_redefined_as_an_entire_persistence_lifetime():
    plan=json.loads((ROOT/'verification_plan.json').read_text())
    catalog=json.loads((ROOT/'docs/functional-events.json').read_text())
    point=next(row for row in plan['features'] if row['id']=='BPU-UTAGE-020')
    assert point['title']=='新预测身份分配时初始化自身的替换保护，不污染其他身份'
    assert 'pending.rewrite' not in point['metadata']['semantic_event_refs']
    assert point['id'] not in catalog['events']['pending.rewrite']['features']['utage']
    assert not any('learning_persistence' in path for role in ('model','checks') for path in point['evidence'][role])


def test_case_reuses_semantic_scenario_and_has_no_edges_or_scheduler_operations():
    source=(ROOT/'tests/utage/testcase/test_learning_persistence.py').read_text()
    tree=ast.parse(source)
    names={node.id for node in ast.walk(tree) if isinstance(node,ast.Name)}
    names|={node.attr for node in ast.walk(tree) if isinstance(node,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','set_','get','gather','create_task','sleep'}
    assert 'from results.' not in source and 'toffee_functional_coverage' not in source
    assert "@pytest.mark.feature('BPU-UTAGE-020')" not in source
