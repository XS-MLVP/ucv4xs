"""Miss payload transport is not direction-learning permission."""
import ast
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_existing_point_gains_integrated_evidence_without_claiming_complete_FTQ():
    plan=json.loads((ROOT/'verification_plan.json').read_text())
    point=next(row for row in plan['features'] if row['id']=='BPU-MBTB-027')
    event=json.loads((ROOT/'docs/functional-events.json').read_text())['events']['feedback.unmatched-owner']
    assert len(plan['features'])==363
    assert point['id'] in event['features']['mbtb']
    assert '不证明完整FTQ可达性' in point['contract']['scope']
    for status in ('reached','checked'):
        assert 'kunminghu_v3.bpu.miss-authority.'+status in point['evidence']['coverage'][status]
    assert all((ROOT/path).is_file() for role in ('model','checks') for path in point['evidence'][role])


def test_thin_case_has_no_edges_or_scheduler_and_does_not_claim_working_set_credit():
    source=(ROOT/'tests/bpu/testcase/test_miss_authority.py').read_text()
    tree=ast.parse(source)
    names={node.id for node in ast.walk(tree) if isinstance(node,ast.Name)}
    names|={node.attr for node in ast.walk(tree) if isinstance(node,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','set_','get','gather','create_task','sleep'}
    assert "@pytest.mark.feature('BPU-INT-100')" not in source
    assert 'from results.' not in source and 'toffee_functional_coverage' not in source


@pytest.mark.parametrize('role',('model','checker','monitor','bundle','env','case','coverage'))
def test_production_support_has_no_experimental_or_test_code_import(role):
    files=[path for path in (ROOT/'bpuverify/bpu'/role).glob('*.py')
           if path.stem in ('window_lifetime','feedback_gate','bounded_sources','admission_window','miss_authority')]
    assert files
    for path in files:
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                assert not (node.module or '').startswith(('tests.','results.'))
            elif isinstance(node,ast.Import):
                assert not any(alias.name.startswith(('tests.','results.')) for alias in node.names)
