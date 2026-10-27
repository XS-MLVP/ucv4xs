"""Environment validation must not be relabelled as Main predictor coverage."""
import ast
import json
from pathlib import Path
from bpuverify.bpu.model.source_eligibility import MODES

ROOT=Path(__file__).resolve().parents[2]


def test_all_eight_native_lifetime_crosses_are_explicit_without_physical_enumeration():
    assert set(MODES)=={'valid-old-late','flushed-before-prepare','flushed-before-launch','changed-before-launch',
        'reset-before-prepare','reset-before-launch','cancel-before-launch','defer-then-accept'}
    contract=json.loads((ROOT/'docs/source-eligibility-driver-contract.json').read_text())
    assert contract['existing_environment_point']=='ENV-DRV-004'
    assert not contract['hardware_feature_PASS_granted'] and not contract['physical_enumeration']


def test_existing_environment_requirement_adds_native_proof_without_new_feature_IDs():
    plan=json.loads((ROOT/'verification_plan.json').read_text())
    assert len(plan['features'])==363
    point=next(p for p in plan['features'] if p['id']=='ENV-DRV-004')
    assert point['metadata']['domain']=='environment'
    assert point['metadata']['previous_pre_native_source_eligibility']
    assert 'tests/bpu/testcase/test_source_eligibility.py' in point['metadata']['native_source_eligibility_tests']


def test_native_case_credits_only_environment_and_excludes_hardware_functional_collection():
    source=(ROOT/'tests/bpu/testcase/test_source_eligibility.py').read_text()
    assert "@pytest.mark.feature('ENV-DRV-004')" in source
    assert '@pytest.mark.toffee_functional_coverage(False)' in source
    assert 'BPU-MBTB-' not in source and 'BPU-INT-' not in source


def test_case_and_new_environment_have_no_edge_or_scheduler_or_raw_set_operations():
    for name in ('tests/bpu/testcase/test_source_eligibility.py','bpuverify/bpu/env/source_eligibility.py'):
        tree=ast.parse((ROOT/name).read_text())
        names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
        names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
        assert not names&{'FallingEdge','RisingEdge','ClockCycles','set_','Set','gather','create_task','sleep'}
