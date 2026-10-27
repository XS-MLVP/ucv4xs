import ucv.runtime as ucv_paths
"""Picker resource boundary shared by the clocked Manager and combinational AddrGen.

No clock stepping, dynamic source adaptation, reference state or coverage collector.
"""
from contextlib import contextmanager
from hashlib import sha256
import importlib
import json
from pathlib import Path

from .runtime import ROOT, validate_binding, validate_runtime


def verify_rtl():
    from ucv.common import read, file_hash
    from ucv.config import Project
    project=Project(); suite=project.suite('vagq')
    for key in suite.recipe['duts']:
        receipt=read(ROOT/'rtl'/key/'source.json')
        if receipt['baseline'] != suite.baseline:
            raise RuntimeError('VAGQ RTL baseline differs from effective baseline')
        for name, expected in receipt['files'].items():
            if file_hash(ROOT/'rtl'/key/name) != expected:
                raise RuntimeError(f'VAGQ RTL changed: {key}/{name}')


def public_signals(dut, module, widths):
    """New native read handles for this instance's exact public port layout."""
    cfg = dut.xcfg
    if int(cfg.cfg_base_address) != int(dut.dut.GetXSignalCFGBasePtr()):
        raise RuntimeError('signal configuration belongs to a different DUT instance')
    signals = {}
    for name, width in widths.items():
        signal = cfg.NewXData(f'{module}Dut_top.{name}', f'committed:{name}')
        if signal is None or signal.IsVPIBinded() or signal.W() != (0 if width == 1 else width):
            raise RuntimeError(f'no matching mem_direct public signal: {name}/{width}')
        signals[name] = signal
    return signals


@contextmanager
def open_dut(module, output, *, clocked=False, register=None):
    """Construct/reset-initialize one actual generated DUT and always Finish it."""
    validate_runtime()
    verify_rtl()
    binding = importlib.import_module('dut.' + module)
    validate_binding(binding.xsp)
    cls = getattr(binding, 'DUT' + module + 'Dut')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    waveform = output / (module + '.fst')
    args = binding.xsp.StringVector([module, ucv_paths.native_seed()])
    dut = cls(args, waveform_filename=str(waveform),
              coverage_filename=str(output / (module + '-coverage.dat')))
    try:
        layout = Path(dut.dut.GetXSignalCFGPath())
        if int(dut.dut.GetXSignalCFGBasePtr()) <= 0 or not layout.is_file():
            raise RuntimeError('picker mem_direct base/layout unavailable')
        if layout.stat().st_size == 0 or not dut.xcfg.GetSignalNames():
            raise RuntimeError('picker mem_direct layout is empty')
        # Picker metadata identifies actual leaves; XPorts are never mistaken
        # for inputs. Only initial reset is written immediately here. Later
        # write-mode and transaction timing belong to the module's driver.
        schema_path = Path(binding.__file__).with_name('signals.json')

        def initialize(node, prefix=''):
            for name, leaf in node.items():
                if name == '_':
                    continue
                path = prefix + name
                if leaf.get('_') is True:
                    if leaf['Pin'] == 'input':
                        pin = getattr(dut, path)
                        pin.AsImmWrite()
                        pin.Set(int(clocked and path == 'reset'))
                else:
                    initialize(leaf, path + '_')

        initialize(json.loads(schema_path.read_text()))
        if clocked:
            dut.InitClock('clock')
        if register is not None:
            register(dut)
        yield dut
    finally:
        dut.Finish()
    if not waveform.is_file() or waveform.stat().st_size == 0:
        raise AssertionError(f'missing/empty requested waveform: {waveform}')
