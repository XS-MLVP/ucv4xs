"""Consumption must preserve the native point table and native merge counts."""
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess

import pytest

from suites.frontend.bpu.coverage.native import NativeCoverageRun
from suites.frontend.bpu.coverage.native import collect_native_coverage
from suites.frontend.bpu.coverage.native import native_coverage_path
from suites.frontend.bpu.coverage.native import reset_native_coverage_run
from suites.frontend.bpu.coverage.native import set_native_coverage_run
from suites.frontend.bpu.coverage.rtl import _coverage_tool


@pytest.fixture(autouse=True)
def isolated_native_run():
    token = set_native_coverage_run(None)
    try:
        yield
    finally:
        reset_native_coverage_run(token)


def data(path, number=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ("v_line/Unit", "if", number),
        ("v_line/Unit", "else", 0),
        ("v_branch/Unit", "condition", number + 1),
        ("v_toggle/Unit", "bit[0]:0->1", number * 7),
        ("v_toggle/Unit", "bit[0]:1->0", 0),
        ("future_custom_type/Unit", "custom", number * 3),
    ]
    path.write_text('# SystemC::Coverage-3\n' + ''.join(
        f"C '\x01f\x02/source with spaces/Unit.sv\x01l\x0212\x01S\x0213-15"
        f"\x01page\x02{kind}\x01o\x02{arm}\x01h\x02TOP.unit' {count}\n"
        for kind, arm, count in rows))
    return path


@pytest.mark.parametrize('batch', (1, 2, 16))
@pytest.mark.parametrize('failed', (False, True))
def test_bounded_batches_equal_native_single_merge_without_dropping_any_type(tmp_path, batch, failed):
    originals = [data(tmp_path / 'original' / f'{index}.dat', index) for index in range(5)]
    expected = tmp_path / 'expected.dat'
    subprocess.run([_coverage_tool('bpu'), '--write', str(expected), *map(str, originals)], check=True)
    run = NativeCoverageRun(tmp_path / 'run', batch_size=batch)
    scratch = tmp_path / 'same-fixture-name.dat'
    for index, original in enumerate(originals):
        run.owner = f'case[{index}]'
        shutil.copyfile(original, scratch)
        destination = run.add('bpu', scratch)
        assert not scratch.exists(), 'pending dumps must not share a reused fixture filename'
        run.end_test(run.owner, failed=failed and index == 2)
        assert sum(map(len, run.pending.values())) < batch
    result = run.finish()
    assert destination.read_bytes() == expected.read_bytes()
    assert b"' 0\n" in destination.read_bytes()
    assert b'future_custom_type' in destination.read_bytes()
    assert result['input_files'] == 5 and result['input_files_by_dut'] == {'bpu': 5}
    assert result['input_bytes'] == sum(path.stat().st_size for path in originals)
    assert result['aggregates'][0]['sha256'] == sha256(expected.read_bytes()).hexdigest()
    assert not list((tmp_path / 'run/pending').rglob('*.dat'))
    retained = [row for row in result['inputs'] if 'retained_path' in row]
    assert len(retained) == int(failed)
    if retained:
        assert Path(retained[0]['retained_path']).read_bytes() == originals[2].read_bytes()
    assert all('spool_path' not in row for row in result['inputs'])


def test_multiple_duts_never_share_an_aggregate(tmp_path):
    run = NativeCoverageRun(tmp_path / 'run', batch_size=2)
    for name in ('bpu', 'tage'):
        run.owner = name
        run.add(name, data(tmp_path / f'{name}.dat'))
        run.end_test(name, failed=False)
    result = run.finish()
    assert result['input_files_by_dut'] == {'bpu': 1, 'tage': 1}
    assert {row['dut'] for row in result['aggregates']} == {'bpu', 'tage'}


@pytest.mark.parametrize('value', (0, -1, True, '16', None))
def test_bad_batch_rejected_without_creating_directory(tmp_path, value):
    with pytest.raises(ValueError, match='positive integer'):
        NativeCoverageRun(tmp_path / 'run', batch_size=value)
    assert not (tmp_path / 'run').exists()


@pytest.mark.parametrize('body', (
    '', '# wrong\n', '# SystemC::Coverage-3\n',
    "# SystemC::Coverage-3\nC 'point' -1\n",
    "# SystemC::Coverage-3\nC 'point' 9223372036854775808\n",
    "# SystemC::Coverage-3\nnot a coverage record\n",
))
def test_malformed_input_is_not_silently_discarded(tmp_path, body):
    run = NativeCoverageRun(tmp_path / 'run')
    run.owner = 'case'
    source = tmp_path / 'source.dat'
    source.write_text(body)
    with pytest.raises(ValueError, match='native coverage'):
        run.add('bpu', source)
    assert source.read_text() == body and not run.inputs


