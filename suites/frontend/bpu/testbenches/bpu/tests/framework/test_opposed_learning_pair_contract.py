"""Human requirements and component cut-point limits stay explicit."""
import ast
import json
from pathlib import Path

ROOT=__import__('suites.frontend.bpu', fromlist=['ROOT']).ROOT


def test_human_pair_contract_is_not_a_physical_matrix_or_full_FTQ_claim():
    c=json.loads((ROOT/'docs/spec/verification/contracts/opposed-learning-pair-contract.json').read_text())
    assert c['title']=='相反方向的两笔旧预测反馈各自更新当前版本，不互相覆盖待写学习'
    assert c['source_gap']['open_rows']==103 and c['source_gap']['guard_rows_and_physical_denominator_retained']
    assert '保存原快照不等于证明FTQ学习资格' in c['scope']
    assert not c['physical_coordinate_enumeration'] and not c['SDK_RTL_DUT_changes']


def test_case_never_exposes_edges_raw_signals_or_manual_tasks():
    tree=ast.parse((ROOT/'testbenches/bpu/tests/testcase/test_opposed_learning_pair.py').read_text())
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','Set','set_','get_','create_task','gather','sleep','skip','xfail'}


def test_new_program_is_declarative_and_has_no_actual_state_seed():
    tree=ast.parse((ROOT/'testbenches/bpu/model/tage/opposed_learning_pair.py').read_text())
    imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    assert imports=={'suites.frontend.bpu.testbenches.bpu.model.tage.direction_turnaround'}
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    assert not names&{'dut','actual','monitor','signal','get_','set_'}
