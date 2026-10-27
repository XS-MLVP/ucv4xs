from types import SimpleNamespace

import pytest

from bpuverify.tage.monitor.shadow import TageShadowMonitor
from tests.framework.fakes import native_name_dut


@pytest.mark.parametrize('dut', (SimpleNamespace(), SimpleNamespace(dut=SimpleNamespace())))
def test_shadow_monitor_requires_native_picker_memory_methods(dut):
    with pytest.raises(RuntimeError, match='picker --rw mem_direct'):
        TageShadowMonitor(dut)


@pytest.mark.parametrize('names,count', (((), 0), ((
    'TOP.Tage.tables_7.tage_entry_write_buffer_bank0.shadowValid_0_0',
    'OTHER.Tage.tables_7.tage_entry_write_buffer_bank0.shadowValid_0_0'), 2)))
def test_shadow_monitor_rejects_missing_or_ambiguous_bindings(names, count, tmp_path):
    dut = native_name_dut(tmp_path, names)
    with pytest.raises(RuntimeError, match=f'shadowValid_0_0.*found {count}'):
        TageShadowMonitor(dut)


@pytest.mark.parametrize('table', (-1, 8, '7'))
def test_shadow_monitor_rejects_unsupported_table_before_native_access(table):
    with pytest.raises(ValueError, match='table must be a configured table'):
        TageShadowMonitor(SimpleNamespace(), table=table)