def test_merge_failure_keeps_last_good_aggregate_and_all_pending_inputs(tmp_path, monkeypatch):
    run = NativeCoverageRun(tmp_path / 'run', batch_size=1)
    run.owner = 'first'
    aggregate = run.add('bpu', data(tmp_path / 'first.dat'))
    run.end_test('first', failed=False)
    before = aggregate.read_bytes()
    run.owner = 'second'
    run.add('bpu', data(tmp_path / 'second.dat', 9))
    spool = Path(run.pending['bpu'][0]['spool_path'])
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(17, args[0])
    monkeypatch.setattr(subprocess, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        run.flush()
    assert aggregate.read_bytes() == before and spool.is_file()
    assert not list(aggregate.parent.glob('.native-merge-*'))
    with pytest.raises(RuntimeError, match='previously failed'):
        run.finish()


def test_input_corruption_is_rejected_before_native_merge(tmp_path):
    run = NativeCoverageRun(tmp_path / 'run')
    run.owner = 'case'
    run.add('bpu', data(tmp_path / 'input.dat'))
    spool = Path(run.pending['bpu'][0]['spool_path'])
    data(spool, 5)
    with pytest.raises(ValueError, match='input changed'):
        run.flush()
    assert spool.is_file() and not run.aggregates['bpu'].exists()


def test_bad_processor_output_does_not_consume_input(tmp_path, monkeypatch):
    run = NativeCoverageRun(tmp_path / 'run')
    run.owner = 'case'
    run.add('bpu', data(tmp_path / 'input.dat'))
    spool = Path(run.pending['bpu'][0]['spool_path'])
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match='header'):
        run.flush()
    assert spool.is_file() and not run.aggregates['bpu'].exists()


def test_context_is_opt_in_and_reset_restores_raw_path(tmp_path):
    raw = data(tmp_path / 'raw.dat')
    assert collect_native_coverage('bpu', raw) == raw and raw.is_file()
    run = NativeCoverageRun(tmp_path / 'run')
    token = set_native_coverage_run(run)
    try:
        run.owner = 'case'
        assert collect_native_coverage('bpu', raw) != raw
    finally:
        reset_native_coverage_run(token)
    assert collect_native_coverage('bpu', raw) == raw
    run.finish()


def test_native_paths_are_isolated_before_dut_construction(tmp_path):
    requested = tmp_path / 'same-name.dat'
    assert native_coverage_path('bpu', requested) == requested
    run = NativeCoverageRun(tmp_path / 'run')
    run.owner = 'case'
    token = set_native_coverage_run(run)
    try:
        first = native_coverage_path('bpu', requested)
        second = native_coverage_path('bpu', requested)
        assert first != second and first.is_relative_to(run.directory) and second.is_relative_to(run.directory)
        assert not requested.exists()
        for path in (first, second):
            run.add('bpu', data(path))
        assert not first.exists() and not second.exists()
        run.end_test('case', failed=False)
        assert run.finish()['input_files'] == 2
    finally:
        reset_native_coverage_run(token)


def test_consumption_error_is_sticky_and_cannot_double_merge(tmp_path, monkeypatch):
    run = NativeCoverageRun(tmp_path / 'run')
    run.owner = 'case'
    aggregate = run.add('bpu', data(tmp_path / 'raw.dat', 3))
    original_unlink = Path.unlink
    def fail_input(path, *args, **kwargs):
        if path.parent.parent.name == 'pending':
            raise OSError('simulated input deletion failure')
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', fail_input)
    with pytest.raises(OSError, match='deletion failure'):
        run.flush()
    before = aggregate.read_bytes()
    with pytest.raises(RuntimeError, match='previously failed'):
        run.finish()
    assert aggregate.read_bytes() == before


def test_reusing_existing_run_directory_is_rejected(tmp_path):
    NativeCoverageRun(tmp_path / 'run')
    with pytest.raises(FileExistsError):
        NativeCoverageRun(tmp_path / 'run')


def test_owner_and_dut_name_are_required(tmp_path):
    run = NativeCoverageRun(tmp_path / 'run')
    source = data(tmp_path / 'input.dat')
    with pytest.raises(RuntimeError, match='active pytest owner'):
        run.add('bpu', source)
    run.owner = 'case'
    with pytest.raises(ValueError, match='DUT name'):
        run.add('../../elsewhere', source)
    run.finish()
    with pytest.raises(RuntimeError, match='already finished'):
        run.add('bpu', source)
