"""Semantic contracts retain old evidence; physical copies are not new points."""
import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FAMILIES = (
    ('utage', 'query_cohort', 'query-cohort-turnover', 54, ('006', '015', '022')),
    ('utage', 'query_identity', 'complete-index-alias', 44, ('023', '024')),
    ('utage', 'selective_protection', 'selective-protection-alias', 60, ('021', '023', '024')),
    ('bpu', 'working_set_replacement', 'ahead-identity-replacement', 20, ('100',)),
)


@pytest.mark.parametrize('dut,family,instance,denominator,features', FAMILIES)
def test_semantic_family_has_its_own_complete_paired_schema(dut, family, instance, denominator, features):
    factory = importlib.import_module(f'bpuverify.{dut}.coverage.{family}').lifetime_coverage
    reached, checked = (factory(status) for status in ('reached', 'checked'))
    assert reached.definition.digest == checked.definition.digest
    assert tuple(reached.definition.points[0].bins) == tuple(checked.definition.points[0].bins)
    assert len(checked.definition.points[0].bins) == denominator
    assert reached.instance == f'kunminghu_v3.{dut}.{instance}.reached'
    assert checked.instance == f'kunminghu_v3.{dut}.{instance}.checked'
    assert reached.coverage == checked.coverage == 0


@pytest.mark.parametrize('dut,family,instance,denominator,features', FAMILIES)
def test_new_semantic_obligations_extend_existing_points_without_old_PASS_credit(dut, family, instance, denominator, features):
    plan = json.loads((ROOT / 'verification_plan.json').read_text())
    assert len(plan['features']) == 363
    contract = json.loads((ROOT / f'docs/{dut}-{family.replace("_", "-")}-contract.json').read_text())
    assert all(contract[key].strip() for key in ('event', 'owner', 'effect', 'preservation', 'scope'))
    for suffix in features:
        identity = ('BPU-UTAGE-' if dut == 'utage' else 'BPU-INT-') + suffix
        point = next(row for row in plan['features'] if row['id'] == identity)
        assert point['metadata']['owned_state_prior_contract'] != point['contract']
        assert any(row['family'] == family for row in point['metadata']['owned_state_semantic_extensions'])
        for status in ('reached', 'checked'):
            assert f'kunminghu_v3.{dut}.{instance}.{status}' in point['evidence']['coverage'][status]
        assert all((ROOT / path).is_file() for role in ('model', 'checks') for path in point['evidence'][role])


def test_old_unpaired_high_index_evidence_is_retained_without_fabricated_reached():
    plan = json.loads((ROOT / 'verification_plan.json').read_text())
    point = next(row for row in plan['features'] if row['id'] == 'BPU-UTAGE-023')
    legacy = point['metadata']['legacy_coverage_bindings']
    assert legacy == dict(checked=['kunminghu_v3.utage.split_context_useful'],
                         fabricated_reached=False, retained_group_names_and_denominators=True)
    assert legacy['checked'][0] not in point['evidence']['coverage']['reached']


@pytest.mark.parametrize('dut,family,instance,denominator,features', FAMILIES)
def test_testcases_reuse_environment_instead_of_pin_or_scheduler_operations(dut, family, instance, denominator, features):
    import ast
    source = (ROOT / f'tests/{dut}/testcase/test_{family}.py').read_text()
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not names & {'FallingEdge', 'RisingEdge', 'ClockCycles', 'set_', 'get', 'gather', 'create_task', 'sleep'}
    assert 'from results.' not in source
    assert 'toffee_functional_coverage' not in source
