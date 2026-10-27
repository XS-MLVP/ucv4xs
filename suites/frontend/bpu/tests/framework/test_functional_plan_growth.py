"""Production gate reproduction and isolated no-DUT publication correction."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from tools import refresh_coverage as staged
import bpuverify.common.coverage.parallel as matrix_module
import bpuverify.common.coverage.rtl as native_module
import toffee.coverage_report as functional_module

NODE = 'tests/example/test_example.py::test_one'


def data():
    prior = dict(features=[dict(id='OLD', status='PASS', tests=[dict(nodeid=NODE, status='PASS')])])
    plan = dict(features=[dict(id='OLD'), dict(id='ADDED')])
    report = dict(features=[dict(id=identity, status='PASS', tests=[dict(nodeid=NODE, status='PASS')])
                           for identity in ('OLD', 'ADDED')],
                  summary=dict(planned=2, executed=2, passed=2, status_counts=dict(PASS=2)))
    return report, plan, prior, {NODE: 'PASS'}


def test_addition_is_accepted_without_changing_old_baseline():
    values = data()
    before = deepcopy(values)
    staged.validate_functional_points(*values)
    assert values == before


@pytest.mark.parametrize('fault', [
    'wrong_identity_same_count', 'missing_identity', 'duplicate_report', 'duplicate_plan',
    'removed_prior_point', 'empty_plan', 'not_run', 'skip', 'false_pass', 'empty_cases',
    'unknown_case', 'wrong_case_status', 'duplicate_case', 'planned_count', 'executed_count',
    'passed_count', 'bool_count', 'status_counts', 'negative_status_count', 'bool_status_count',
])
def test_incomplete_or_corrupt_growth_is_rejected(fault):
    report, plan, prior, verdicts = data()
    row = report['features'][1]
    if fault == 'wrong_identity_same_count': row['id'] = 'OTHER'
    elif fault == 'missing_identity': report['features'].pop()
    elif fault == 'duplicate_report': row['id'] = 'OLD'
    elif fault == 'duplicate_plan': plan['features'][1]['id'] = 'OLD'
    elif fault == 'removed_prior_point': plan['features'][0]['id'] = 'REPLACED'; report['features'][0]['id'] = 'REPLACED'
    elif fault == 'empty_plan': plan['features'] = []
    elif fault == 'not_run': row['status'] = 'NOT_RUN'
    elif fault == 'skip': row['tests'][0]['status'] = 'SKIP'
    elif fault == 'false_pass': row['status'] = 'XFAIL'
    elif fault == 'empty_cases': row['tests'] = []
    elif fault == 'unknown_case': row['tests'][0]['nodeid'] = 'unknown'
    elif fault == 'wrong_case_status': row['tests'][0]['status'] = 'XFAIL'
    elif fault == 'duplicate_case': row['tests'].append(deepcopy(row['tests'][0]))
    elif fault == 'planned_count': report['summary']['planned'] = 1
    elif fault == 'executed_count': report['summary']['executed'] = 1
    elif fault == 'passed_count': report['summary']['passed'] = 1
    elif fault == 'bool_count': report['summary']['planned'] = True
    elif fault == 'status_counts': report['summary']['status_counts'] = dict(PASS=1, XFAIL=1)
    elif fault == 'negative_status_count': report['summary']['status_counts']['FAIL'] = -1
    elif fault == 'bool_status_count': report['summary']['status_counts']['FAIL'] = False
    with pytest.raises(ValueError):
        staged.validate_functional_points(report, plan, prior, verdicts)


def test_existing_XFAIL_remains_executed_not_passed():
    report, plan, prior, verdicts = data()
    report['features'][0].update(status='XFAIL', tests=[dict(nodeid='known_defect', status='XFAIL')])
    verdicts['known_defect'] = 'XFAIL'
    report['summary'].update(passed=1, status_counts=dict(PASS=1, XFAIL=1, FAIL=0))
    staged.validate_functional_points(report, plan, prior, verdicts)


@pytest.mark.parametrize('corrupt,expected_exit,selected,coverage', [
    (False, 0, False, True), (True, 1, False, True), (False, 0, True, True), (False, 0, True, False)])
def test_actual_refresh_publication_path_for_plan_addition(tmp_path, monkeypatch, corrupt, expected_exit, selected, coverage):
    module = staged
    report, plan, prior, verdicts = data()
    if corrupt:
        report['features'][1]['id'] = 'WRONG_SAME_COUNT'
    # Matrix completeness has separate full-schema positive/negative tests;
    # this fixture isolates functional-plan publication behavior.
    monkeypatch.setattr(matrix_module, 'validate_parallel_case_coverage', lambda report, **scope: dict(regression_profile=scope['profile']))
    results = tmp_path / 'results'
    results.mkdir()
    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    baseline = dict(format='bpu-rtl-line-coverage', version=3, pytest_exitstatus=0, dut={})
    for name in module.NAMES:
        path = results / 'baseline' / f'{name}.info'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'TN:native\nSF:rtl/{name}.sv\nDA:1,1\nDA:2,0\nend_of_record\n')
        baseline['dut'][name] = dict(lcov_file=str(path), source_lines=dict(total=2, hit=1))
    save(results / 'rtl-line-coverage.json', baseline)
    save(results / 'feature-points.json', prior)
    save(results / 'rtl-coverage-manifest.json', {})
    save(results / 'summary.json', dict(full_regression_complete=True, process_exitstatus=0))
    (results / 'verification-report.html').write_text('old report')
    save(tmp_path / 'verification_plan.json', plan)
    scope = tmp_path / 'tests/example/test_example.py'
    scope.parent.mkdir(parents=True)
    scope.write_text('synthetic fixture only')
    before = {name: (results / name).read_bytes() for name in (
        'feature-points.json', 'rtl-line-coverage.json', 'rtl-coverage-manifest.json',
        'summary.json', 'verification-report.html')}
    output = results / 'new-run'
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module, 'source_epoch', lambda: {})
    monkeypatch.setattr(module.shutil, 'disk_usage', lambda _: SimpleNamespace(free=module.FLOOR+1))
    def fake_inputs(run, expected, tests, **options):
        assert expected == [NODE] and tests == verdicts
        assert options == (dict(require_coverage=False) if selected else {})
        return [run / 'functional-coverage.json'] if coverage else []
    monkeypatch.setattr(module, 'execution_inputs', fake_inputs)
    class Process:
        pid = 999999
        def __init__(self, command, *, cwd, env, stdout, stderr):
            if '--collect-only' in command:
                stdout.write(NODE + '\n')
            else:
                (output / 'pytest.xml').write_text('<testsuites><testsuite><testcase classname="tests.example.test_example" name="test_one" /></testsuite></testsuites>')
                run = output / 'pytest-artifacts'
                save(run / 'feature-points.json', report)
                save(run / 'rtl-coverage-manifest.json', {})
                save(run / 'functional-manifest.json', {})
        def wait(self):
            return 0
    monkeypatch.setattr(module.subprocess, 'Popen', Process)
    def native_report(manifest, destination):
        report = baseline if coverage else dict(baseline, dut={})
        save(destination, report)
        return report
    monkeypatch.setattr(native_module, 'build_report', native_report)
    monkeypatch.setattr(functional_module, 'load_functional_coverage', lambda _: dict(groups=[dict(coverage=100)]) if coverage else None)
    def generate(**options):
        assert coverage, 'no-DUT/no-functional-coverage runs must not fabricate a coverage report'
        options['output'].write_text('new qualified report')
    monkeypatch.setattr(functional_module, 'generate_unified_coverage_report', generate)
    arguments = [f'--run-dir={output}', '--workers=1', '--engine=legacy']
    if selected:
        arguments += ['--select', 'tests/example/test_example.py']
    assert module.main(arguments) == expected_exit
    terminal = json.loads((output / 'exit.json').read_text())
    assert terminal['process_exitstatus'] == expected_exit
    if expected_exit:
        assert 'current functional point identities differ' in terminal['failure']
        assert all((results / name).read_bytes() == payload for name, payload in before.items())
        assert not (results / 'rtl-lines').exists()
    elif selected:
        assert terminal['selected_regression_complete']
        assert not terminal['full_regression_complete'] and not terminal['reports_published']
        assert terminal['exact_selected_collection'] == 1
        assert all((results / name).read_bytes() == payload for name, payload in before.items())
        assert not (results / 'rtl-lines').exists()
        assert bool(terminal['coverage_report']) == coverage
        assert (output / 'verification-report.html').exists() == coverage
    else:
        assert terminal['full_regression_complete'] and terminal['reports_published']
        assert terminal['functional_points']['planned'] == terminal['functional_points']['executed'] == 2
        assert json.loads((results / 'feature-points.json').read_text()) == report
        assert len(list((results / 'rtl-lines').glob('*.info'))) == 10
