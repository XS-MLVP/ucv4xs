"""Definition/source association is not a new measurement or functional PASS."""
from copy import deepcopy
import json

import pytest

from tools.review_semantic_gaps import (
    ROOT, shadow_role, validate_catalog, held_repair_witnesses, micro_ras_parent_claims,
)


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
    catalog=json.loads((ROOT/'docs/spec/verification/functional/functional-events.json').read_text())
    previous=deepcopy(catalog)
    validate_catalog(catalog)
    assert catalog==previous
    required = {'useful.allocate','useful.change','useful.hold','useful.maintenance',
        'ahead.reward','ahead.penalize','ahead.replace','replacement.touch',
        'pending.rewrite','main.rewrite','main.replacement-forward','path.recover',
        'common.recover','loop.recover','ras.retire','micro-ras.repair','predictor.restart'}
    assert required <= catalog['events'].keys()
    assert not catalog['events']['micro-ras.repair']['features']['bpu']
    # These belong to other predictors despite their INT prefix.
    assert 'BPU-INT-083' not in catalog['events']['ahead.reward']['features']['bpu']
    assert 'BPU-INT-067' not in catalog['events']['replacement.touch']['features']['bpu']


def test_global_maintenance_names_the_learning_preservation_event_and_reuses_existing_requirements():
    catalog=json.loads((ROOT/'docs/spec/verification/functional/functional-events.json').read_text())
    event=catalog['events']['useful.maintenance']
    assert event['features']==dict(utage=['BPU-UTAGE-017'],bpu=['BPU-INT-051','BPU-INT-102'])
    assert '共同前态' in event['effect'] and '方向' in event['effect']
    assert 'T/NT' in event['observation'] and '合格失败' in event['observation']
    path,number=event['source'].rsplit(':',1)
    assert 'when(lowTickCounter(LowTickWidth))' in (ROOT/path).read_text().splitlines()[int(number)-1]


def test_bpu_parent_excludes_held_s2_call_repair_but_standalone_input_does_not():
    assert not held_repair_witnesses()
    assert held_repair_witnesses(relax_parent=True)
    claims,parent=micro_ras_parent_claims()
    assert parent.path=='rtl/bpu/Bpu.sv'
    assert {(c['first'],c['last'],c['arm']) for c in claims}=={(135,136,'elsif')}


@pytest.mark.parametrize('dut,identity', (('mbtb','BPU-MBTB-001'), ('ubtb','BPU-UBTB-001')))
def test_nonempty_reset_definition_binds_new_paired_lifetimes_without_reusing_ready_credit(dut,identity):
    catalog=json.loads((ROOT/'docs/spec/verification/functional/functional-events.json').read_text())
    assert catalog['events']['predictor.restart']['features'][dut]==([identity,'BPU-MBTB-019'] if dut=='mbtb' else [identity])
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
    catalog=json.loads((ROOT/'docs/spec/verification/functional/functional-events.json').read_text())
    assert identity in catalog['events'][event]['features'][family.split('.')[0]]


def test_old_cleanup_single_group_is_preserved_as_mandatory_without_fabricating_reached():
    from suites.frontend.bpu.testbenches.bpu.tests.framework.test_parallel_matrices import EXTRA_MATRICES
    factory,axes,cross,denominator=EXTRA_MATRICES['mbtb_legacy_cleanup']
    assert denominator==len(axes['phase'])==4 and cross is None
