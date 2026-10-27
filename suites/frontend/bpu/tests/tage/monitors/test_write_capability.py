from types import SimpleNamespace

import pytest

from bpuverify.tage.monitor.write import TageWriteActivityMonitor
from tests.framework.fakes import native_name_dut


def test_write_monitor_requires_native_picker_memory():
    with pytest.raises(RuntimeError, match='picker --rw mem_direct'):
        TageWriteActivityMonitor(SimpleNamespace())


@pytest.mark.parametrize('names, count', (((), 0), ((
    'TOP.Tage.tables_3.tage_entry_write_buffer_bank0.io_write_0_valid',
    'OTHER.Tage.tables_3.tage_entry_write_buffer_bank0.io_write_0_valid'), 2)))
def test_write_monitor_requires_unique_port_binding(names, count, tmp_path):
    dut = native_name_dut(tmp_path, names)
    with pytest.raises(RuntimeError, match=f'io_write_0_valid.*found {count}'):
        TageWriteActivityMonitor(dut)
