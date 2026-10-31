"""The feature is logical recursive ownership, not per-stack-slot toggles."""
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def test_human_requirement_precedes_case_and_keeps_local_guard_zero_rows():
    c=json.loads((ROOT/'docs/ras-adjacent-recursion-contract.json').read_text())
    assert c['title']=='接近容量时，相邻递归层各自保留剩余返回次数和外层调用身份'
    assert c['source_gap']['remaining_semantic_attribution_rows']==6
    assert c['source_gap']['local_priority_and_parent_action_guard_rows_not_waived']
    assert c['new_feature_IDs']==0 and not c['physical_coordinate_enumeration']
    plan={p['id']:p for p in json.loads((ROOT/'verification_plan.json').read_text())['features']}
    for identity in c['features']:
        point=plan[identity]
        assert 'tests/bpu/testcase/test_ras_adjacent_recursion.py' in point['evidence']['checks']
        for status in ('reached','checked'):
            assert 'kunminghu_v3.bpu.adjacent-recursive-return.'+status in point['evidence']['coverage'][status]


def test_case_has_no_edge_scheduler_or_signal_level_work():
    source=(ROOT/'tests/bpu/testcase/test_ras_adjacent_recursion.py').read_text();tree=ast.parse(source)
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    assert not names&{'RisingEdge','FallingEdge','ClockCycles','Set','set_','create_task','gather','sleep','skip','xfail'}
    assert "'BPU-INT-096'" in source


def test_model_has_no_monitor_DUT_or_actual_state_dependency():
    tree=ast.parse((ROOT/'bpu/model/ras/adjacent_recursion.py').read_text())
    imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    assert imports=={'dataclasses','suites.frontend.bpu.ras.model.model'}
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    assert not names&{'dut','monitor','actual','get_','set_'}


def test_environment_reuses_existing_genuine_source_and_retirement_lifetime():
    text=(ROOT/'bpu/env/ras/adjacent_recursion.py').read_text()
    assert 'check_lifetime' in text and 'layer_pcs=program.layer_pcs' in text
    assert 'root_pc=ROOT' in text and 'results.' not in text
