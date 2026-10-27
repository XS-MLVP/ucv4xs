"""Build metadata comes only from a verified successful matching build."""
import json
from pathlib import Path

import pytest
from tools import rebuild_memory_direct as staged

FLAGS = '--no-coverage-expr;--no-coverage-fsm;--MMD;--MP;--MAKEFLAGS;-DVL_INLINE_OPT=inline;-O3;--instr-count-dpi;0'


@pytest.fixture
def build_record(tmp_path):
    stage = tmp_path / 'staging'
    package = stage / 'dut/bpu'
    package.mkdir(parents=True)
    for name in ('__init__.py', 'signals.json', 'BpuDut_offset.yaml',
                 '_UT_BpuDut.so', 'libUTBpuDut.so', 'BpuDut.v'):
        (package / name).write_text('synthetic fixture: ' + name)
    identities = {path.name: staged.digest(path) for path in package.iterdir()}
    log = stage / 'bpu-build.log'
    log.write_text('-- Verilator 5.052, trace option: TRACE_FST\n-- Verilator flags: ' + FLAGS + '\n')
    receipt = dict(dut='bpu', process_exitstatus=0, observed_child_exitstatus=0,
        package_sha256=identities, log=str(log), log_sha256=staged.digest(log),
        command=['picker', 'export', 'Bpu.sv', '--rw', 'mem_direct', '-c', '-w', 'memory-direct.fst'])
    receipt_path = stage / 'bpu-build.exit.json'
    def save():
        receipt_path.write_text(json.dumps(receipt))
    save()
    return stage, package, identities, log, receipt, receipt_path, save


def test_current_flags_are_taken_from_the_verified_log(build_record):
    stage, package, identities, log, receipt, receipt_path, save = build_record
    before = receipt_path.read_bytes()
    settings = staged.validated_build_settings('bpu', stage, identities)
    assert settings['verilator_flags'] == FLAGS.split(';')
    assert '--vpi' not in settings['verilator_flags'] and '--public-flat-rw' not in settings['verilator_flags']
    assert settings['trace_feature'] == 'fst' and settings['coverage_feature']
    assert 'not complete Verilator argv' in settings['verilator_flags_scope']
    assert settings['build_log'] == dict(path=str(log), sha256=staged.digest(log))
    assert receipt_path.read_bytes() == before and not (package / 'build-provenance.json').exists()


@pytest.mark.parametrize('fault', [None, 'parent_changed', 'make_changed'])
def test_resumed_build_keeps_and_verifies_failed_parent(build_record, fault):
    stage, package, identities, log, original, original_path, save = build_record
    original.update(process_exitstatus=1, observed_child_exitstatus=1)
    save()
    failed = original_path.read_bytes()
    resumed_log = stage / 'bpu-resume-build.log'
    resumed_log.write_bytes(log.read_bytes())
    receipt = dict(original, process_exitstatus=0, observed_child_exitstatus=0,
        log=str(resumed_log), log_sha256=staged.digest(resumed_log), jobs=16,
        execution_command=['make', '-j', '16'],
        resume_of=dict(path=str(original_path), sha256=staged.digest(original_path)))
    if fault == 'make_changed':
        receipt['execution_command'] = ['make', 'unrelated']
    (stage / 'bpu-resume-build.exit.json').write_text(json.dumps(receipt))
    if fault == 'parent_changed':
        original['command'].append('--different-export')
        save()
    if fault:
        with pytest.raises(ValueError, match='resumed build'):
            staged.validated_build_settings('bpu', stage, identities)
    else:
        settings = staged.validated_build_settings('bpu', stage, identities)
        assert settings['build_execution_command'] == ['make', '-j', '16']
        assert settings['build_resume_of'] == receipt['resume_of']
        assert original_path.read_bytes() == failed


@pytest.mark.parametrize('nested', [False, True])
def test_incomplete_or_nested_native_binding_cannot_be_installed(build_record, nested):
    stage, package, *_ = build_record
    native = package / 'xspcomm'
    native.mkdir()
    if nested:
        for name in ('__init__.py', 'pyxspcomm.py', '_pyxspcomm.so', 'libxspcomm.so.3'):
            (native / name).write_text('synthetic fixture')
        (native / 'xspcomm').mkdir()
    with pytest.raises(AssertionError, match='copied xspcomm binding'):
        staged.validate(package, 'bpu')


