"""Human same-boundary obligation is not bank enumeration or old PASS reuse."""
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def test_human_contract_is_distinct_from_the_old_strictly_earlier_subscope():
    old=json.loads((ROOT/'docs/main-accepted-recovery-contract.json').read_text())
    new=json.loads((ROOT/'docs/main-coincident-recovery-contract.json').read_text())
    assert '原学习接纳严格早于恢复' in old['scope']
    assert new['new_feature_IDs']==0 and new['source_gap']['related_open_native_rows']==72
    assert '同一拍' in new['event'] and '尚未接纳' in new['effect']


def test_case_contains_only_semantic_program_and_evidence_calls():
    tree=ast.parse((ROOT/'tests/bpu/testcase/test_main_coincident_recovery.py').read_text())
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','Set','set_','get_','gather','create_task','sleep','skip','xfail'}


def test_old_features_require_both_old_and_new_complete_paired_lifetimes():
    points={p['id']:p for p in json.loads((ROOT/'verification_plan.json').read_text())['features']}
    assert len(points)==363
    for name in ('BPU-INT-005','BPU-INT-093'):
        p=points[name]
        assert p['metadata']['previous_strictly_earlier_recovery_contract']
        for status in ('reached','checked'):
            assert 'kunminghu_v3.bpu.main-accepted-recovery.'+status in p['evidence']['coverage'][status]
            assert 'kunminghu_v3.bpu.main-coincident-recovery.'+status in p['evidence']['coverage'][status]
        assert 'tests/bpu/testcase/test_main_coincident_recovery.py' in p['evidence']['checks']
