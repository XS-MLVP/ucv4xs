"""Production policy must not fork toffee's collectors or credit fake bins."""
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.coverage.exports import write_functional_coverage, set_functional_exports, reset_functional_exports
from suites.frontend.bpu.pytest_plugins.managed import measured_functional_case, ManagedFeatures
from tools.managed_regression import managed_command, execution_verdicts


@pytest.mark.parametrize('node,measured', [
    ('tests/bpu/testcase/test_main.py::test_real', True),
    ('tests/ras/testcase/test_stack.py::test_real[x]', True),
    ('tests/bpu/scoreboard/test_main.py::test_model', False),
    ('tests/framework/test_parallel_matrices.py::test_fake', False),
    ('tests/bpu/drivers/test_main.py::test_encode', False),
])
def test_only_dut_scenarios_automatically_contribute_functional_measurements(node, measured):
    assert measured_functional_case(node) is measured


@pytest.mark.parametrize('enabled', [False, True])
def test_legacy_explicit_exports_are_disabled_only_in_managed_mode(tmp_path, enabled):
    calls = []
    database = NS(write_json=lambda path: calls.append(path))
    token = set_functional_exports(enabled)
    try:
        write_functional_coverage(database, tmp_path/'unused.json')
        assert calls == ([tmp_path/'unused.json'] if enabled else [])
    finally:
        reset_functional_exports(token)


@pytest.mark.parametrize('workers', [1, 8, 64])
def test_production_runner_owns_merging_without_legacy_or_export_flags(tmp_path, workers):
    command = managed_command(tmp_path, NS(workers=workers, select=None, regression_profile='production'))
    assert command[1:4] == ['-m', 'toffee', 'run']
    assert command[command.index('--workers')+1] == str(workers)
    assert '--bpu-full-suite' in command
    assert not any('artifact-run' in arg or 'rtl-retention' in arg or 'export-coverage-json' in arg for arg in command)
    assert ('--maxschedchunk=1' in command) is (workers>1)


def test_selected_scopes_do_not_claim_full_functional_acceptance(tmp_path):
    node = 'tests/bpu/testcase/test_main.py::test_real'
    command = managed_command(tmp_path, NS(workers=2, select=[node], regression_profile='production'))
    assert '--bpu-full-suite' not in command and command[-1] == node


def test_legacy_replay_does_not_silently_ignore_managed_debug_flags():
    from tools.refresh_coverage import main
    with pytest.raises(SystemExit) as error:
        main(['--engine=legacy','--keep-coverage-inputs'])
    assert error.value.code==2


@pytest.mark.parametrize('flag,forwarded',[
    ('keep_coverage_inputs',['--keep-coverage-inputs']),
    ('export_coverage_json',['--export-coverage-json']),
    ('dump_trace',['--dump-trace','--keep-coverage-inputs']),
])
def test_debug_artifacts_are_retained_only_by_explicit_request(tmp_path,flag,forwarded):
    args=NS(workers=1, select=['tests/bpu/testcase/test_main.py'], regression_profile='production', **{flag:True})
    command=managed_command(tmp_path,args)
    assert all(value in command for value in forwarded)


def test_junit_diagnostic_preserves_ordinary_failure_and_strict_xfail(tmp_path):
    path = tmp_path/'junit.xml'
    path.write_text('<testsuites><testsuite><testcase classname="tests.x" name="test_pass" />'
        '<testcase classname="tests.x" name="test_fail"><failure /></testcase>'
        '<testcase classname="tests.x" name="test_xfail"><skipped type="pytest.xfail" /></testcase>'
        '</testsuite></testsuites>')
    nodes = [f'tests/x.py::test_{name}' for name in ('pass','fail','xfail')]
    assert execution_verdicts(path,nodes) == dict(zip(nodes, ('PASS','FAIL','XFAIL')))


def test_junit_rejects_unexpected_skipping(tmp_path):
    path = tmp_path/'junit.xml'
    path.write_text('<testsuites><testsuite><testcase classname="tests.x" name="test_skip"><skipped /></testcase></testsuite></testsuites>')
    with pytest.raises(ValueError,match='skip'):
        execution_verdicts(path,['tests/x.py::test_skip'])


