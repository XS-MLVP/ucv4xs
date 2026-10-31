"""Production roles contain no staging imports or relaxed failure paths."""
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCES=('bpu/model/main_cold_original_order.py','bpu/checker/main_cold_original_order.py',
    'bpu/env/main_cold_original_order.py','bpu/env/main_original_lifetime.py',
    'bpu/case/main_cold_original_order.py','bpu/coverage/main_cold_original_order.py',
    'tests/bpu/testcase/test_main_cold_original_order.py')


def test_every_production_role_is_free_of_prototype_imports_or_dynamic_replacement():
    for name in SOURCES:
        source=(ROOT/name).read_text();tree=ast.parse(source)
        imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        assert not any(module.startswith('results') for module in imports)
        names={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
        assert not names&{'monkeypatch','setattr','exec','eval'}


def test_cold_case_only_declares_semantic_intent_and_existing_points():
    tree=ast.parse((ROOT/'tests/bpu/testcase/test_main_cold_original_order.py').read_text())
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','Set','set_','gather','create_task','sleep','xfail','skip'}


def test_both_preparation_modes_reuse_one_lifetime_without_overriding_sdk_or_predictors():
    for name in ('main_original_order','main_cold_original_order'):
        source=(ROOT/f'bpu/env/{name}.py').read_text()
        assert 'run_original_lifetime' in source and 'prepare_sources=prepare' in source
        assert 'checker_factory=Checks' in source


def test_cold_contract_keeps_original_failures_and_full_architectural_scope_limits():
    contract=json.loads((ROOT/'docs/main-cold-original-order-contract.json').read_text())
    assert contract['new_feature_IDs']==0 and not contract['physical_coordinate_enumeration']
    assert '首个异常' in contract['failure_contract'] and '完整FTQ' in contract['scope']
    assert contract['features']==['BPU-INT-093','BPU-INT-095','BPU-MBTB-028']


def test_control_cleanup_occurs_inside_live_service_monitor_scope():
    tree=ast.parse((ROOT/'bpu/env/main_original_lifetime.py').read_text())
    scopes=[n for n in ast.walk(tree) if isinstance(n,ast.AsyncWith) and any(
        isinstance(item.context_expr,ast.Call) and isinstance(item.context_expr.func,ast.Name)
        and item.context_expr.func.id=='ServiceMonitor' for item in n.items)]
    assert len(scopes)==1
    assert any(isinstance(n,ast.Try) and any(isinstance(a,ast.Await) and isinstance(a.value,ast.Call)
        and isinstance(a.value.func,ast.Name) and a.value.func.id=='close_pressure'
        for block in n.finalbody for a in ast.walk(block)) for n in ast.walk(scopes[0]))
