"""Parent semantics, source validity and public driver controls stay explicit."""
import ast
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def test_human_requirement_is_clear_destination_and_independent_learning():
    c=json.loads((ROOT/'docs/main-duplicate-cleanup-contract.json').read_text())
    assert c['title']=='重复分支副本清理按目标副本执行，不能吞掉独立分支的学习'
    assert c['source_gap']['parent_dual_inputs_are_write_and_cleanup_not_two_arbitrary_trains']
    assert c['source_gap']['cross_owner_candidate_rows']+c['source_gap']['dual_operation_candidate_rows']==93
    assert '16窗口' in c['scope'] and not c['physical_coordinate_enumeration']


def test_case_never_exposes_edges_io_or_manual_tasks():
    tree=ast.parse((ROOT/'tests/bpu/testcase/test_main_duplicate_cleanup.py').read_text())
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','Set','set_','get_','gather','create_task','sleep','skip','xfail'}


def test_environment_keeps_cold_source_qualification_and_no_internal_s2_write():
    text=(ROOT/'bpu/env/main_duplicate_cleanup.py').read_text()
    assert 'ledger.live' in text and 'prepare_feedback' in text and 'admit_when' in text
    assert 'accept_window' in text and 's2_fire.Set' not in text and 'ImmSet' not in text
    assert 'no_commit_inferred=True' in text and 'full_FTQ_reachability_proved=False' in text


def test_existing_points_keep_explicit_paired_cleanup_schema():
    points={p['id']:p for p in json.loads((ROOT/'verification_plan.json').read_text())['features']}
    assert len(points)==363
    for identity in ('BPU-MBTB-029','BPU-INT-093'):
        p=points[identity];assert 'tests/bpu/testcase/test_main_duplicate_cleanup.py' in p['evidence']['checks']
        for status in ('reached','checked'):
            assert 'kunminghu_v3.bpu.main-duplicate-cleanup.'+status in p['evidence']['coverage'][status]
