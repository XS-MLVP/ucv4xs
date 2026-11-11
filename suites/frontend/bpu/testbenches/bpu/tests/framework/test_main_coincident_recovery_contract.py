"""Human same-boundary obligation is not bank enumeration or old PASS reuse."""
import ast
import json
from pathlib import Path

ROOT=__import__('suites.frontend.bpu', fromlist=['ROOT']).ROOT


def test_human_contract_is_distinct_from_the_old_strictly_earlier_subscope():
    old=json.loads((ROOT/'docs/spec/verification/contracts/main-accepted-recovery-contract.json').read_text())
    new=json.loads((ROOT/'docs/spec/verification/contracts/main-coincident-recovery-contract.json').read_text())
    assert '原学习接纳严格早于恢复' in old['scope']
    assert new['new_feature_IDs']==0 and new['source_gap']['related_open_native_rows']==72
    assert '同一拍' in new['event'] and '尚未接纳' in new['effect']


def test_case_contains_only_semantic_program_and_evidence_calls():
    tree=ast.parse((ROOT/'testbenches/bpu/tests/testcase/test_main_coincident_recovery.py').read_text())
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','Set','set_','get_','gather','create_task','sleep','skip','xfail'}