@pytest.mark.parametrize('fault', [
    'missing_receipt', 'wrong_DUT', 'build_failure', 'child_failure', 'boolean_exit',
    'package_mismatch', 'wrong_log_path', 'missing_log', 'log_changed', 'log_symlink',
    'receipt_symlink', 'missing_flags', 'duplicate_flags', 'empty_flags', 'VPI', 'VPI_equals',
    'public_flat', 'public_flat_equals', 'missing_trace', 'duplicate_trace', 'wrong_trace',
    'wrong_backend', 'no_coverage', 'no_trace_command', 'bad_command_type',
])
def test_invalid_build_record_is_rejected_before_install(build_record, fault, tmp_path):
    stage, package, identities, log, receipt, receipt_path, save = build_record
    if fault == 'wrong_DUT': receipt['dut'] = 'sc'
    elif fault == 'build_failure': receipt['process_exitstatus'] = 1
    elif fault == 'child_failure': receipt['observed_child_exitstatus'] = 1
    elif fault == 'boolean_exit': receipt['process_exitstatus'] = False
    elif fault == 'package_mismatch': receipt['package_sha256'] = {}
    elif fault == 'wrong_log_path': receipt['log'] = str(tmp_path / 'outside.log')
    elif fault == 'wrong_backend': receipt['command'][receipt['command'].index('--rw')+1] = 'dpi'
    elif fault == 'no_coverage': receipt['command'].remove('-c')
    elif fault == 'no_trace_command': receipt['command'].remove('-w')
    elif fault == 'bad_command_type': receipt['command'] = 'picker export'
    elif fault == 'missing_flags': log.write_text('-- Verilator 5.052, trace option: TRACE_FST\n')
    elif fault == 'duplicate_flags': log.write_text(log.read_text() + '-- Verilator flags: ' + FLAGS + '\n')
    elif fault == 'empty_flags': log.write_text('-- Verilator 5.052, trace option: TRACE_FST\n-- Verilator flags: \n')
    elif fault in ('VPI', 'VPI_equals', 'public_flat', 'public_flat_equals'):
        option = dict(VPI='--vpi', VPI_equals='--vpi=1', public_flat='--public-flat-rw', public_flat_equals='--public-flat-rw=1')[fault]
        log.write_text(log.read_text().rstrip() + ';' + option + '\n')
    elif fault == 'missing_trace': log.write_text('-- Verilator flags: ' + FLAGS + '\n')
    elif fault == 'duplicate_trace': log.write_text(log.read_text() + '-- Verilator 5.052, trace option: TRACE_FST\n')
    elif fault == 'wrong_trace': log.write_text(log.read_text().replace('TRACE_FST', 'TRACE_VCD'))
    if fault not in ('missing_log', 'log_symlink', 'log_changed'):
        receipt['log_sha256'] = staged.digest(log)
    save()
    if fault == 'missing_receipt': receipt_path.unlink()
    elif fault == 'missing_log': log.unlink()
    elif fault == 'log_changed': log.write_text(log.read_text() + 'unrecorded edit\n')
    elif fault == 'log_symlink':
        other = tmp_path / 'outside.log'; other.write_bytes(log.read_bytes()); log.unlink(); log.symlink_to(other)
    elif fault == 'receipt_symlink':
        other = tmp_path / 'outside.json'; other.write_bytes(receipt_path.read_bytes()); receipt_path.unlink(); receipt_path.symlink_to(other)
    with pytest.raises((ValueError, FileNotFoundError)):
        staged.validated_build_settings('bpu', stage, identities)
    assert package.exists() and not (package / 'build-provenance.json').exists()


@pytest.mark.parametrize('corrupt', (False, True))
def test_actual_installer_corrects_metadata_or_preserves_target_before_move(build_record, monkeypatch, tmp_path, corrupt):
    stage, package, identities, log, receipt, receipt_path, save = build_record
    root = tmp_path / 'repo'
    target = root / 'dut/bpu'
    target.mkdir(parents=True)
    old = dict(format='bpu-dut-build-provenance', version=1, dut='bpu',
               verilator_flags=['--coverage', '--vpi', '--public-flat-rw'])
    old_path = target / 'build-provenance.json'
    old_path.write_text(json.dumps(old))
    before = old_path.read_bytes()
    monkeypatch.setattr(staged, 'ROOT', root)
    monkeypatch.setattr(staged, 'validate', lambda current, name: dict(identities))
    if corrupt:
        log.write_text(log.read_text() + 'unrecorded edit\n')
        with pytest.raises(ValueError, match='log identity'):
            staged.install('bpu', stage)
        assert old_path.read_bytes() == before and package.exists()
        assert not (stage / 'backup-dut/bpu').exists()
        return
    staged.install('bpu', stage)
    installed = json.loads(old_path.read_text())
    assert installed['verilator_flags'] == FLAGS.split(';')
    assert installed['access_mode'] == 'MEM_DIRECT' and installed['VPI'] is False
    assert installed['trace_feature'] == 'fst' and installed['coverage_feature'] is True
    assert installed['memory_direct_package_sha256'] == identities
    assert (stage / 'backup-dut/bpu/build-provenance.json').read_bytes() == before
    assert not package.exists()
