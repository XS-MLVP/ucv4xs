"""Source-owned stack semantics must not become sampled-input verification."""
import ast
import json
from pathlib import Path

import pytest

from suites.frontend.bpu.testbenches.bpu.coverage.owned_return_stack import lifetime_coverage
from suites.frontend.bpu.testbenches.bpu.model.owned_return_stack import PROGRAMS
from suites.frontend.bpu.testbenches.bpu.model.owned_return_stack import OBLIGATIONS

ROOT=__import__('suites.frontend.bpu', fromlist=['ROOT']).ROOT


def test_only_semantic_lifetimes_are_crossed_no_bank_or_physical_depth_axis():
    contract=json.loads((ROOT/'docs/spec/verification/contracts/owned-return-stack-contract-20261020.json').read_text())
    assert len(PROGRAMS)==6 and len(OBLIGATIONS)==44
    assert contract['bounded_native_programs_defined_before_execution']['required_obligations']==44
    for status in ('reached','checked'):
        group=lifetime_coverage(status)
        assert set(group.report()['points'][0]['counts'])==set(OBLIGATIONS)
        assert group.coverage==0


@pytest.mark.parametrize('filename',('model/return_stack_sources.py','model/owned_return_stack.py'))
def test_models_import_only_semantic_algorithms_and_value_types(filename):
    source=(ROOT/'testbenches/bpu'/filename).read_text()
    tree=ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node,(ast.ImportFrom,ast.Import)):
            modules=([node.module] if isinstance(node,ast.ImportFrom) else [x.name for x in node.names])
            assert all(m=='dataclasses' or '.model.' in m for m in modules)
    assert not any(word in source for word in ('memory_signal','from tests.','from results.','xspcomm','Set('))


def test_thin_pytest_case_has_no_pins_wait_cycles_or_scheduler_plumbing():
    source=(ROOT/'testbenches/bpu/tests/testcase/test_owned_return_stack.py').read_text()
    tree=ast.parse(source)
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','set_','get_set','gather','create_task','sleep'}
    assert 'from results.' not in source and 'from tests.' not in source
