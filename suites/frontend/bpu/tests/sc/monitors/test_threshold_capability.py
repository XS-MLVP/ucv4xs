"""Missing native observation support is an error, never a skipped test."""
from types import SimpleNamespace

import pytest

from suites.frontend.bpu.sc.monitor.threshold import ScThresholdMonitor
from tests.framework.fakes import native_name_dut


def test_threshold_monitor_requires_native_picker_memory():
    with pytest.raises(RuntimeError, match='picker --rw mem_direct'):
        ScThresholdMonitor(SimpleNamespace())


@pytest.mark.parametrize('names, count', [
    ((), 0), (('TOP.Sc.scThreshold_0_value', 'OTHER.Sc.scThreshold_0_value'), 2),
])
def test_threshold_monitor_requires_unique_signal_per_way(names, count, tmp_path):
    dut = native_name_dut(tmp_path, names)
    with pytest.raises(RuntimeError, match=f'way 0.*found {count}'):
        ScThresholdMonitor(dut)
