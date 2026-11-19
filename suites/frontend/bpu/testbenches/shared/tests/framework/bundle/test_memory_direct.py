"""Native bindings are explicit, bounded and never use picker getter fallbacks."""
from __future__ import annotations

import ctypes
from types import SimpleNamespace

import pytest

import xspcomm as xsp
from ucv import xscfg
from suites.frontend.bpu.testbenches.shared.env.memory_direct import MemoryDirectSignals
from suites.frontend.bpu.testbenches.shared.env.memory_direct import memory_signal
from suites.frontend.bpu.testbenches.shared.env.memory_direct import require_memory_direct


def native_dut(tmp_path, *, width=1, stride=1, size=0):
    storage = (ctypes.c_ubyte * 96)(*([0xA5] * 96))
    for position in range(16, 16 + stride * max(1, size)):
        storage[position] = 0
    layout = tmp_path / 'offset.xscfg'
    kind = 'CData' if stride == 1 else 'SData' if stride == 2 else 'IData' if stride == 4 else 'QData' if stride == 8 else 'VlWide'
    variable = {'type': kind, 'mem_bytes': stride, 'rtl_width': width, 'offset': 16}
    if size:
        variable.update(array_size=size, array_dimensions=[size], array_strides=[stride])
    sections = {'variables': {'model.field': variable}}
    xscfg.write_database(layout, sections)
    base = ctypes.addressof(storage)
    def forbidden(*args, **kwargs):
        raise AssertionError('legacy picker getters must never be used')
    dut = SimpleNamespace(
        dut=SimpleNamespace(GetXSignalCFGBasePtr=lambda: base, GetXSignalCFGPath=lambda: str(layout)),
        xcfg=xsp.XSignalCFG(str(layout), base),
        internal_signals={'model.field': object()},
        GetInternalSignal=forbidden, GetInternalSignalList=forbidden,
        storage=storage, layout=layout, sections=sections,
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
    layout = str(first.layout)
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
    dut.sections['variables']['__Vdly__model.field'] = {
        'mem_bytes': 1, 'rtl_width': 8, 'offset': 17}
    dut.sections['signals'] = {'model.field': {
        'kind': 'direct', 'source': 'model.field',
        'mem_bytes': 1, 'rtl_width': 8, 'offset': 16}}
    xscfg.write_database(dut.layout, dut.sections)
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
        dut.dut.GetXSignalCFGPath = lambda: str(tmp_path / 'missing.xscfg')
    elif case == 'wrong_base':
        dut.xcfg.cfg_base_address += 1
    elif case == 'wrong_layout':
        dut.xcfg.cfg_data = str(tmp_path / 'other.xscfg')
    else:
        dut.xcfg = SimpleNamespace(cfg_base_address=ctypes.addressof(dut.storage),
            cfg_data=str(dut.layout), GetSignalNames=lambda: ())
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
    record = {'kind': kind, 'rtl_width': 8}
    if kind == 'direct':
        record.update(source='model.field', offset=16, mem_bytes=1)
    elif kind == 'projection':
        record.update(source='model.field', expr='model.field & 3U')
    elif kind == 'expr':
        record.update(deps=['model.field'], expr='model.field + 1U')
    else:
        record.update(value='3U')
    dut.sections['signals'] = {'model.alias': record}
    xscfg.write_database(dut.layout, dut.sections)
    dut.storage[16] = 13
    view = require_memory_direct(dut)
    alias = view.signal('model.alias')
    assert alias.U() == expected and not alias.IsVPIBinded()
    if kind != 'direct':
        assert alias.IsOutIO()
    dut.storage[16] = 6
    assert alias.U() == dict(direct=6, projection=2, expr=7, const=3)[kind]
    assert bytes(dut.storage[:16]) == bytes([0xA5] * 16)
