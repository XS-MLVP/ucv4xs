"""No-native controls for per-DUT registration, collection and RTL identity.

These are new environment selftests, separate from the migrated original nodes.
Only synthetic metadata, text and receipts are created in tmp_path. Runtime
validation is stubbed solely to reach the real verify_rtl/open_dut boundary;
the native import is replaced by a sentinel, never an actual binding.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from ucv.config import Project

from suites.vector.vagq import ROOT
from suites.vector.vagq.testbenches.shared.env import native

pytestmark = [pytest.mark.selftest, pytest.mark.toffee_functional_coverage(False)]

DUTS = (
    'AddrGen', 'MaskGen', 'MergeCtrl', 'NewPipelineConnectPipe', 'NewPipelineConnectPipe_3',
    'OrderedPermitCtrl', 'SplitCtrl', 'StoreDataCtrl', 'VAGQ', 'VAGQArbiter',
    'VAGQEntryTable', 'VAGQManager',
)
LAZY_FIXTURES = (
    ('VAGQArbiter', 'arbiter', 'arbiter_env'),
    ('VAGQEntryTable', 'entrytable', 'entrytable_env'),
    ('MergeCtrl', 'merge', 'merge_env'),
    ('SplitCtrl', 'split', 'split_env'),
    ('StoreDataCtrl', 'storedata', 'storedata_env'),
    ('VAGQ', 'vagq', 'vagq_env'),
)


def _probe(tmp_path, mode, dut, selection):
    project = Project()
    output = tmp_path / 'probe.json'
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                       PYTHONPATH=os.pathsep.join((str(project.root), str(project.root / 'src'))))
    completed = subprocess.run([
        sys.executable, '-B', str(Path(__file__).with_name('_startup_probe.py')),
        mode, dut, str(tmp_path / 'vagq'), selection, str(output),
    ], cwd=project.root, env=environment, capture_output=True, text=True, timeout=60)
    (tmp_path / 'probe.log').write_text(completed.stdout + completed.stderr)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(output.read_text())


def _metadata(tmp_path, dut):
    path = tmp_path / 'vagq' / 'dut' / dut / 'signals.json'
    path.parent.mkdir(parents=True)
    # Picker-shaped synthetic leaves, not copied from any generated DUT.
    path.write_text(json.dumps({
        'clock': {'_': True, 'Pin': 'input', 'High': 0, 'Low': 1},
        'reset': {'_': True, 'Pin': 'input', 'High': 0, 'Low': 1},
        'io_synthetic_input': {'_': True, 'Pin': 'input', 'High': 7, 'Low': 0},
        'io_synthetic_output': {'_': True, 'Pin': 'output', 'High': 7, 'Low': 0},
    }))
    return path


@pytest.mark.parametrize('dut', DUTS)
def test_selected_dut_collects_with_only_its_own_metadata(tmp_path, dut):
    path = _metadata(tmp_path, dut)
    workspace = json.loads((ROOT / 'workspace.json').read_text())
    selected = workspace['duts'][dut]['tests']
    assert len(selected) == 1
    report = _probe(tmp_path, 'collect', dut, selected[0])
    assert all(node.startswith(selected[0] + '/') for node in report['items'])
    assert set(report['metadata_reads']) <= {str(path)}
    assert sorted(p.name for p in (tmp_path / 'vagq' / 'dut').iterdir()) == [dut]


@pytest.mark.parametrize('dut,testbench', (('VAGQArbiter', 'arbiter'), ('VAGQ', 'vagq')))
def test_model_entry_collects_without_fixture_import_order(tmp_path, dut, testbench):
    path = _metadata(tmp_path, dut)
    selection = f'testbenches/{testbench}/tests/test_model.py'
    report = _probe(tmp_path, 'collect', dut, selection)
    assert all(node.startswith(selection + '::') for node in report['items'])
    assert set(report['metadata_reads']) <= {str(path)}


@pytest.mark.parametrize('dut,testbench,fixture', LAZY_FIXTURES, ids=[row[0] for row in LAZY_FIXTURES])
def test_metadata_is_read_on_fixture_use_not_registration(tmp_path, dut, testbench, fixture):
    selection = f'suites.vector.vagq.testbenches.{testbench}.tests.fixtures:{fixture}'
    report = _probe(tmp_path, 'fixture', dut, selection)
    assert report['registration_reads'] == []
    assert len(report['metadata_reads']) == 1


def _receipt(tmp_path, dut, *, fault=None):
    directory = tmp_path / 'rtl' / dut
    directory.mkdir(parents=True)
    text = b'Synthetic identity control only; not design RTL.\n'
    (directory / 'synthetic.txt').write_bytes(text)
    receipt = {'baseline': Project().suite('vagq').baseline,
               'files': {'synthetic.txt': sha256(text).hexdigest()}}
    if fault == 'wrong_baseline':
        receipt['baseline'] = {'synthetic': 'incorrect baseline'}
    elif fault == 'wrong_hash':
        receipt['files']['synthetic.txt'] = '0' * 64
    elif fault == 'missing_rtl':
        (directory / 'synthetic.txt').unlink()
    elif fault == 'empty_files':
        receipt['files'] = {}
    if fault != 'missing_receipt':
        (directory / 'source.json').write_text(json.dumps(receipt))


class BindingReached(Exception):
    pass


def _loader_boundary(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(native, 'ROOT', tmp_path)
    monkeypatch.setattr(native, 'validate_runtime', lambda: calls.append('runtime'))

    def import_binding(name):
        calls.append(name)
        raise BindingReached(name)

    monkeypatch.setattr(native, 'importlib', SimpleNamespace(import_module=import_binding))
    return calls


@pytest.mark.parametrize('dut', DUTS)
def test_open_dut_checks_selected_receipt_without_unselected_products(monkeypatch, tmp_path, dut):
    _receipt(tmp_path, dut)
    calls = _loader_boundary(monkeypatch, tmp_path)
    with pytest.raises(BindingReached, match=f'dut.{dut}'):
        with native.open_dut(dut, tmp_path / 'output'):
            pytest.fail('the synthetic control must never construct a DUT')
    assert calls == ['runtime', 'dut.' + dut]


@pytest.mark.parametrize('dut', ('NewPipelineConnectPipe', 'NewPipelineConnectPipe_3'))
@pytest.mark.parametrize('fault', ('missing_receipt', 'wrong_baseline', 'wrong_hash', 'missing_rtl', 'empty_files'))
def test_open_dut_rejects_missing_or_invalid_selected_identity(monkeypatch, tmp_path, dut, fault):
    _receipt(tmp_path, dut, fault=fault)
    calls = _loader_boundary(monkeypatch, tmp_path)
    with pytest.raises((FileNotFoundError, RuntimeError)):
        with native.open_dut(dut, tmp_path / 'output'):
            pytest.fail('invalid identity reached native construction')
    assert calls == ['runtime']


def test_joint_dut_verification_requires_every_declared_participant(monkeypatch, tmp_path):
    _receipt(tmp_path, 'MaskGen')
    _receipt(tmp_path, 'SplitCtrl', fault='wrong_hash')
    monkeypatch.setattr(native, 'ROOT', tmp_path)
    native.verify_rtl('MaskGen')
    with pytest.raises(RuntimeError, match='SplitCtrl/synthetic.txt'):
        native.verify_rtl('MaskGen', 'SplitCtrl')


def test_explicit_full_verification_still_checks_all_roots(monkeypatch, tmp_path):
    for dut in DUTS:
        _receipt(tmp_path, dut)
    monkeypatch.setattr(native, 'ROOT', tmp_path)
    native.verify_rtl()
    (tmp_path / 'rtl' / 'VAGQManager' / 'synthetic.txt').write_text('tampered synthetic control')
    native.verify_rtl('NewPipelineConnectPipe')
    with pytest.raises(RuntimeError, match='VAGQManager/synthetic.txt'):
        native.verify_rtl()


def test_unknown_dut_is_rejected_before_native_import(monkeypatch, tmp_path):
    calls = _loader_boundary(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match='Unknown VAGQ DUT'):
        with native.open_dut('not-a-declared-dut', tmp_path / 'output'):
            pytest.fail('unknown DUT reached construction')
    assert calls == ['runtime']
