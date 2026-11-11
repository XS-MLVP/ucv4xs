"""Canonical LCOV must match the explicit report, not an old directory glob."""
import json
from pathlib import Path

import pytest

from tools.sync_published_lcov import NAMES
from tools.sync_published_lcov import source_counts
from tools.sync_published_lcov import sync


@pytest.fixture
def native_report(tmp_path):
    results = tmp_path / 'results'
    run = results / 'qualified-run' / 'rtl-lines'
    run.mkdir(parents=True)
    rows = {}
    for name in sorted(NAMES):
        path = run / (name + '.info')
        path.write_text(f'TN:verilator_coverage\nSF:/rtl/{name}.sv\nDA:1,3\nDA:2,0\nend_of_record\n')
        rows[name] = dict(lcov_file=str(path), source_lines=dict(total=2, hit=1))
    report = results / 'rtl-line-coverage.json'
    report.write_text(json.dumps(dict(format='bpu-rtl-line-coverage', version=3,
                                     pytest_exitstatus=0, dut=rows)))
    return tmp_path, report, rows


def test_check_detects_stale_without_writing_and_publish_is_idempotent(native_report):
    root, report, rows = native_report
    canonical = root / 'results/rtl-lines'
    canonical.mkdir()
    (canonical / 'bpu.info').write_text('old snapshot')
    (canonical / 'obsolete.info').write_text('unrelated historical file')
    checked = sync(report, root=root)
    assert set(checked['stale_before']) == NAMES
    assert not checked['synchronized']
    assert (canonical / 'bpu.info').read_text() == 'old snapshot'
    published = sync(report, root=root, publish=True)
    assert published['synchronized'] and not published['new_coverage_claimed']
    for name, row in rows.items():
        assert (canonical / (name + '.info')).read_bytes() == Path(row['lcov_file']).read_bytes()
    assert (canonical / 'obsolete.info').read_text() == 'unrelated historical file'
    assert sync(report, root=root)['stale_before'] == []
    assert sync(report, root=root, publish=True)['stale_before'] == []
    assert not list(canonical.glob('.*'))


@pytest.mark.parametrize('field,value', (
    ('format', 'other'), ('version', 2), ('pytest_exitstatus', 1),
    ('dut', {}), ('dut', {'unexpected': {}})))
def test_incomplete_or_failed_report_never_publishes(native_report, field, value):
    root, report, _ = native_report
    data = json.loads(report.read_text())
    data[field] = value
    report.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        sync(report, root=root, publish=True)
    assert not (root / 'results/rtl-lines').exists()


@pytest.mark.parametrize('corruption', ('counts', 'missing', 'relative', 'outside'))
def test_all_inputs_validated_before_any_replacement(native_report, corruption):
    root, report, rows = native_report
    data = json.loads(report.read_text())
    row = data['dut']['utage']  # Last source, after nine valid sources.
    if corruption == 'counts':
        row['source_lines']['hit'] = 2
    elif corruption == 'missing':
        Path(row['lcov_file']).unlink()
    elif corruption == 'relative':
        row['lcov_file'] = 'relative.info'
    else:
        row['lcov_file'] = str(root / 'outside.info')
    report.write_text(json.dumps(data))
    canonical = root / 'results/rtl-lines'
    canonical.mkdir()
    old = canonical / 'abtb.info'
    old.write_text('preserve existing output')
    with pytest.raises((ValueError, FileNotFoundError)):
        sync(report, root=root, publish=True)
    assert old.read_text() == 'preserve existing output'
    assert list(canonical.iterdir()) == [old]


@pytest.mark.parametrize('bad', (
    b'', b'DA:1,1\n', b'SF:x\nDA:1,1\n',
    b'SF:x\nDA:1,-1\nend_of_record\n',
    b'SF:x\nDA:0,1\nend_of_record\n',
    b'SF:x\nDA:1,1\nDA:1,2\nend_of_record\n',
    b'SF:x\nSF:y\nDA:1,1\nend_of_record\n',
    b'end_of_record\n', b'TN:only-header\n',
    b'SF:x\nDA:1,1\nBRDA:1,0,0,1\nend_of_record\n'))
def test_invalid_native_lcov_rejected(bad):
    with pytest.raises(ValueError):
        source_counts(bad)


@pytest.mark.parametrize('kind', ('directory', 'target', 'source'))
def test_symlink_paths_are_not_replaced_or_followed(native_report, kind):
    root, report, rows = native_report
    canonical = root / 'results/rtl-lines'
    outside = root / 'unrelated'
    outside.mkdir()
    if kind == 'directory':
        canonical.symlink_to(outside, target_is_directory=True)
    elif kind == 'target':
        canonical.mkdir()
        (canonical / 'utage.info').symlink_to(outside / 'original.info')
    else:
        source = Path(rows['utage']['lcov_file'])
        source.unlink()
        source.symlink_to(outside / 'original.info')
    with pytest.raises(ValueError):
        sync(report, root=root, publish=True)
    assert not list(outside.iterdir())


def test_report_change_during_preflight_never_publishes(native_report, monkeypatch):
    root, report, _ = native_report
    read_bytes = Path.read_bytes
    reads = 0
    def changed(path):
        nonlocal reads
        data = read_bytes(path)
        if path == report:
            reads += 1
            if reads > 1:
                return data + b' '
        return data
    monkeypatch.setattr(Path, 'read_bytes', changed)
    with pytest.raises(ValueError, match='changed during preflight'):
        sync(report, root=root, publish=True)
    assert not (root / 'results/rtl-lines').exists()


def test_source_change_during_preflight_never_publishes(native_report, monkeypatch):
    root, report, rows = native_report
    source = Path(rows['abtb']['lcov_file'])
    read_bytes = Path.read_bytes
    reads = 0
    def changed(path):
        nonlocal reads
        data = read_bytes(path)
        if path == source:
            reads += 1
            if reads > 1:
                return data + b'\n'
        return data
    monkeypatch.setattr(Path, 'read_bytes', changed)
    with pytest.raises(ValueError, match='source changed during preflight'):
        sync(report, root=root, publish=True)
    assert not (root / 'results/rtl-lines').exists()


def test_failed_atomic_replace_preserves_target_and_removes_temporary(native_report, monkeypatch):
    root, report, _ = native_report
    canonical = root / 'results/rtl-lines'
    canonical.mkdir()
    target = canonical / 'abtb.info'
    target.write_text('original output')
    def failed(*args, **kwargs):
        raise OSError('injected replace failure')
    monkeypatch.setattr(Path, 'replace', failed)
    with pytest.raises(OSError, match='replace failure'):
        sync(report, root=root, publish=True)
    assert target.read_text() == 'original output'
    assert list(canonical.iterdir()) == [target]
