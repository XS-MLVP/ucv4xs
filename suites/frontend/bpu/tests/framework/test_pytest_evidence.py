"""Missing workers, lifecycle phases, and artifacts cannot become green evidence."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from suites.frontend.bpu.pytest_plugins import evidence


@pytest.fixture
def make_state(tmp_path, monkeypatch):
    states = []
    monkeypatch.setattr(evidence, 'RTL_COVERAGE_FILES', set())
    def make(*, workers=2, collect=False, run=None):
        options = dict(artifact_run=str(run or tmp_path / 'results' / f'run{len(states)}'),
                       rtl_retention='raw', rtl_batch_size=16)
        config = SimpleNamespace(rootpath=tmp_path,
            option=SimpleNamespace(numprocesses=workers, collectonly=collect),
            getoption=lambda name: options[name],
            _bpu_feature_plan=[dict(id='F', component='Unit', title='Required check')],
            _bpu_feature_ids={'F'})
        state = evidence.Evidence(config)
        states.append(state)
        return state
    yield make
    for state in reversed(states):
        state.pytest_unconfigure()


def phase(worker='gw0', *, status='PASS', outcome='passed'):
    return dict(status=status, outcome=outcome, worker=worker)


def test_receipt_collection_uses_final_deselected_session(make_state):
    state = make_state(collect=True)
    item = SimpleNamespace(nodeid='selected', iter_markers=lambda name: ())
    state.pytest_collection_finish(SimpleNamespace(items=[item]))
    assert state.collected == ['selected'] and state.mapping == {'selected': []}


def populated(state):
    nodeid = 'tests/unit/test_a.py::test_same[p0]'
    state.collected = [nodeid]
    state.mapping[nodeid] = ['F']
    state.started = state.collections = {'gw0'}
    state.reports[nodeid] = dict(setup=phase(status=None), call=phase(), teardown=phase(status=None))
    state.receipts['gw0'] = dict(worker='gw0', collected_count=1,
        collection_sha256=evidence.collection_digest([nodeid]), files=[],
        pytest_exitstatus=0, integrity_errors=[], native_retention=dict(mode='raw'))
    return nodeid


@pytest.mark.parametrize('status', ('FAIL', 'ERROR', 'XPASS'))
def test_ordinary_failed_worker_is_complete_but_never_pass_evidence(make_state, status):
    state = make_state()
    nodeid = populated(state)
    state.reports[nodeid]['call'] = phase(status=status, outcome='failed')
    receipt = state.receipts.pop('gw0')
    receipt['pytest_exitstatus'] = int(pytest.ExitCode.TESTS_FAILED)
    node = SimpleNamespace(gateway=SimpleNamespace(id='gw0'), workeroutput={'bpu_evidence': receipt})
    state.pytest_testnodedown(node, None)
    tests, _ = state.validated_results()
    assert not state.errors
    assert tests[0]['status'] == status
    assert receipt['pytest_exitstatus'] == 1


def test_failed_worker_without_a_reported_failure_is_incomplete(make_state):
    state = make_state()
    populated(state)
    receipt = state.receipts.pop('gw0')
    receipt['pytest_exitstatus'] = 1
    node = SimpleNamespace(gateway=SimpleNamespace(id='gw0'), workeroutput={'bpu_evidence': receipt})
    state.pytest_testnodedown(node, None)
    state.validated_results()
    assert 'unexplained worker tests-failed exit: gw0' in state.errors


@pytest.mark.parametrize('exitstatus', (2, 3, 4, 5))
def test_non_test_failure_exits_remain_integrity_errors(make_state, exitstatus):
    state = make_state()
    nodeid = populated(state)
    state.reports[nodeid]['call'] = phase(status='FAIL', outcome='failed')
    receipt = state.receipts.pop('gw0')
    receipt['pytest_exitstatus'] = exitstatus
    node = SimpleNamespace(gateway=SimpleNamespace(id='gw0'), workeroutput={'bpu_evidence': receipt})
    state.pytest_testnodedown(node, None)
    state.validated_results()
    assert f'worker exitstatus: gw0: {exitstatus}' in state.errors


def report(nodeid='tests/unit/test_a.py::test_same[p0]', *, when='call', outcome='passed', worker='gw0'):
    return SimpleNamespace(nodeid=nodeid, when=when, outcome=outcome,
        failed=outcome=='failed', skipped=outcome=='skipped', longrepr='',
        user_properties=[('bpu_features', ['F']), ('bpu_worker', worker)])


@pytest.mark.parametrize('when,outcome,xfail,expected', (
    ('setup','passed',False,None), ('teardown','passed',False,None),
    ('call','passed',False,'PASS'), ('call','failed',False,'FAIL'),
    ('setup','failed',False,'ERROR'), ('teardown','failed',False,'ERROR'),
    ('call','skipped',False,'SKIP'), ('setup','skipped',False,'SKIP'),
    ('call','skipped',True,'XFAIL'), ('call','passed',True,'XPASS')))
def test_pytest_phase_status_is_preserved(when,outcome,xfail,expected):
    value = report(when=when,outcome=outcome)
    if xfail:
        value.wasxfail = 'known RTL defect'
    assert evidence.status_of(value) == expected


def test_strict_xpass_is_a_failure_not_an_ordinary_pass():
    value = report(outcome='failed')
    value.longrepr = '[XPASS(strict)] known RTL defect'
    assert evidence.status_of(value) == 'XPASS'


@pytest.mark.parametrize('statuses,expected', (
    ({'PASS','XPASS'},'XPASS'), ({'PASS','FAIL'},'FAIL'),
    ({'PASS','ERROR'},'ERROR'), ({'PASS','XFAIL'},'PASS'),
    ({'XFAIL'},'XFAIL'), ({'SKIP'},'SKIP'), (set(),'NOT_RUN')))
def test_feature_status_never_hides_unexpected_failure(statuses,expected):
    assert evidence.worst(statuses) == expected


def test_complete_worker_collection_and_lifecycle_is_accepted(make_state):
    state = make_state(); populated(state)
    tests, files = state.validated_results()
    assert not state.errors and tests[0]['status']=='PASS' and files==[]


@pytest.mark.parametrize('fault', (
    'missing_receipt','missing_collection','collection_count','collection_hash',
    'missing_test','extra_test','duplicate_collection_node','missing_setup',
    'missing_call','missing_teardown','wrong_worker','cross_worker_lifecycle'))
def test_incomplete_or_inconsistent_execution_is_rejected(make_state,fault):
    state = make_state(); nodeid = populated(state)
    if fault=='missing_receipt':state.receipts.clear()
    elif fault=='missing_collection':state.collections=set()
    elif fault=='collection_count':state.receipts['gw0']['collected_count']=2
    elif fault=='collection_hash':state.receipts['gw0']['collection_sha256']='changed'
    elif fault=='missing_test':state.reports.clear()
    elif fault=='extra_test':state.reports['other::test_a']=state.reports[nodeid]
    elif fault=='duplicate_collection_node':state.collected.append(nodeid)
    elif fault.startswith('missing_'):del state.reports[nodeid][fault.removeprefix('missing_')]
    elif fault=='wrong_worker':
        for value in state.reports[nodeid].values():value['worker']='gw99'
    else:state.reports[nodeid]['call']['worker']='gw1'
    state.validated_results()
    assert state.errors


@pytest.mark.parametrize('fault', ('changed','missing','outside_worker','duplicate','symlink'))
def test_artifact_identity_and_worker_ownership_are_enforced(make_state,tmp_path,fault):
    state = make_state();populated(state)
    root=state.run/'workers/gw0';root.mkdir(parents=True)
    path=root/'functional-coverage.json';path.write_text('{}')
    row=dict(kind='functional',**evidence.fingerprint(path))
    state.receipts['gw0']['files']=[row]
    if fault=='changed':path.write_text('{"changed":true}')
    elif fault=='missing':path.unlink()
    elif fault=='outside_worker':
        outside=tmp_path/'outside.json';outside.write_text('{}')
        state.receipts['gw0']['files']=[dict(kind='functional',**evidence.fingerprint(outside))]
    elif fault=='duplicate':state.receipts['gw0']['files'].append(row.copy())
    else:
        target=tmp_path/'other.json';target.write_text('{}');path.unlink();path.symlink_to(target)
    state.validated_results()
    assert state.errors


def test_duplicate_test_phase_is_not_silently_overwritten(make_state):
    state=make_state();populated(state)
    state.pytest_runtest_logreport(report())
    assert any('duplicate report' in error for error in state.errors)


def test_worker_crash_is_sticky_even_with_later_valid_receipt(make_state):
    state=make_state();populated(state)
    node=SimpleNamespace(gateway=SimpleNamespace(id='gw0'),workeroutput={})
    state.pytest_testnodedown(node, 'terminated')
    state.validated_results()
    assert any('worker crashed' in error for error in state.errors)


def test_collection_only_creates_no_execution_artifacts(make_state,tmp_path):
    state=make_state(collect=True)
    state.pytest_sessionfinish(SimpleNamespace(exitstatus=0),0)
    assert not state.run.exists()


def test_existing_artifact_run_is_never_reused(make_state,tmp_path):
    directory=tmp_path/'results/existing';directory.mkdir(parents=True)
    sentinel=directory/'sentinel';sentinel.write_text('keep')
    with pytest.raises(FileExistsError):make_state(run=directory)
    assert sentinel.read_text()=='keep'


def test_run_cannot_escape_results(make_state,tmp_path):
    with pytest.raises(pytest.UsageError):make_state(run=tmp_path/'outside')


def test_serial_publication_preserves_feature_and_manifest_schemas(make_state):
    state=make_state(workers=0);nodeid=populated(state)
    state.started=state.collections=set();state.receipts.clear()
    for value in state.reports[nodeid].values():value['worker']='main'
    state.pytest_sessionfinish(SimpleNamespace(exitstatus=0),0)
    result=json.loads((state.run/'evidence.json').read_text())
    feature=json.loads((state.run/'feature-points.json').read_text())
    manifest=json.loads((state.run/'rtl-coverage-manifest.json').read_text())
    assert result['evidence_complete'] and result['collected_count']==1
    assert result['integrity_errors']==[]
    assert feature['summary']['status_counts']['PASS']==1
    assert manifest['format']=='bpu-rtl-coverage-manifest' and manifest['version']==1
    assert manifest['files']==[]


def test_missing_lifecycle_forces_pytest_failure_and_diagnostic_report(make_state):
    state=make_state(workers=0);nodeid=populated(state)
    state.started=state.collections=set();state.receipts.clear()
    state.reports[nodeid]={'call':phase('main')}
    session=SimpleNamespace(exitstatus=0)
    state.pytest_sessionfinish(session,0)
    assert session.exitstatus==pytest.ExitCode.TESTS_FAILED
    data=json.loads((state.run/'evidence.json').read_text())
    assert not data['evidence_complete'] and data['integrity_errors']
