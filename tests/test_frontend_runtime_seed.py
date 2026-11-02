"""CLI-recorded seeds reach the real FTQ/ICache constructor boundary."""
from types import SimpleNamespace

import pytest

from suites.frontend.ftq import harness as ftq
from suites.frontend.icache.runtime import dut as icache


def loader(monkeypatch, tmp_path, kind):
    class Native:
        def __init__(self, arguments, **options):
            self.arguments = list(arguments)
            self.options = options
            self.dut = SimpleNamespace(WaveformEnable=lambda _: None)
            self.finished = False

        def InitClock(self, name):
            self.clock_name = name

        def Finish(self):
            self.finished = True

    package = tmp_path / 'dut' / 'chosen'
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('# native constructor test boundary\n')
    module = SimpleNamespace(xsp=SimpleNamespace(StringVector=list), DUTFake=Native)
    target = ftq if kind == 'ftq' else icache
    spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _: None))
    monkeypatch.setattr(target.importlib.util, 'spec_from_file_location', lambda *_, **__: spec)
    monkeypatch.setattr(target.importlib.util, 'module_from_spec', lambda _: module)
    if kind == 'ftq':
        monkeypatch.setattr(ftq, 'DUT_ROOT', tmp_path / 'dut')

        def create():
            owner = ftq.Dut('chosen', None)
            return owner.dut, owner._finish

        return create
    monkeypatch.setattr(icache, 'ROOT', tmp_path)
    monkeypatch.setattr(icache, 'validate_dut_runtime', lambda _: None)
    monkeypatch.setattr(icache, 'require_memory_direct', lambda _: SimpleNamespace(_metadata={'bound': 1}, close=lambda: None))
    monkeypatch.setattr(icache, 'initialize_dut_inputs', lambda _: None)
    monkeypatch.setattr(icache, 'output_directory', lambda *_: tmp_path / 'outputs')
    factory = icache.DutFactory(managed_coverage=True)
    return lambda: (factory.create('chosen'), factory.close)


@pytest.mark.parametrize('kind', ('ftq', 'icache'))
@pytest.mark.parametrize('configured,expected', ((None, 1), ('7', 7)))
def test_native_frontend_arguments_use_the_recorded_seed(monkeypatch, tmp_path, kind, configured, expected):
    create = loader(monkeypatch, tmp_path, kind)
    if configured is None:
        monkeypatch.delenv('UCV_SEED', raising=False)
    else:
        monkeypatch.setenv('UCV_SEED', configured)
    native, close = create()
    assert native.arguments == ['chosen', f'+verilator+seed+{expected}']
    close()
    assert native.finished


@pytest.mark.parametrize('kind', ('ftq', 'icache'))
def test_frontend_seed_is_resolved_for_each_native_construction(monkeypatch, tmp_path, kind):
    create = loader(monkeypatch, tmp_path, kind)
    for value in ('3', '11'):
        monkeypatch.setenv('UCV_SEED', value)
        native, close = create()
        assert native.arguments == ['chosen', f'+verilator+seed+{value}']
        close()
