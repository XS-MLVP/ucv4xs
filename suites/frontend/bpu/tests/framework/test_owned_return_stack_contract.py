"""Source-owned stack semantics must not become sampled-input verification."""
import ast
import json
from pathlib import Path

import pytest

from bpuverify.bpu.coverage.owned_return_stack import lifetime_coverage
from bpuverify.bpu.model.owned_return_stack import PROGRAMS,OBLIGATIONS

ROOT=Path(__file__).resolve().parents[2]


def test_existing_features_keep_their_contracts_and_bind_the_new_lifetime_schema():
    plan=json.loads((ROOT/'verification_plan.json').read_text())
    assert len(plan['features'])==363
    for identity in ('BPU-INT-008','BPU-INT-052','BPU-INT-080','BPU-INT-081'):
        point=next(f for f in plan['features'] if f['id']==identity)
        assert point['contract']['event'] and point['contract']['owner']
        assert point['metadata']['autonomous_return_stack_validation']['contract']=='docs/owned-return-stack-contract-20261020.json'
        for status in ('reached','checked'):
            assert lifetime_coverage(status).instance in point['evidence']['coverage'][status]


def test_only_semantic_lifetimes_are_crossed_no_bank_or_physical_depth_axis():
    contract=json.loads((ROOT/'docs/owned-return-stack-contract-20261020.json').read_text())
    assert len(PROGRAMS)==6 and len(OBLIGATIONS)==44
    assert contract['bounded_native_programs_defined_before_execution']['required_obligations']==44
    for status in ('reached','checked'):
        group=lifetime_coverage(status)
        assert set(group.report()['points'][0]['counts'])==set(OBLIGATIONS)
        assert group.coverage==0


@pytest.mark.parametrize('filename',('model/return_stack_sources.py','model/owned_return_stack.py'))
def test_models_import_only_semantic_algorithms_and_value_types(filename):
    source=(ROOT/'bpuverify/bpu'/filename).read_text()
    tree=ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node,(ast.ImportFrom,ast.Import)):
            modules=([node.module] if isinstance(node,ast.ImportFrom) else [x.name for x in node.names])
            assert all(m=='dataclasses' or '.model.' in m for m in modules)
    assert not any(word in source for word in ('memory_signal','from tests.','from results.','xspcomm','Set('))


def test_thin_pytest_case_has_no_pins_wait_cycles_or_scheduler_plumbing():
    source=(ROOT/'tests/bpu/testcase/test_owned_return_stack.py').read_text()
    tree=ast.parse(source)
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','set_','get_set','gather','create_task','sleep'}
    assert 'from results.' not in source and 'from tests.' not in source
