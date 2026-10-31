"""Call-stack meaning, real retirement and source-proof scope stay separate."""
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def test_combined_retirement_has_existing_point_and_paired_native_evidence():
    plan=json.loads((ROOT/'verification_plan.json').read_text())
    point=next(p for p in plan['features'] if p['id']=='BPU-RAS-017')
    catalog=json.loads((ROOT/'docs/functional-events.json').read_text())
    assert len(plan['features'])==363
    assert point['id'] in catalog['events']['ras.retire']['features']['ras']
    assert '不证明完整FTQ' in point['contract']['scope']
    for status in ('reached','checked'):
        assert 'kunminghu_v3.ras.original-commit-action.'+status in point['evidence']['coverage'][status]
    assert all((ROOT/name).is_file() for role in ('model','checks') for name in point['evidence'][role])


def test_semantic_model_does_not_decode_native_receipts_or_read_hardware():
    tree=ast.parse((ROOT/'ras/model/commit_action.py').read_text())
    assert {n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}=={'dataclasses'}
    assert not any(isinstance(n,ast.Import) for n in ast.walk(tree))
    assert 'def receipts(' not in (ROOT/'ras/model/commit_action.py').read_text()


def test_case_has_no_edges_or_scheduler_operations():
    source=(ROOT/'tests/ras/testcase/test_commit_action.py').read_text()
    tree=ast.parse(source)
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','set_','gather','create_task','sleep'}
    assert 'toffee_functional_coverage' not in source and 'from results.' not in source


def test_normal_support_never_imports_experimental_or_test_helpers():
    for role in ('model','monitor','checker','coverage','env','case'):
        source=(ROOT/f'ras/{role}/commit_action.py').read_text()
        assert 'from results.' not in source and 'from tests.' not in source
