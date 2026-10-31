"""Production refresh cannot publish a partial or mixed-worker invocation."""
import json
from pathlib import Path

import pytest

from suites.frontend.bpu.pytest_plugins.evidence import collection_digest
from suites.frontend.bpu.pytest_plugins.evidence import fingerprint
from tools import refresh_coverage as refresh


@pytest.mark.parametrize('workers', [1, 4, 8, 16, 32])
def test_production_command_uses_isolated_outputs_and_fixed_worker_count(tmp_path, workers):
    command = refresh.pytest_command(tmp_path, workers)
    assert f'--artifact-run={tmp_path}/pytest-artifacts' in command
    assert '--rtl-retention=merged' in command
    assert '--regression-profile=production' in command
    if workers == 1:
        assert '-n' not in command
    else:
        assert command[command.index('-n') + 1] == str(workers)
        assert '--dist=load' in command and '--max-worker-restart=0' in command
        assert '--maxschedchunk=1' in command


def test_collection_and_execution_can_request_deep_physical_profile(tmp_path):
    assert '--regression-profile=physical' in refresh.pytest_command(tmp_path, 4, 'physical')
    with pytest.raises(ValueError, match='unknown regression profile'):
        refresh.pytest_command(tmp_path, 4, 'typo')


@pytest.mark.parametrize('workers', [-4, 0])
def test_invalid_worker_count_is_rejected(workers):
    with pytest.raises(ValueError, match='positive'):
        refresh.pytest_command(Path('results/new'), workers)
    with pytest.raises(SystemExit) as error:
        refresh.main([f'--workers={workers}'])
    assert error.value.code == 2


@pytest.fixture
def execution(tmp_path, monkeypatch):
    monkeypatch.setattr(refresh, 'ROOT', tmp_path)
    run = tmp_path / 'results/run'
    root = run / 'workers/gw0'
    root.mkdir(parents=True)
    node = 'tests/a/test_a.py::test_one[p0]'
    files = []
    for kind, name in [('rtl', 'native/bpu/native-merged.dat'),
                       ('functional', 'case/results/bpu/functional-coverage.json')]:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}')
        files.append(dict(kind=kind, **fingerprint(path)))
    receipt = dict(worker='gw0', collected_count=1, collection_sha256=collection_digest([node]),
        files=files, pytest_exitstatus=0, integrity_errors=[],
        native_retention=dict(mode='merged', input_files_by_dut=dict(bpu=2)))
    path = root / 'receipt.json'
    path.write_text(json.dumps(receipt))
    evidence = dict(format='bpu-pytest-evidence', version=1, pytest_exitstatus=0,
        evidence_complete=True, integrity_errors=[], collected_count=1,
        test_status_counts=dict(PASS=1),
        tests=[dict(nodeid=node, status='PASS', phases={
            phase: dict(worker='gw0', status='PASS' if phase == 'call' else None, outcome='passed')
            for phase in ('setup', 'call', 'teardown')})],
        workers=[dict(worker='gw0', receipt=str(path), **fingerprint(path))])
    manifests = {
        'evidence.json': evidence,
        'functional-manifest.json': dict(format='bpu-functional-manifest', version=1,
            pytest_exitstatus=0, files=[dict(worker='gw0', **files[1])]),
        'rtl-coverage-manifest.json': dict(format='bpu-rtl-coverage-manifest', version=1,
            pytest_exitstatus=0, files=[str(Path(files[0]['path']).relative_to(tmp_path))],
            native_retention=dict(mode='merged', input_files_by_dut=dict(bpu=2), input_files=2)),
    }

    def save():
        for name, value in manifests.items():
            (run / name).write_text(json.dumps(value))

    save()
    return run, [node], {node: 'PASS'}, manifests, receipt, save


def test_current_run_only_inputs_are_accepted(execution):
    run, nodes, verdicts, manifests, receipt, save = execution
    assert refresh.execution_inputs(run, nodes, verdicts) == [Path(receipt['files'][1]['path'])]
    old = run.parent / 'bpu/functional-coverage-old.json'
    old.parent.mkdir(); old.write_text('{"stale":true}')
    assert old not in refresh.execution_inputs(run, nodes, verdicts)


@pytest.mark.parametrize('scope', ['../external', 'tools/refresh_coverage.py', 'tests/does-not-exist.py'])
def test_selected_scope_cannot_escape_existing_repository_tests(scope):
    with pytest.raises(SystemExit) as error:
        refresh.main(['--select', scope])
    assert error.value.code == 2


def test_selected_no_dut_tests_need_receipts_but_not_fabricated_coverage(execution):
    run, nodes, verdicts, manifests, receipt, save = execution
    receipt['files'] = []
    receipt['native_retention']['input_files_by_dut'] = {}
    path = run / 'workers/gw0/receipt.json'
    path.write_text(json.dumps(receipt))
    manifests['evidence.json']['workers'][0].update(fingerprint(path))
    manifests['functional-manifest.json']['files'] = []
    manifests['rtl-coverage-manifest.json'].update(files=[], native_retention=dict(
        mode='merged', input_files_by_dut={}, input_files=0))
    save()
    assert refresh.execution_inputs(run, nodes, verdicts, require_coverage=False) == []
    with pytest.raises(ValueError, match='no current-run functional/native coverage'):
        refresh.execution_inputs(run, nodes, verdicts)


