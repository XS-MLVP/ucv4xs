"""Semantic contracts retain old evidence; physical copies are not new points."""
import importlib
import json
from pathlib import Path

import pytest

ROOT = __import__('suites.frontend.bpu', fromlist=['ROOT']).ROOT
FAMILIES = (
    ('utage', 'query_cohort', 'query-cohort-turnover', 54, ('006', '015', '022')),
    ('utage', 'query_identity', 'complete-index-alias', 44, ('023', '024')),
    ('utage', 'selective_protection', 'selective-protection-alias', 60, ('021', '023', '024')),
    ('bpu', 'working_set_replacement', 'ahead-identity-replacement', 20, ('100',)),
)


@pytest.mark.parametrize('dut,family,instance,denominator,features', FAMILIES)
def test_semantic_family_has_its_own_complete_paired_schema(dut, family, instance, denominator, features):
    factory = importlib.import_module(f'suites.frontend.bpu.testbenches.{dut}.coverage.{family}').lifetime_coverage
    reached, checked = (factory(status) for status in ('reached', 'checked'))
    assert reached.definition.digest == checked.definition.digest
    assert tuple(reached.definition.points[0].bins) == tuple(checked.definition.points[0].bins)
    assert len(checked.definition.points[0].bins) == denominator
    assert reached.instance == f'kunminghu_v3.{dut}.{instance}.reached'
    assert checked.instance == f'kunminghu_v3.{dut}.{instance}.checked'
    assert reached.coverage == checked.coverage == 0


@pytest.mark.parametrize('dut,family,instance,denominator,features', FAMILIES)
def test_new_semantic_obligations_extend_existing_points_without_old_PASS_credit(dut, family, instance, denominator, features):
    contract = json.loads((ROOT / f'docs/spec/verification/contracts/{dut}-{family.replace("_", "-")}-contract.json').read_text())
    assert all(contract[key].strip() for key in ('event', 'owner', 'effect', 'preservation', 'scope'))


@pytest.mark.parametrize('dut,family,instance,denominator,features', FAMILIES)
def test_testcases_reuse_environment_instead_of_pin_or_scheduler_operations(dut, family, instance, denominator, features):
    import ast
    source = (ROOT / f'testbenches/{dut}/tests/testcase/test_{family}.py').read_text()
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not names & {'FallingEdge', 'RisingEdge', 'ClockCycles', 'set_', 'get', 'gather', 'create_task', 'sleep'}
    assert 'from results.' not in source
    assert 'toffee_functional_coverage' not in source
