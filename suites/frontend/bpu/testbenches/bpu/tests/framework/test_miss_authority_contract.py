"""Miss payload transport is not direction-learning permission."""
import ast
import json
from pathlib import Path
import pytest

ROOT = __import__('suites.frontend.bpu', fromlist=['ROOT']).ROOT


def test_existing_point_gains_integrated_evidence_without_claiming_complete_FTQ():
    event=json.loads((ROOT/'docs/spec/verification/functional/functional-events.json').read_text())['events']['feedback.unmatched-owner']
    assert 'BPU-MBTB-027' in event['features']['mbtb']


def test_thin_case_has_no_edges_or_scheduler_and_does_not_claim_working_set_credit():
    source=(ROOT/'testbenches/bpu/tests/testcase/test_miss_authority.py').read_text()
    tree=ast.parse(source)
    names={node.id for node in ast.walk(tree) if isinstance(node,ast.Name)}
    names|={node.attr for node in ast.walk(tree) if isinstance(node,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','set_','get','gather','create_task','sleep'}
    assert "@pytest.mark.feature('BPU-INT-100')" not in source
    assert 'from results.' not in source and 'toffee_functional_coverage' not in source


@pytest.mark.parametrize('role',('model','checker','monitor','bundle','env','case','coverage'))
def test_production_support_has_no_experimental_or_test_code_import(role):
    locations={'model':'model','checker':'checker','monitor':'env/monitor','bundle':'env/bundle',
               'env':'tests/scenarios/lifetimes','case':'tests/scenarios','coverage':'coverage'}
    files=[path for path in (ROOT/'testbenches/bpu'/locations[role]).glob('*.py')
           if path.stem in ('window_lifetime','feedback_gate','bounded_sources','admission_window','miss_authority')]
    assert files
    for path in files:
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                assert not (node.module or '').startswith(('tests.','results.'))
            elif isinstance(node,ast.Import):
                assert not any(alias.name.startswith(('tests.','results.')) for alias in node.names)
