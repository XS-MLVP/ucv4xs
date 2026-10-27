"""Human semantics and public flow precede case collection."""
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def test_contract_declares_resolution_order_and_visibility_not_physical_points():
    value=json.loads((ROOT/'docs/main-original-order-contract.json').read_text())
    assert value['title']=='同一分支的原始解析按实际接纳顺序更新，未执行后继不被重学'
    assert value['new_feature_IDs']==0 and not value['physical_coordinate_enumeration']
    assert value['source_gap']['related_native_zero_rows']==93
    assert value['source_gap']['relation_is_not_a_claim_to_hit_all_93_rows']


def test_case_only_declares_semantic_intent_and_leaves_signal_timing_in_environment():
    source=(ROOT/'tests/bpu/testcase/test_main_original_order.py').read_text();tree=ast.parse(source)
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','set_','Set','gather','create_task','sleep'}
    assert 'bpu_agent' in source and "'BPU-INT-093'" in source and "'BPU-MBTB-028'" in source


def test_new_model_describes_semantic_versions_and_reuses_existing_algorithms():
    source=(ROOT/'bpuverify/bpu/model/main_original_order.py').read_text();tree=ast.parse(source)
    imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    assert 'bpuverify.mbtb.model.replacement' in imports and 'bpuverify.mbtb.model.semantic' in imports
    assert not any('toffee' in module or 'monitor' in module or 'driver' in module for module in imports)


def test_new_environment_drives_no_edges_or_internal_signals():
    names=set()
    for name in ('main_original_order.py','main_original_lifetime.py'):
        source=(ROOT/'bpuverify/bpu/env'/name).read_text();tree=ast.parse(source)
        local={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
        local|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
        assert not local&{'FallingEdge','RisingEdge','ClockCycles','Set','AsImmWrite','gather','sleep','commit'}
        names|=local
    assert 'ServiceMonitor' in names and 'PredictionWindow' in names
