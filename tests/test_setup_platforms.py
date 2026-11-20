"""Native setup must select and validate a binary for the actual host."""
import io
import struct
import tarfile
from types import SimpleNamespace

import pytest

from ucv import host
from ucv.common import UcvError, file_hash, write
from ucv.setup import install_generation_tools
import ucv.setup as installation


def test_macos_generation_downloads_and_validates_macho(tmp_path, monkeypatch):
    monkeypatch.setattr(host, 'system', lambda: 'Darwin')
    monkeypatch.setattr(host, 'machine', lambda: 'aarch64')
    project = SimpleNamespace(root=tmp_path, local={})
    downloads = []
    binary = b'\xcf\xfa\xed\xfe' + struct.pack('<I', 0x0100000C) + bytes(24)

    def download(url, destination):
        downloads.append(url)
        if url == host.MILL_LAUNCHER:
            destination.write_text('#!/bin/sh\n')
        else:
            with tarfile.open(destination, 'w:gz') as archive:
                member = tarfile.TarInfo('firtool/bin/firtool')
                member.size = len(binary)
                archive.addfile(member, io.BytesIO(binary))

    monkeypatch.setattr('ucv.setup.urllib.request.urlretrieve', download)
    install_generation_tools(project)
    assert downloads == [host.MILL_LAUNCHER, host.firtool_url()]
    installed = tmp_path/'.tools/bin/firtool'
    assert installed.read_bytes() == binary
    assert installed.stat().st_mode & 0o111 == 0o111


def test_macos_rejects_linux_firtool_seed_before_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(host, 'system', lambda: 'Darwin')
    monkeypatch.setattr(host, 'machine', lambda: 'aarch64')
    tools = tmp_path/'.tools/bin'
    tools.mkdir(parents=True)
    (tools/'mill').write_text('#!/bin/sh\n')
    seed = tmp_path/'linux-firtool'
    binary = bytearray(64)
    binary[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<H', binary, 18, 0xB7)
    seed.write_bytes(binary)
    project = SimpleNamespace(root=tmp_path, local={'firtool': str(seed)})
    with pytest.raises(UcvError, match='not Mach-O'):
        install_generation_tools(project)
    assert not (tools/'firtool').exists()


@pytest.fixture
def prior_install(tmp_path, monkeypatch):
    monkeypatch.setattr(host, 'system', lambda: 'Darwin')
    monkeypatch.setattr(host, 'machine', lambda: 'aarch64')
    tools = tmp_path/'.tools/verilator/bin'
    tools.mkdir(parents=True)
    binary = tools/'verilator_bin'
    binary.write_bytes(b'\xcf\xfa\xed\xfe' + struct.pack('<I', 0x0100000C) + bytes(24))
    (tools/'verilator').write_text('#!/bin/sh\n')
    python = tmp_path/'.venv/bin/python'
    python.parent.mkdir(parents=True)
    python.touch()
    pin = {'commit': 'a'*40}
    receipt = {'tools': {'verilator': pin}, 'system': 'Darwin', 'machine': 'aarch64',
               'binaries': {'verilator/bin/verilator_bin': file_hash(binary)}}
    project = SimpleNamespace(root=tmp_path, tools={'verilator': pin}, local={},
                              environment=lambda: {'PATH': '/host/bin'})
    # Build tools for xcomm/Picker exist, but Verilator source prerequisites do not.
    monkeypatch.setattr(installation.shutil, 'which', lambda name, **kwargs:
                        '/host/bin/'+name if name in {'git', 'cmake', 'make', 'c++', 'swig'} else None)
    return project, receipt, binary


@pytest.mark.parametrize('stale', ['no_receipt', 'lock', 'machine', 'system', 'binary'])
def test_stale_verilator_install_requires_source_prerequisites_before_pip(prior_install, stale, monkeypatch):
    project, receipt, binary = prior_install
    if stale == 'lock':receipt['tools'] = {'verilator': {'commit': 'b'*40}}
    if stale == 'machine':receipt['machine'] = 'x86_64'
    if stale == 'system':receipt['system'] = 'Linux'
    if stale != 'no_receipt':write(project.root/'.tools/receipt.json', receipt)
    if stale == 'binary':binary.write_bytes(binary.read_bytes()+b'changed')
    monkeypatch.setattr(installation, 'execute', lambda *args, **kwargs:
                        pytest.fail('must check source prerequisites before installing packages'))
    with pytest.raises(UcvError, match='Missing host build tools: autoconf, flex, bison, help2man'):
        installation.setup(project)


def test_verified_verilator_install_does_not_require_source_build_tools(prior_install, monkeypatch):
    project, receipt, _ = prior_install
    write(project.root/'.tools/receipt.json', receipt)
    calls = []

    def stop_at_pip(command, **kwargs):
        calls.append(command)
        raise RuntimeError('reached package installation')

    monkeypatch.setattr(installation, 'execute', stop_at_pip)
    with pytest.raises(RuntimeError, match='reached package installation'):
        installation.setup(project)
    assert calls[0][1:4] == ['-m', 'pip', 'install']


@pytest.mark.parametrize('failed_tool', ['mill', 'firtool'])
def test_interrupted_generation_download_can_be_retried(tmp_path, monkeypatch, failed_tool):
    monkeypatch.setattr(host, 'system', lambda: 'Darwin')
    monkeypatch.setattr(host, 'machine', lambda: 'aarch64')
    project = SimpleNamespace(root=tmp_path, local={})
    interrupted = True
    binary = b'\xcf\xfa\xed\xfe' + struct.pack('<I', 0x0100000C) + bytes(24)

    def download(url, destination):
        tool = 'mill' if url == host.MILL_LAUNCHER else 'firtool'
        if interrupted and tool == failed_tool:
            destination.write_bytes(b'partial download')
            raise OSError('download interrupted')
        if tool == 'mill':
            destination.write_text('#!/bin/sh\n')
        else:
            with tarfile.open(destination, 'w:gz') as archive:
                member = tarfile.TarInfo('firtool/bin/firtool')
                member.size = len(binary)
                archive.addfile(member, io.BytesIO(binary))

    monkeypatch.setattr(installation.urllib.request, 'urlretrieve', download)
    with pytest.raises(OSError, match='download interrupted'):
        install_generation_tools(project)
    assert not (tmp_path/'.tools/bin'/failed_tool).exists()
    assert not list((tmp_path/'.tools/bin').glob('generation-*'))
    interrupted = False
    install_generation_tools(project)
    assert (tmp_path/'.tools/bin/firtool').read_bytes() == binary
    assert (tmp_path/'.tools/bin/mill').stat().st_mode & 0o111 == 0o111


def test_foreign_firtool_download_is_not_published(tmp_path, monkeypatch):
    monkeypatch.setattr(host, 'system', lambda: 'Darwin')
    monkeypatch.setattr(host, 'machine', lambda: 'aarch64')
    tools = tmp_path/'.tools/bin'
    tools.mkdir(parents=True)
    (tools/'mill').write_text('#!/bin/sh\n')

    def download(url, destination):
        binary = bytearray(64)
        binary[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', binary, 18, 0xB7)
        with tarfile.open(destination, 'w:gz') as archive:
            member = tarfile.TarInfo('firtool/bin/firtool')
            member.size = len(binary)
            archive.addfile(member, io.BytesIO(binary))

    monkeypatch.setattr(installation.urllib.request, 'urlretrieve', download)
    with pytest.raises(UcvError, match='not Mach-O'):
        install_generation_tools(SimpleNamespace(root=tmp_path, local={}))
    assert not (tools/'firtool').exists()
