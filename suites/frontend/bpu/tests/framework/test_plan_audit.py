"""Definition review must expose missing proof rather than manufacture credit."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from bpuverify.common.pytest.points import validate_plan
from tools.audit_verification_plan import audit, markdown


def sample(root):
    for name in ('model.py','checks.py'):
        (root/name).write_text('"""Synthetic path-binding fixture only."""\n')
    point=dict(id='BPU-DEMO-001',component='Demo',title='Logical owner update',description='accepted owner update',
        metadata=dict(domain='hardware'),
        contract={key:'explicit '+key for key in
                  ('event','owner','effect','observation','preservation','scope')},
        evidence=dict(model=['model.py'],checks=['checks.py'],
            coverage=dict(reached=['demo.reached'],checked=['demo.checked'])))
    plan=dict(version=2,features=[point])
    measurement=dict(features=[dict(id=point['id'],status='FAIL',
        tests=[dict(nodeid='tests/demo.py::test_demo',status='FAIL')])])
    functional=dict(groups={'demo.reached':100,'demo.checked':0})
    return plan,measurement,functional


def test_reached_without_checked_retains_failure_and_exposes_zero_credit(tmp_path):
    inputs=sample(tmp_path)
    previous=deepcopy(inputs)
    report=audit(*inputs,tmp_path)
    assert report['summaries']['hardware']['status_counts']['FAIL']==1
    assert report['summaries']['hardware']['passed']==0
    assert report['points'][0]['coverage_association']=='paired'
    assert report['points'][0]['gaps']==['checked-coverage-zero']
    assert inputs==previous


def test_legacy_full_group_is_not_a_reached_checked_pair(tmp_path):
    plan,measurement,functional=sample(tmp_path)
    plan['features'][0]['evidence']['coverage']=dict(reached=[],checked=['old_group'])
    functional['groups']['old_group']=100
    report=audit(plan,measurement,functional,tmp_path)
    assert report['points'][0]['coverage_association']=='unpaired-checked-group'
    assert report['points'][0]['gaps']==['no-separate-reached-binding']
    assert report['summaries']['hardware']['passed']==0


def test_explicit_new_definition_is_not_run_in_an_older_measurement(tmp_path):
    plan,measurement,functional=sample(tmp_path)
    added=deepcopy(plan['features'][0]);added['id']='BPU-DEMO-002'
    plan['features'].append(added)
    with pytest.raises(ValueError):audit(plan,measurement,functional,tmp_path)
    result=audit(plan,measurement,functional,tmp_path,planned_additions=[added['id']])
    assert result['summaries']['hardware']['planned']==2
    assert result['summaries']['hardware']['executed']==1
    assert result['summaries']['hardware']['status_counts']['NOT_RUN']==1
    assert result['points'][-1]['status']=='NOT_RUN' and result['points'][-1]['tests']==[]
    assert result['points'][0]['status']=='FAIL'


def test_addition_allowlist_cannot_hide_an_unknown_or_missing_old_identity(tmp_path):
    plan,measurement,functional=sample(tmp_path)
    with pytest.raises(ValueError):
        audit(plan,measurement,functional,tmp_path,planned_additions=['NOT_A_REAL_POINT'])


def test_group_not_present_in_measurement_is_not_assumed_covered(tmp_path):
    plan,measurement,functional=sample(tmp_path)
    del functional['groups']['demo.checked']
    report=audit(plan,measurement,functional,tmp_path)
    assert report['points'][0]['coverage_values']['checked']['demo.checked'] is None
    assert 'not-measured:demo.checked' in report['points'][0]['gaps']


@pytest.mark.parametrize('status', ['PASS', 'FAIL'])
def test_refined_obligations_limits_and_spec_questions_cannot_disappear_behind_old_verdict(tmp_path,status):
    plan,measurement,functional=sample(tmp_path)
    point=plan['features'][0]
    requirement='At both bounds net-zero votes retain the common pre-state.'
    limitation='Old interior-only cases do not prove the boundary.'
    question='Disposition of an already accepted operation during disable is unresolved.'
    point['metadata'].update(semantic_requirements=[requirement],
        semantic_review=dict(evidence_limits=limitation,unresolved_specification=question))
    measurement['features'][0].update(status=status,tests=[dict(nodeid='tests/demo.py::test_demo',status=status)])
    functional['groups']['demo.checked']=100
    before=deepcopy((plan,measurement,functional))
    report=audit(plan,measurement,functional,tmp_path)
    row=report['points'][0]
    assert row['status']==status and row['gaps']==['unresolved-specification']
    assert row['semantic_requirements']==[requirement]
    assert row['evidence_limits']==limitation and row['unresolved_specification']==question
    assert row['requirement_verdict_scope']=='retained-tests-only; subrequirements-not-independently-adjudicated'
    assert report['summaries']['hardware']['passed']==int(status=='PASS')
    rendered=markdown(report)
    assert all(text in rendered for text in (requirement,limitation,question,'不继承旧PASS'))
    assert (plan,measurement,functional)==before


def test_older_definition_without_refinement_metadata_remains_readable(tmp_path):
    report=audit(*sample(tmp_path),tmp_path)
    row=report['points'][0]
    assert row['semantic_requirements']==[] and row['evidence_limits']==row['unresolved_specification']==''
    assert 'explicit owner' in markdown(report)


@pytest.mark.parametrize('damage',['model','identity','verdict','contract','fake_pair'])
def test_missing_or_corrupt_binding_is_rejected(tmp_path,damage):
    plan,measurement,functional=sample(tmp_path)
    if damage=='model': (tmp_path/'model.py').unlink()
    elif damage=='identity': measurement['features'][0]['id']='OTHER'
    elif damage=='verdict': measurement['features'][0]['status']='PASS'
    elif damage=='contract': plan['features'][0]['contract'].pop('owner')
    elif damage=='fake_pair': plan['features'][0]['evidence']['coverage']['reached']=['old_group']
    with pytest.raises(ValueError):audit(plan,measurement,functional,tmp_path)


def test_all_current_failed_requirements_have_explicit_event_contracts():
    root=Path(__file__).resolve().parents[2]
    plan=json.loads((root/'verification_plan.json').read_text())
    validate_plan(plan)
    points={point['id']:point for point in plan['features']}
    failed=('BPU-ABTB-053','BPU-MBTB-027','BPU-MBTB-028','BPU-MBTB-029',
        'BPU-ITTAGE-019','BPU-URAS-016','BPU-RAS-008','BPU-RAS-017',
        'BPU-UTAGE-007','BPU-UTAGE-016','BPU-UTAGE-020','BPU-UTAGE-021','BPU-UTAGE-025',
        'BPU-UBTB-011','BPU-TAGE-026','BPU-INT-044','BPU-INT-094')
    assert all('contract' in points[identity] for identity in failed)
    structured=[point for point in points.values() if 'contract' in point]
    reviewed=('BPU-UTAGE-023','BPU-UTAGE-024','BPU-ABTB-050','BPU-ABTB-051',
              'BPU-MBTB-024','BPU-INT-055','BPU-INT-056','BPU-INT-058')
    assert set(failed+reviewed) <= {point['id'] for point in structured}
    assert len(structured) >= 19+len(reviewed)
    for point in structured:
        for name in point['evidence']['model']+point['evidence']['checks']:
            assert (root/name).is_file(),(point['id'],name)
