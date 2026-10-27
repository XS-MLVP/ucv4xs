"""Native bindings are explicit, bounded and never use picker getter fallbacks."""
from __future__ import annotations

import ctypes
from types import SimpleNamespace

import pytest

import xspcomm as xsp
from bpuverify.common.env.memory_direct import MemoryDirectSignals
from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import require_memory_direct


def native_dut(tmp_path, *, width=1, stride=1, size=0):
    storage = (ctypes.c_ubyte * 96)(*([0xA5] * 96))
    for position in range(16, 16 + stride * max(1, size)):
        storage[position] = 0
    layout = tmp_path / 'offset.yaml'
    kind = 'CData' if stride == 1 else 'SData' if stride == 2 else 'IData' if stride == 4 else 'QData' if stride == 8 else 'VlWide'
    layout.write_text('variables:\n  - name: model.field\n'
        f'    type: {kind}\n    mem_bytes: {stride}\n    rtl_width: {width}\n'
        f'    offset: 16\n' + (f'    array_size: {size}\n' if size else ''), encoding='utf-8')
    base = ctypes.addressof(storage)
    def forbidden(*args, **kwargs):
        raise AssertionError('legacy picker getters must never be used')
    dut = SimpleNamespace(
        dut=SimpleNamespace(GetXSignalCFGBasePtr=lambda: base, GetXSignalCFGPath=lambda: str(layout)),
        xcfg=xsp.XSignalCFG(str(layout), base),
        internal_signals={'model.field': object()},
        GetInternalSignal=forbidden, GetInternalSignalList=forbidden,
        storage=storage,
    )
    return dut


@pytest.mark.parametrize('width,stride', [(1,1),(2,1),(8,1),(9,2),(16,2),(17,4),
    (32,4),(33,8),(64,8),(65,12),(128,16)])
def test_native_scalar_read_write_does_not_touch_neighbors(tmp_path, width, stride):
    dut = native_dut(tmp_path, width=width, stride=stride)
    view = require_memory_direct(dut)
    assert view.names() == ('TOP.model.field',)
    field = memory_signal(dut, 'TOP.model.field')
    assert field is memory_signal(dut, 'model.field')
    assert field is not dut.internal_signals['model.field']
    assert not field.IsVPIBinded()
    field.AsImmWrite()
    value = (1 << width) - 1
    field.Set(value)
    assert field.U() == value
    assert bytes(dut.storage[:16]) == bytes([0xA5] * 16)
    assert bytes(dut.storage[16 + stride:]) == bytes([0xA5] * (80 - stride))
    # Mutate the actual backing memory, not the XData cache.
    for position in range(16, 16 + stride):
        dut.storage[position] = 0
    assert field.U() == 0


def test_native_array_indices_have_separate_handles_and_storage(tmp_path):
    dut = native_dut(tmp_path, width=3, stride=1, size=3)
    view = require_memory_direct(dut)
    for position in range(3):
        field = view.signal('model.field', position)
        field.AsImmWrite()
        field.Set(position + 1)
    assert bytes(dut.storage[16:19]) == bytes([1,2,3])
    assert bytes(dut.storage[:16]) == bytes([0xA5] * 16)
    assert bytes(dut.storage[19:]) == bytes([0xA5] * 77)
    assert view.signal('model.field', 0) is not view.signal('model.field', 1)
    with pytest.raises(ValueError, match='explicit element index'):
        view.signal('model.field')
    for position in (-1, 3):
        with pytest.raises(IndexError, match='out of bounds'):
            view.signal('model.field', position)


def test_same_layout_different_model_bases_never_share_handles(tmp_path):
    first = native_dut(tmp_path, width=8, stride=1)
    second = SimpleNamespace(
        storage=(ctypes.c_ubyte * 96)(), internal_signals={},
    )
    base = ctypes.addressof(second.storage)
    layout = str(tmp_path / 'offset.yaml')
    second.dut = SimpleNamespace(GetXSignalCFGBasePtr=lambda: base, GetXSignalCFGPath=lambda: layout)
    second.xcfg = xsp.XSignalCFG(layout, base)
    left, right = memory_signal(first, 'model.field'), memory_signal(second, 'model.field')
    assert left is not right
    first.storage[16], second.storage[16] = 3, 7
    assert (left.U(), right.U()) == (3, 7)
    right.AsImmWrite()
    right.Set(5)
    assert (left.U(), right.U()) == (3, 5)
    require_memory_direct(first).close()
    assert right.U() == 5


def test_rtl_discovery_does_not_confuse_delayed_temporary_with_real_field(tmp_path):
    dut = native_dut(tmp_path, width=8, stride=1)
    layout = tmp_path / 'offset.yaml'
    layout.write_text(layout.read_text() +
        '  - name: __Vdly__model.field\n    mem_bytes: 1\n    rtl_width: 8\n    offset: 17\n'
        'signals:\n  - name: model.field\n    kind: direct\n    source: model.field\n'
        '    mem_bytes: 1\n    rtl_width: 8\n    offset: 16\n', encoding='utf-8')
    view = require_memory_direct(dut)
    assert '__Vdly__model.field' in tuple(view.cfg.GetSignalNames())
    assert view.names() == ('TOP.model.field',)
    dut.storage[16] = 7
    assert view.signal('model.field').U() == 7


