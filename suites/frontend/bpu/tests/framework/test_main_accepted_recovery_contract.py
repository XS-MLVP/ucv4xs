"""Recovery crosses accepted learning, not raw IO scheduling."""
import ast
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def test_human_requirement_separates_prediction_fate_from_accepted_learning():
    c=json.loads((ROOT/'docs/main-accepted-recovery-contract.json').read_text())
    assert c['title']=='已经接纳的学习副本不随后续预测恢复而丢失'
    assert '原学习接纳严格早于恢复' in c['scope'] and c['source_gap']['related_native_zero_rows']==93
    assert c['source_gap']['raw_denominator_and_guards_retained'] and c['new_feature_IDs']==0


def test_native_case_has_no_edges_raw_signals_wait_constants_or_manual_tasks():
    tree=ast.parse((ROOT/'tests/bpu/testcase/test_main_accepted_recovery.py').read_text())
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','Set','set_','get_','gather','create_task','sleep','skip','xfail'}


def test_environment_uses_complete_original_gate_and_actual_source_ledger():
    text=(ROOT/'bpuverify/bpu/env/main_accepted_recovery.py').read_text()
    assert 'prepare_feedback' in text and 'drain=False' in text and 'ledger.live' in text
    assert 'plan_redirect' in text and 'ledger.accepted[-1].source' in text
    assert 'no_commit_inferred=True' in text and 'full_FTQ_reachability_proved=False' in text


def test_existing_functional_points_bind_both_lifetime_schemas():
    points={p['id']:p for p in json.loads((ROOT/'verification_plan.json').read_text())['features']}
    assert len(points)==363
    for identity in ('BPU-INT-005','BPU-INT-093'):
        p=points[identity];assert 'tests/bpu/testcase/test_main_accepted_recovery.py' in p['evidence']['checks']
        for status in ('reached','checked'):
            assert 'kunminghu_v3.bpu.main-accepted-recovery.'+status in p['evidence']['coverage'][status]