@pytest.mark.parametrize('fault', [
    'failed', 'incomplete', 'errors', 'count', 'verdict', 'status_counts', 'missing_worker',
    'duplicate_worker', 'receipt_changed', 'receipt_collection', 'receipt_failed',
    'artifact_changed', 'artifact_missing', 'artifact_escape', 'artifact_duplicate',
    'missing_phase', 'wrong_worker', 'functional_extra', 'functional_missing',
    'rtl_extra', 'rtl_missing', 'native_count', 'native_mode',
])
def test_partial_corrupt_or_mixed_evidence_is_rejected(execution, fault, tmp_path):
    run, nodes, verdicts, manifests, receipt, save = execution
    evidence = manifests['evidence.json']
    worker = evidence['workers'][0]
    receipt_path = Path(worker['path'])
    if fault == 'failed': evidence['pytest_exitstatus'] = 1
    elif fault == 'incomplete': evidence['evidence_complete'] = False
    elif fault == 'errors': evidence['integrity_errors'] = ['crash']
    elif fault == 'count': evidence['collected_count'] = 2
    elif fault == 'verdict': evidence['tests'][0]['status'] = 'XFAIL'
    elif fault == 'status_counts': evidence['test_status_counts'] = dict(PASS=0)
    elif fault == 'missing_worker': evidence['workers'] = []
    elif fault == 'duplicate_worker': evidence['workers'].append(worker.copy())
    elif fault == 'receipt_changed': receipt_path.write_text('{}')
    elif fault.startswith('receipt_') or fault in ('artifact_escape', 'artifact_duplicate'):
        if fault == 'receipt_collection': receipt['collection_sha256'] = 'wrong'
        elif fault == 'receipt_failed': receipt['pytest_exitstatus'] = 1
        elif fault == 'artifact_duplicate': receipt['files'].append(receipt['files'][0])
        else:
            outside = tmp_path / 'outside.json'; outside.write_text('{}')
            receipt['files'][1] = dict(kind='functional', **fingerprint(outside))
        receipt_path.write_text(json.dumps(receipt))
        worker.update(fingerprint(receipt_path))
    elif fault == 'artifact_changed': Path(receipt['files'][0]['path']).write_text('changed')
    elif fault == 'artifact_missing': Path(receipt['files'][0]['path']).unlink()
    elif fault == 'missing_phase': del evidence['tests'][0]['phases']['call']
    elif fault == 'wrong_worker': evidence['tests'][0]['phases']['call']['worker'] = 'gw1'
    elif fault == 'functional_extra': manifests['functional-manifest.json']['files'].append(receipt['files'][0])
    elif fault == 'functional_missing': manifests['functional-manifest.json']['files'] = []
    elif fault == 'rtl_extra': manifests['rtl-coverage-manifest.json']['files'].append('results/old.dat')
    elif fault == 'rtl_missing': manifests['rtl-coverage-manifest.json']['files'] = []
    elif fault == 'native_count': manifests['rtl-coverage-manifest.json']['native_retention']['input_files'] = 1
    else: manifests['rtl-coverage-manifest.json']['native_retention']['mode'] = 'raw'
    save()
    with pytest.raises((ValueError, OSError)):
        refresh.execution_inputs(run, nodes, verdicts)


def test_new_source_files_and_dut_changes_are_included_in_automatic_epoch(tmp_path, monkeypatch):
    monkeypatch.setattr(refresh, 'ROOT', tmp_path)
    monkeypatch.setattr(refresh, 'find_spec', lambda name: type('Spec', (), {
        'origin': None, 'submodule_search_locations': []})())
    for name in ('pytest.ini', 'requirements.txt', 'verification_plan.json',
                 'new.py', 'tests/unit.py', 'tools/runner.py',
                 'rtl/bpu/test.v', 'dut/bpu/native.so'):
        path = tmp_path / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(name)
    before = refresh.source_epoch()
    added = tmp_path / 'tests/new.py'; added.write_text('new test')
    assert str(added) in refresh.source_epoch() and before != refresh.source_epoch()
    binary = tmp_path / 'dut/bpu/native.so'; binary.write_text('changed')
    assert refresh.source_epoch()[str(binary)] != before[str(binary)]


@pytest.mark.parametrize('directory', ['dut/bpu', 'runtime/xspcomm'])
@pytest.mark.parametrize('suffix', ['3', '0.3.0'])
def test_versioned_native_libraries_are_frozen(tmp_path, monkeypatch, directory, suffix):
    monkeypatch.setattr(refresh, 'ROOT', tmp_path)
    dependency = tmp_path / 'runtime/xspcomm'
    dependency.mkdir(parents=True)
    monkeypatch.setattr(refresh, 'find_spec', lambda name: type('Spec', (), {
        'origin': None, 'submodule_search_locations': [str(dependency)]})())
    for name in ('pytest.ini', 'requirements.txt', 'verification_plan.json'):
        (tmp_path / name).write_text(name)
    binary = tmp_path / directory / f'libxspcomm.so.{suffix}'
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text('original native library')
    before = refresh.source_epoch()
    assert str(binary) in before
    binary.write_text('changed versioned native library')
    assert refresh.source_epoch()[str(binary)] != before[str(binary)]