@pytest.mark.parametrize('case,message', [
    ('no_native','no native-memory interface'), ('zero_base','base is zero'),
    ('no_layout','layout missing'), ('wrong_base','another model base'),
    ('wrong_layout','does not match'), ('empty_names','contains no signals'),
])
def test_invalid_native_capability_fails_without_fallback(tmp_path, case, message):
    dut = native_dut(tmp_path)
    if case == 'no_native':
        dut.dut = SimpleNamespace()
    elif case == 'zero_base':
        dut.dut.GetXSignalCFGBasePtr = lambda: 0
    elif case == 'no_layout':
        dut.dut.GetXSignalCFGPath = lambda: str(tmp_path / 'missing.yaml')
    elif case == 'wrong_base':
        dut.xcfg.cfg_base_address += 1
    elif case == 'wrong_layout':
        dut.xcfg.cfg_data = str(tmp_path / 'other.yaml')
    else:
        dut.xcfg = SimpleNamespace(cfg_base_address=ctypes.addressof(dut.storage),
            cfg_data=str(tmp_path / 'offset.yaml'), GetSignalNames=lambda: ())
    with pytest.raises(RuntimeError, match=message):
        MemoryDirectSignals(dut)


def test_unknown_derived_unsafe_and_closed_bindings_fail(tmp_path):
    dut = native_dut(tmp_path)
    view = require_memory_direct(dut)
    with pytest.raises(RuntimeError, match='unavailable: model.missing'):
        view.signal('model.missing')
    view.cfg = SimpleNamespace(At=lambda name: SimpleNamespace(is_empty=True),
        NewXData=lambda *args: SimpleNamespace(IsVPIBinded=lambda: False, IsOutIO=lambda: False))
    with pytest.raises(RuntimeError, match='must be read-only'):
        view.signal('model.field')
    view.cfg = SimpleNamespace(At=lambda name: SimpleNamespace(is_empty=False, rtl_width=8, mem_bytes=4))
    with pytest.raises(RuntimeError, match='unsafe native-memory layout'):
        view.signal('model.field')
    view.close()
    for operation in (view.names, lambda: view.signal('model.field'), lambda: require_memory_direct(dut)):
        with pytest.raises(RuntimeError, match='closed DUT'):
            operation()


@pytest.mark.parametrize('kind,expected', [('direct',13), ('projection',1), ('expr',14), ('const',3)])
def test_trace_reconstructed_read_views_use_native_cfg_without_vpi(tmp_path, kind, expected):
    dut = native_dut(tmp_path, width=8, stride=1)
    layout = tmp_path / 'offset.yaml'
    common = 'signals:\n  - name: model.alias\n    kind: ' + kind + '\n    rtl_width: 8\n'
    if kind == 'direct':
        extra = '    source: model.field\n    offset: 16\n    mem_bytes: 1\n'
    elif kind == 'projection':
        extra = '    source: model.field\n    expr: "model.field & 3U"\n'
    elif kind == 'expr':
        extra = '    deps:\n      - name: model.field\n    expr: "model.field + 1U"\n'
    else:
        extra = '    value: "3U"\n'
    layout.write_text(layout.read_text() + common + extra, encoding='utf-8')
    dut.storage[16] = 13
    view = require_memory_direct(dut)
    alias = view.signal('model.alias')
    assert alias.U() == expected and not alias.IsVPIBinded()
    if kind != 'direct':
        assert alias.IsOutIO()
    dut.storage[16] = 6
    assert alias.U() == dict(direct=6, projection=2, expr=7, const=3)[kind]
    assert bytes(dut.storage[:16]) == bytes([0xA5] * 16)


@pytest.mark.dut('uras')
def test_actual_picker_dut_has_native_clock_reset_and_committed_state(dut_factory):
    dut = dut_factory.create('uras', coverage_name='memory-direct-capability-smoke.dat')
    view = require_memory_direct(dut)
    assert view.base > 0
    reset = memory_signal(dut, 'UrasDut_top.reset')
    assert reset.U() == 1 and not reset.IsVPIBinded()
    dut.Step(2)
    dut.reset.Set(0)
    dut.Step(4)
    assert reset.U() == 0
    assert not dut.internal_signals
    dut_factory.close()
    with pytest.raises(RuntimeError, match='closed DUT'):
        view.names()


@pytest.mark.dut('uras')
def test_trace_reset_alias_reads_committed_memory_not_pending_rise_write(dut_factory):
    dut = dut_factory.create('uras', coverage_name='memory-direct-committed-reset-smoke.dat')
    view = require_memory_direct(dut)
    name = 'UrasDut_top.MicroRas.reset'
    assert view._metadata[name]['source'] == 'UrasDut_top.reset'
    committed = memory_signal(dut, name)
    dut.Step(2)
    dut.reset.Set(0)
    assert dut.reset.U() == 0  # Pending input value, not the RTL memory yet.
    assert committed.U() == 1
    dut.Step(1)
    assert committed.U() == 0
    assert not dut.internal_signals