def test_project_domain_hook_rejects_mixed_worker_lifecycle(tmp_path):
    config = NS(workerinput={}, _bpu_feature_ids=set(), _bpu_feature_plan=[])
    features = ManagedFeatures(config,tmp_path)
    features.phases['tests/x.py::test_x'] = {'setup':dict(worker='gw0'),'call':dict(worker='gw1'),'teardown':dict(worker='gw0')}
    try:
        with pytest.raises(ValueError,match='mixed-owner'):
            features.pytest_toffee_coverage(config,None,[],0)
    finally:
        features.pytest_unconfigure()


@pytest.mark.parametrize('node,exported',[
    ('tests/bpu/testcase/test_real.py::test_real', False),
    ('tests/bpu/scoreboard/test_serializer.py::test_json_contract', True),
])
def test_explicit_serializer_contracts_remain_testable_without_dut_credit(tmp_path,node,exported):
    features=ManagedFeatures(NS(workerinput={}),tmp_path)
    protocol=features.pytest_runtest_protocol(NS(nodeid=node))
    calls=[]
    try:
        next(protocol)
        write_functional_coverage(NS(write_json=lambda path:calls.append(path)),tmp_path/'test.json')
        assert bool(calls) is exported
        with pytest.raises(StopIteration):next(protocol)
    finally:
        protocol.close()
        features.pytest_unconfigure()


def test_project_export_policy_never_monkeypatches_framework_methods():
    import ast
    path = Path(__file__).resolve().parents[2]/'coverage/exports.py'
    for node in ast.walk(ast.parse(path.read_text())):
        assert not (isinstance(node,ast.Assign) and any(isinstance(t,ast.Attribute) for t in node.targets))


def test_report_protection_accepts_compaction_without_resurrecting_old_runs(tmp_path):
    import json
    from tools.managed_regression import snapshot_publications
    from tools.refresh_coverage import digest
    results=tmp_path/'results';current=results/'current';current.mkdir(parents=True)
    lcov=current/'bpu.info';lcov.write_text('SF:example.sv\nDA:1,1\nend_of_record\n')
    bundle=current/'evidence.zip';bundle.write_bytes(b'byte-exact compact evidence')
    (current/'native-index.json').write_text(json.dumps(dict(dut=dict(bpu=dict(
        lcov_file='results/current/bpu.info',sha256=digest(lcov),
        inputs=[dict(original_path='results/deleted-old-run/rtl-lines/bpu.info')])))))
    (current/'evidence-index.json').write_text(json.dumps(dict(bundle='results/current/evidence.zip',sha256=digest(bundle))))
    result=snapshot_publications(results)
    assert set(result)=={'current/bpu.info','current/evidence.zip','current/native-index.json','current/evidence-index.json'}
    assert not (results/'deleted-old-run').exists()
    assert result['current/bpu.info']==digest(lcov)


@pytest.mark.parametrize('fault',('missing','changed','foreign'))
def test_current_baseline_protection_rejects_missing_changed_or_foreign_payload(tmp_path,fault):
    import json
    from tools.managed_regression import snapshot_publications
    from tools.refresh_coverage import digest
    results=tmp_path/'results';current=results/'current';current.mkdir(parents=True)
    payload=(tmp_path if fault=='foreign' else current)/'payload';payload.write_bytes(b'original')
    checksum=digest(payload)
    (current/'evidence-index.json').write_text(json.dumps(dict(bundle=str(payload),sha256=checksum)))
    if fault=='missing':payload.unlink()
    if fault=='changed':payload.write_bytes(b'changed')
    with pytest.raises(ValueError,match='current baseline artifact'):snapshot_publications(results)


def test_legacy_report_protection_keeps_all_existing_publications(tmp_path):
    from tools.managed_regression import snapshot_publications,CANONICAL
    results=tmp_path/'results';results.mkdir()
    for name in CANONICAL:(results/name).write_text(name)
    assert set(snapshot_publications(results))==set(CANONICAL)
