"""Definition/source association is not a new measurement or functional PASS."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tools.review_semantic_gaps import (
    ROOT, shadow_role, validate_catalog, held_repair_witnesses, micro_ras_parent_claims,
)
from suites.frontend.bpu.pytest_plugins.points import validate_plan


@pytest.mark.parametrize('text,previous,role,events', [
    ('if (io_train_t1_alloc_valid)','', 'allocation-choice',
     ('useful.allocate','useful.change','useful.hold')),
    ("usefulEntries_2_73_value <= 2'h2;",'', 'allocation-initialize',('useful.allocate',)),
    ('else if (_newUseful_T_8)','', 'saturation-choice',('useful.hold','useful.change')),
    ('usefulEntries_2_73_value <= _GEN_147;','else if (_newUseful_T_8)',
     'saturation-preserve',('useful.hold',)),
    ('usefulEntries_2_73_value <= _newUseful_T_13;','else', 'counter-change',('useful.change',)),
])
def test_exact_source_roles_keep_control_anchor_many_to_many(text,previous,role,events):
    assert shadow_role(text,previous)==(role,events)


@pytest.mark.parametrize('text,previous', [
    ('entries_2_index <= io_train_index;',''),
    ('usefulEntries_2_73_value <= _GEN_147;','if (io_usefulReset)'),
    ('if (an_unreviewed_guard)',''),
])
def test_unreviewed_source_shape_is_not_guessed_from_shadow_module_name(text,previous):
    assert shadow_role(text,previous)==('UNRESOLVED',())


def test_current_event_catalog_is_traceable_without_manufacturing_an_execution():
    catalog=json.loads((ROOT/'docs/functional-events.json').read_text())
    plan=json.loads((ROOT/'verification_plan.json').read_text())
    previous=deepcopy((catalog,plan))
    validate_plan(plan)
    validate_catalog(catalog,plan)
    assert (catalog,plan)==previous
    required = {'useful.allocate','useful.change','useful.hold','useful.maintenance',
        'ahead.reward','ahead.penalize','ahead.replace','replacement.touch',
        'pending.rewrite','main.rewrite','main.replacement-forward','path.recover',
        'common.recover','loop.recover','ras.retire','micro-ras.repair','predictor.restart'}
    assert required <= catalog['events'].keys()
    for point in plan['features']:
        refs=point['metadata'].get('semantic_event_refs',[])
        assert all(ref in catalog['events'] for ref in refs)
        for ref in refs:
            assert any(point['id'] in names for names in catalog['events'][ref]['features'].values())
    assert not catalog['events']['micro-ras.repair']['features']['bpu']
    # These belong to other predictors despite their INT prefix.
    assert 'BPU-INT-083' not in catalog['events']['ahead.reward']['features']['bpu']
    assert 'BPU-INT-067' not in catalog['events']['replacement.touch']['features']['bpu']


def test_global_maintenance_names_the_learning_preservation_event_and_reuses_existing_requirements():
    catalog=json.loads((ROOT/'docs/functional-events.json').read_text())
    event=catalog['events']['useful.maintenance']
    assert event['features']==dict(utage=['BPU-UTAGE-017'],bpu=['BPU-INT-051','BPU-INT-102'])
    assert '共同前态' in event['effect'] and '方向' in event['effect']
    assert 'T/NT' in event['observation'] and '合格失败' in event['observation']
    path,number=event['source'].rsplit(':',1)
    assert 'when(lowTickCounter(LowTickWidth))' in (ROOT/path).read_text().splitlines()[int(number)-1]


def test_unknown_point_reference_is_rejected():
    catalog=json.loads((ROOT/'docs/functional-events.json').read_text())
    plan=json.loads((ROOT/'verification_plan.json').read_text())
    catalog['events']['useful.allocate']['features']['utage'].append('BPU-UNKNOWN-999')
    with pytest.raises(ValueError,match='unknown functional point'):
        validate_catalog(catalog,plan)


def test_bpu_parent_excludes_held_s2_call_repair_but_standalone_input_does_not():
    assert not held_repair_witnesses()
    assert held_repair_witnesses(relax_parent=True)
    claims,parent=micro_ras_parent_claims()
    assert parent.path=='rtl/bpu/Bpu.sv'
    assert {(c['first'],c['last'],c['arm']) for c in claims}=={(135,136,'elsif')}


def test_recipe_is_preserved_separately_from_readable_requirement():
    points={p['id']:p for p in json.loads((ROOT/'verification_plan.json').read_text())['features']}
    point=points['BPU-UTAGE-023']
    assert '流水线祖先' in point['title']
    assert point['metadata']['semantic_review']['previous_title']!=point['title']
    assert point['metadata']['semantic_review']['scenario_detail']
    assert '完整 usefulness' in point['contract']['observation']
    assert point['metadata']['semantic_event_refs']==['useful.change']


@pytest.mark.parametrize('dut,identity', (('mbtb','BPU-MBTB-001'), ('ubtb','BPU-UBTB-001')))
def test_nonempty_reset_definition_binds_new_paired_lifetimes_without_reusing_ready_credit(dut,identity):
    catalog=json.loads((ROOT/'docs/functional-events.json').read_text())
    points={p['id']:p for p in json.loads((ROOT/'verification_plan.json').read_text())['features']}
    point=points[identity]
    assert point['metadata']['semantic_event_refs']==['predictor.restart']
    assert catalog['events']['predictor.restart']['features'][dut]==([identity,'BPU-MBTB-019'] if dut=='mbtb' else [identity])
    assert point['metadata']['previous_reset_contract']['scope'] != point['contract']['scope']
    assert '异步查询transfer取消' in point['contract']['scope']
    for status in ('reached','checked'):
        assert point['evidence']['coverage'][status]==['kunminghu_v3.'+dut+'.'+family+'.'+status
            for family in (('reset-lifetime','query-reset-lifetime','cleanup-reset-lifetime') if dut=='mbtb'
                           else ('reset-lifetime','query-reset-lifetime'))]
    assert 'tests/'+dut+'/testcase/test_reset.py' in point['evidence']['checks']
    assert 'tests/'+dut+'/testcase/test_reset_lifetime.py' in point['evidence']['checks']
    path,number=catalog['events']['predictor.restart']['source'].rsplit(':',1)
    assert 'private val entries = RegInit' in (ROOT/path).read_text().splitlines()[int(number)-1]


@pytest.mark.parametrize('identity,family,event',(
    ('BPU-MBTB-001','mbtb.query-reset-lifetime','predictor.restart'),
    ('BPU-UBTB-001','ubtb.query-reset-lifetime','predictor.restart'),
    ('BPU-MBTB-019','mbtb.cleanup-reset-lifetime','branch.duplicate_cleanup'),
    ('BPU-INT-004','bpu.joint-late-sources','prediction.select_executed_branch'),
    ('BPU-INT-007','bpu.joint-late-sources','prediction.select_executed_branch'),
    ('BPU-INT-032','bpu.joint-late-sources','prediction.select_executed_branch')))
def test_new_lifetime_definitions_require_their_own_paired_proof_not_old_PASS(identity,family,event):
    plan=json.loads((ROOT/'verification_plan.json').read_text())
    catalog=json.loads((ROOT/'docs/functional-events.json').read_text())
    point=next(point for point in plan['features'] if point['id']==identity)
    assert point['metadata']['previous_pre_query_joint_cleanup_contract']!=point['contract']
    assert event in point['metadata']['semantic_event_refs']
    assert identity in catalog['events'][event]['features'][family.split('.')[0]]
    for status in ('reached','checked'):
        assert 'kunminghu_v3.'+family+'.'+status in point['evidence']['coverage'][status]
    assert all((ROOT/path).is_file() for role in ('model','checks') for path in point['evidence'][role])


def test_old_cleanup_single_group_is_preserved_as_mandatory_without_fabricating_reached():
    from tests.framework.test_parallel_matrices import EXTRA_MATRICES
    plan=json.loads((ROOT/'verification_plan.json').read_text())
    point=next(point for point in plan['features'] if point['id']=='BPU-MBTB-019')
    legacy=point['metadata']['legacy_coverage_bindings']
    factory,axes,cross,denominator=EXTRA_MATRICES['mbtb_legacy_cleanup']
    assert legacy==dict(checked=[factory().instance],required_by_production_merge_gate=True,
        original_four_bins_preserved=True,fabricated_reached=False)
    assert denominator==len(axes['phase'])==4 and cross is None
    assert factory().instance not in point['evidence']['coverage']['reached']


@pytest.mark.parametrize('identity',('BPU-UTAGE-006','BPU-UTAGE-015','BPU-UTAGE-022'))
def test_query_learning_definitions_require_both_new_lifetimes_without_reinterpreting_old_PASS(identity):
    plan=json.loads((ROOT/'verification_plan.json').read_text())
    point=next(point for point in plan['features'] if point['id']==identity)
    assert point['metadata']['previous_pre_read_lifetime_contract']!=point['contract']
    assert point['metadata']['read_lifetime_qualification']['old_PASS_is_not_new_subrequirement_proof']
    assert point['metadata']['read_lifetime_qualification']['multiple_age_wrap_not_proved']
    assert '后端提交执行真值' in point['contract']['scope']
    assert 'prediction.owned_read' in point['metadata']['semantic_event_refs']
    for status in ('reached','checked'):
        for family in ('read-version-lifetime','distinct-ancestor-learning'):
            assert 'kunminghu_v3.utage.'+family+'.'+status in point['evidence']['coverage'][status]
    assert all((ROOT/path).is_file() for role in ('model','checks') for path in point['evidence'][role])


@pytest.mark.parametrize('identity,legacy',(('BPU-UTAGE-015','shadow_ring'),('BPU-UTAGE-022','partial_shadow_wrap')))
def test_original_unpaired_utage_groups_keep_their_names_and_full_denominators(identity,legacy):
    point=next(point for point in json.loads((ROOT/'verification_plan.json').read_text())['features'] if point['id']==identity)
    assert point['metadata']['legacy_coverage_bindings']['checked']==['kunminghu_v3.utage.'+legacy]
    assert point['metadata']['legacy_coverage_bindings']['retained_in_full_merge_gate']
    assert all(name.endswith('.checked') for name in point['evidence']['coverage']['checked'])
