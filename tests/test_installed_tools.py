"""Installed tools must belong to this host's architecture."""
import json

import pytest

from ucv import host, validation
from ucv.common import UcvError, file_hash, write


@pytest.fixture
def installed(tmp_path, monkeypatch):
    """A receipt plus the two binaries ``installed_tools`` hashes."""
    monkeypatch.setattr(host, 'system', lambda: 'Linux')
    tools = {'toffee': {'commit': '1' * 40}, 'xcomm': {'commit': '2' * 40}}
    prefix = tmp_path / '.tools'
    (prefix / 'bin').mkdir(parents=True)
    (prefix / 'verilator/bin').mkdir(parents=True)
    picker = prefix / 'bin/picker'
    verilator = prefix / 'verilator/bin/verilator_bin'
    picker.write_bytes(b'picker')
    verilator.write_bytes(b'verilator')

    def receipt(machine='x86_64'):
        return {
            'tools': tools,
            'profile': 'runtime',
            'machine': machine,
            'system': 'Linux',
            'binaries': {'bin/picker': file_hash(picker),
                         'verilator/bin/verilator_bin': file_hash(verilator)},
        }

    from types import SimpleNamespace
    project = SimpleNamespace(root=tmp_path, tools=tools,
                              environment=staticmethod(lambda: {}))
    assert project.root == tmp_path

    def save(data):
        write(prefix / 'receipt.json', data)

    save(receipt())
    return project, save, receipt


def test_matching_architecture_is_accepted(installed, monkeypatch):
    project, save, receipt = installed
    monkeypatch.setattr(host, 'machine', lambda: 'x86_64')
    assert validation.installed_tools(project, runtime=False)['machine'] == 'x86_64'


def test_aarch64_tools_are_rejected_on_an_x86_host(installed, monkeypatch):
    project, save, receipt = installed
    save(receipt('aarch64'))
    monkeypatch.setattr(host, 'machine', lambda: 'x86_64')
    with pytest.raises(UcvError, match='built for aarch64 but this host is x86_64'):
        validation.installed_tools(project, runtime=False)


def test_aarch64_host_accepts_aarch64_tools(installed, monkeypatch):
    project, save, receipt = installed
    save(receipt('aarch64'))
    monkeypatch.setattr(host, 'machine', lambda: 'aarch64')
    assert validation.installed_tools(project, runtime=False)['machine'] == 'aarch64'


def test_receipt_without_architecture_is_rejected_explicitly(installed, monkeypatch):
    project, save, receipt = installed
    data = receipt()
    del data['machine']
    save(data)
    monkeypatch.setattr(host, 'machine', lambda: 'aarch64')
    with pytest.raises(UcvError, match='does not record the host architecture'):
        validation.installed_tools(project, runtime=False)


def test_missing_receipt_still_reports_installation_first(tmp_path):
    class Project:
        root = tmp_path
        tools = {}
    with pytest.raises(UcvError, match='not installed'):
        validation.installed_tools(Project, runtime=False)


def test_same_architecture_on_another_os_is_rejected(installed, monkeypatch):
    project, save, receipt = installed
    monkeypatch.setattr(host, 'machine', lambda: 'aarch64')
    monkeypatch.setattr(host, 'system', lambda: 'Darwin')
    save(receipt('aarch64'))
    with pytest.raises(UcvError, match='built for Linux but this host is Darwin'):
        validation.installed_tools(project, runtime=False)
    data = receipt('aarch64')
    data['system'] = 'Darwin'
    save(data)
    assert validation.installed_tools(project, runtime=False)['system'] == 'Darwin'
