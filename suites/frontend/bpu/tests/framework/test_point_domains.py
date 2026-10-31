"""Hardware correctness cannot be inflated by environment-contract passes."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from suites.frontend.bpu.pytest_plugins.points import domain, make_report, summarize, summary_for, validate_plan, validate_report
from tools.refresh_coverage import validate_functional_points


def points():
    return [dict(id='BPU-DEMO-001',status='PASS'),
            dict(id='BPU-DEMO-002',status='FAIL'),
            dict(id='BPU-DEMO-003',status='XFAIL'),
            dict(id='ENV-DRV-001',status='PASS')]


def test_primary_summary_excludes_environment_but_preserves_every_verdict():
    rows = points()
    original = deepcopy(rows)
    report = make_report(rows)
    validate_report(report)
    assert report['summary']['planned']==3 and report['summary']['passed']==1
    assert report['summaries']['environment']['planned']==1
    assert report['summaries']['all']['planned']==4
    assert report['features']==rows==original


def test_environment_failure_is_not_hidden_by_primary_hardware_summary():
    rows = [dict(id='BPU-DEMO-001',status='PASS'),dict(id='ENV-DRV-001',status='FAIL')]
    report = make_report(rows)
    validate_report(report)
    assert report['summary']['pass_rate']==100
    assert report['summaries']['environment']['status_counts']['FAIL']==1
    assert report['summaries']['all']['status_counts']['FAIL']==1


@pytest.mark.parametrize('status',['ERROR','FAIL','XPASS','PASS','XFAIL','SKIP','NOT_RUN'])
def test_execution_and_pass_have_distinct_meanings(status):
    row = summarize([dict(status=status)])
    assert row['planned']==1
    assert row['executed']==int(status not in ('SKIP','NOT_RUN'))
    assert row['passed']==int(status=='PASS')


@pytest.mark.parametrize('scope',['hardware','environment','all','primary'])
@pytest.mark.parametrize('mutation',['count','bool','rate','status','negative'])
def test_corrupt_or_omitted_partitions_cannot_hide_verdicts(scope,mutation):
    report=make_report(points())
    report=deepcopy(report)  # Primary and hardware may alias in freshly built reports.
    row=report['summary'] if scope=='primary' else report['summaries'][scope]
    if mutation=='count': row['planned']+=1
    elif mutation=='bool': row['passed']=True
    elif mutation=='rate': row['pass_rate']=100
    elif mutation=='status': row['status_counts'].pop('FAIL')
    elif mutation=='negative': row['status_counts']['FAIL']=-1
    # Environment is already 100%; force a changed rate for that partition.
    if mutation=='rate' and scope=='environment': row['pass_rate']=0
    with pytest.raises(ValueError): validate_report(report)


@pytest.mark.parametrize('identity,declared',[('ENV-DRV-001','hardware'),('BPU-DEMO-001','environment'),('BPU-DEMO-001','physical')])
def test_domain_cannot_relabel_hardware_or_environment_points(identity,declared):
    with pytest.raises(ValueError): domain(dict(id=identity,metadata=dict(domain=declared)))


def test_historical_v1_reports_are_read_without_rewriting_or_inflating_hardware():
    rows=points()
    report=dict(version=1,features=rows,summary=summarize(rows))
    before=deepcopy(report)
    assert summary_for(report)['planned']==3
    assert summary_for(report,'environment')['planned']==1
    assert summary_for(report,'all')['planned']==4
    assert report==before


def test_v2_publication_gate_still_requires_every_environment_point():
    node='tests/demo.py::test_demo'
    rows=[dict(id=identity,status='PASS',tests=[dict(nodeid=node,status='PASS')])
          for identity in ('BPU-DEMO-001','ENV-DRV-001')]
    report=make_report(rows)
    plan=dict(features=[dict(id=row['id']) for row in rows])
    validate_functional_points(report,plan,plan,{node:'PASS'})
    report['features'].pop()
    with pytest.raises(ValueError,match='identities differ'):
        validate_functional_points(report,plan,plan,{node:'PASS'})


def test_real_plan_has_explicit_domains_and_documented_expectations():
    root=Path(__file__).resolve().parents[2]
    plan=json.loads((root/'verification_plan.json').read_text())
    validate_plan(plan)
    # Natural working-set lifetime, cold isolation and multi-path history
    # lifetime add semantic requirements, never physical-coordinate IDs.
    assert len(plan['features'])==363
    assert sum(domain(row)=='hardware' for row in plan['features'])==353
    assert sum(domain(row)=='environment' for row in plan['features'])==10
    assert all(row.get('description','').strip() for row in plan['features'])
    assert not any(row['component']=='Interface' for row in plan['features'])


def test_definition_provenance_is_existing_documentation_not_a_generic_template():
    root=Path(__file__).resolve().parents[2]
    plan=json.loads((root/'verification_plan.json').read_text())
    text=(root/'docs/functional-points.md').read_text()
    restored=[row for row in plan['features'] if
              row['metadata'].get('definition_source','').startswith('docs/functional-points.md') or
              row['metadata'].get('semantic_review',{}).get('previous_definition_source','').startswith('docs/functional-points.md')]
    assert len(restored)==152
    for row in restored:
        review=row['metadata'].get('semantic_review',{})
        if 'previous_definition_source' in review:
            assert review['scenario_detail'] in text
            assert row['id'] in review['previous_definition_source']
        else:
            assert row['description'] in text
            assert row['id'] in row['metadata']['definition_source']
