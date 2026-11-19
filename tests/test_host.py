"""Host architecture identity and architecture-specific tool acquisition."""
import struct

import pytest

from ucv import host
from ucv.common import UcvError


@pytest.mark.parametrize('reported,expected', [
    ('x86_64', 'x86_64'), ('amd64', 'x86_64'), ('AMD64', 'x86_64'),
    ('aarch64', 'aarch64'), ('arm64', 'aarch64'), ('AARCH64', 'aarch64'),
])
def test_machine_names_are_canonicalised(monkeypatch, reported, expected):
    monkeypatch.setattr(host.platform, 'machine', lambda: reported)
    assert host.machine() == expected


@pytest.mark.parametrize('system,machine_name,accepted', [
    ('Linux', 'x86_64', True),
    ('Linux', 'aarch64', True),
    ('Linux', 'arm64', True),
    ('Linux', 'riscv64', False),
    ('Darwin', 'aarch64', False),
    ('Darwin', 'x86_64', False),
    ('Windows', 'x86_64', False),
])
def test_supported_hosts(system, machine_name, accepted):
    assert host.supported(machine_name, system) is accepted


def test_require_names_the_host_and_the_requirement():
    with pytest.raises(UcvError, match=r'Linux x86_64 or aarch64'):
        host.require('riscv64', 'Linux')
    with pytest.raises(UcvError, match=r'Darwin riscv64|Linux riscv64'):
        host.require('riscv64', 'Linux')
    host.require('aarch64', 'Linux')


def _elf(path, machine_code, *, elf_class=2, data=1):
    header = bytearray(64)
    header[0:4] = b'\x7fELF'
    header[4] = elf_class
    header[5] = data
    struct.pack_into('<H' if data == 1 else '>H', header, 18, machine_code)
    path.write_bytes(bytes(header))
    return path


@pytest.mark.parametrize('code,expected', [(0x3E, 'x86_64'), (0xB7, 'aarch64'),
                                           (0x28, 'arm'), (0xF3, 'riscv')])
def test_elf_machine_is_read_from_the_header(tmp_path, code, expected):
    assert host.elf_machine(_elf(tmp_path / 'binary', code)) == expected


def test_non_elf_and_missing_files_report_no_machine(tmp_path):
    text = tmp_path / 'script'
    text.write_text('#!/bin/sh\n')
    assert host.elf_machine(text) is None
    assert host.elf_machine(tmp_path / 'absent') is None


def test_foreign_seed_binary_is_rejected_before_use(tmp_path):
    aarch64 = _elf(tmp_path / 'verilator_bin', 0xB7)
    with pytest.raises(UcvError, match=r'built for aarch64, but this host is x86_64'):
        host.require_elf_machine(aarch64)
    assert host.require_elf_machine(aarch64, 'aarch64') == 'aarch64'


def test_a_seed_that_is_not_elf_is_rejected(tmp_path):
    script = tmp_path / 'verilator_bin'
    script.write_text('#!/bin/sh\n')
    with pytest.raises(UcvError, match='not ELF'):
        host.require_elf_machine(script)


def test_firtool_is_published_for_x86_64_only():
    """CIRCT ships no linux-arm64 build, so aarch64 must not appear to have one."""
    assert host.firtool_url('x86_64').endswith('firrtl-bin-linux-x64.tar.gz')
    assert host.firtool_url('aarch64') is None
    assert host.rtl_generation_available('x86_64') is True
    assert host.rtl_generation_available('aarch64') is False


@pytest.mark.parametrize('alias', ['amd64', 'AMD64', 'x64'])
def test_aliases_resolve_identically_in_every_entry_point(alias):
    """A caller passing platform.machine() directly must get the same answer."""
    assert host.canonical(alias) == 'x86_64'
    assert host.supported(alias, 'Linux') is True
    assert host.rtl_generation_available(alias) is True
    assert host.firtool_url(alias) == host.firtool_url('x86_64')


@pytest.mark.parametrize('alias', ['arm64', 'aarch64'])
def test_arm_aliases_agree_across_entry_points(alias):
    assert host.canonical(alias) == 'aarch64'
    assert host.supported(alias, 'Linux') is True
    assert host.rtl_generation_available(alias) is False


def test_rejection_names_the_canonical_architecture(monkeypatch):
    """An alias in the message must not look like a different architecture."""
    with pytest.raises(UcvError, match=r'Linux riscv64'):
        host.require('RISCV64', 'Linux')


def test_mill_launcher_is_the_architecture_neutral_script():
    """The jar is not executable; only the shell launcher selects a native build."""
    assert host.MILL_LAUNCHER.endswith('-mill.sh')
    assert ':jar' not in host.MILL_LAUNCHER
    assert host.MILL_DISTRIBUTION in host.MILL_LAUNCHER
