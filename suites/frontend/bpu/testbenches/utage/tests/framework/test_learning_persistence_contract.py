"""Refine existing pending semantics without broadening useful initialization."""
import ast
import json
from pathlib import Path
import pytest

ROOT=__import__('suites.frontend.bpu', fromlist=['ROOT']).ROOT


@pytest.mark.parametrize('identity',('BPU-UTAGE-015','BPU-UTAGE-016'))
def test_pending_version_ownership_has_explicit_existing_point_and_paired_proof(identity):
    catalog=json.loads((ROOT/'docs/spec/verification/functional/functional-events.json').read_text())
    assert identity in catalog['events']['pending.rewrite']['features']['utage']


def test_useful_initialization_is_not_redefined_as_an_entire_persistence_lifetime():
    catalog=json.loads((ROOT/'docs/spec/verification/functional/functional-events.json').read_text())
    assert 'BPU-UTAGE-020' not in catalog['events']['pending.rewrite']['features']['utage']


def test_case_reuses_semantic_scenario_and_has_no_edges_or_scheduler_operations():
    source=(ROOT/'testbenches/utage/tests/testcase/test_learning_persistence.py').read_text()
    tree=ast.parse(source)
    names={node.id for node in ast.walk(tree) if isinstance(node,ast.Name)}
    names|={node.attr for node in ast.walk(tree) if isinstance(node,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','set_','get','gather','create_task','sleep'}
    assert 'from results.' not in source and 'toffee_functional_coverage' not in source
    assert "@pytest.mark.feature('BPU-UTAGE-020')" not in source
