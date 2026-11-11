"""Call-stack meaning, real retirement and source-proof scope stay separate."""
import ast
import json
from pathlib import Path

ROOT=__import__('suites.frontend.bpu', fromlist=['ROOT']).ROOT


def test_combined_retirement_has_existing_point_and_paired_native_evidence():
    catalog=json.loads((ROOT/'docs/spec/verification/functional/functional-events.json').read_text())
    assert 'BPU-RAS-017' in catalog['events']['ras.retire']['features']['ras']


def test_semantic_model_does_not_decode_native_receipts_or_read_hardware():
    tree=ast.parse((ROOT/'testbenches/ras/model/commit_action.py').read_text())
    assert {n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}=={'dataclasses'}
    assert not any(isinstance(n,ast.Import) for n in ast.walk(tree))
    assert 'def receipts(' not in (ROOT/'testbenches/ras/model/commit_action.py').read_text()


def test_case_has_no_edges_or_scheduler_operations():
    source=(ROOT/'testbenches/ras/tests/testcase/test_commit_action.py').read_text()
    tree=ast.parse(source)
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','set_','gather','create_task','sleep'}
    assert 'toffee_functional_coverage' not in source and 'from results.' not in source


def test_normal_support_never_imports_experimental_or_test_helpers():
    for role in ('model','env/monitor','checker','coverage','tests/scenarios/lifetimes','tests/scenarios'):
        source=(ROOT/f'testbenches/ras/{role}/commit_action.py').read_text()
        assert 'from results.' not in source and 'from tests.' not in source
