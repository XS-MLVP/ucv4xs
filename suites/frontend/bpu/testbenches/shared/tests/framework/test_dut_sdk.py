"""SDK normalization preserves old artifacts and fails before destructive work."""
from pathlib import Path

import pytest
from tools import dut_sdk


@pytest.fixture
def sdk(tmp_path, monkeypatch):
    directory = tmp_path / 'dut/xspcomm'
    directory.mkdir(parents=True)
    for name in ('__init__.py', 'pyxspcomm.py', dut_sdk.LIBRARY, dut_sdk.EXTENSION):
        (directory / name).write_bytes(name.encode())
    for name in ('libxspcomm.so.0.1.0', '_pyxspcomm.so.0.1.0'):
        (directory / name).write_bytes(b'old contents')
    (directory / 'libxspcomm.so').symlink_to('libxspcomm.so.0.1.0')
    (directory / 'libxspcomm.so.3').write_bytes(b'duplicate alias')
    (directory / '_pyxspcomm.so').symlink_to('_pyxspcomm.so.0.1.0')
    monkeypatch.setattr(dut_sdk, '_elf', lambda p:
        'Library soname: [libxspcomm.so.3]' if p.name == dut_sdk.LIBRARY
        else 'Shared library: [libxspcomm.so.3]')
    return directory


def test_one_version_with_recoverable_old_links_and_libraries(sdk, tmp_path):
    before = dut_sdk.inspect_sdk(sdk)
    backup = tmp_path / 'backup'
    receipt = dut_sdk.normalize_sdk(sdk, backup)
    assert dut_sdk.validate_sdk(sdk) == before == receipt['canonical_sha256']
    assert (backup / 'libxspcomm.so').readlink() == Path('libxspcomm.so.0.1.0')
    assert (backup / 'libxspcomm.so.0.1.0').read_bytes() == b'old contents'
    assert (backup / 'libxspcomm.so.3').read_bytes() == b'duplicate alias'
    assert (sdk / 'libxspcomm.so').resolve() == sdk / dut_sdk.LIBRARY
    assert dut_sdk.normalize_sdk(sdk, tmp_path / 'second')['moved'] == []


@pytest.mark.parametrize('fault', ('missing', 'wrong_abi', 'nested', 'backup_exists', 'backup_inside'))
def test_invalid_package_or_backup_changes_nothing(sdk, tmp_path, monkeypatch, fault):
    backup = tmp_path / 'backup'
    if fault == 'missing': (sdk / dut_sdk.LIBRARY).unlink()
    elif fault == 'wrong_abi': monkeypatch.setattr(dut_sdk, '_elf', lambda p: 'libxspcomm.so.1')
    elif fault == 'nested': (sdk / 'xspcomm').mkdir()
    elif fault == 'backup_exists': backup.mkdir()
    elif fault == 'backup_inside': backup = sdk / 'backup'
    before = sorted(p.name for p in sdk.iterdir())
    with pytest.raises(ValueError):
        dut_sdk.normalize_sdk(sdk, backup)
    assert sorted(p.name for p in sdk.iterdir()) == before
    assert (sdk / 'libxspcomm.so').readlink() == Path('libxspcomm.so.0.1.0')


def test_incomplete_cleanup_rolls_back(sdk, tmp_path, monkeypatch):
    def reject(_):
        raise ValueError('injected postcondition failure')
    monkeypatch.setattr(dut_sdk, 'validate_sdk', reject)
    with pytest.raises(ValueError, match='postcondition'):
        dut_sdk.normalize_sdk(sdk, tmp_path / 'backup')
    assert (sdk / 'libxspcomm.so').readlink() == Path('libxspcomm.so.0.1.0')
    assert (sdk / 'libxspcomm.so.3').read_bytes() == b'duplicate alias'
    assert (sdk / 'libxspcomm.so.0.1.0').read_bytes() == b'old contents'


def test_mixed_versions_are_rejected(sdk):
    with pytest.raises(ValueError, match='mixed/incomplete'):
        dut_sdk.validate_sdk(sdk)
