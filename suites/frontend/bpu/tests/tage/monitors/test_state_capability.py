from types import SimpleNamespace

import pytest

from bpuverify.tage.monitor.state import TagePredictionStateMonitor
from tests.framework.fakes import native_name_dut


def test_state_monitor_requires_native_picker_memory():
    with pytest.raises(RuntimeError, match='picker --rw mem_direct'):
        TagePredictionStateMonitor(SimpleNamespace(), None, None)


@pytest.mark.parametrize('names, count', (((), 0), (('TOP.Tage.s2_hits_0_0', 'OTHER.Tage.s2_hits_0_0'), 2)))
def test_state_monitor_requires_unique_first_hit_signal(names, count, tmp_path):
    dut = native_name_dut(tmp_path, names)
    with pytest.raises(RuntimeError, match=f's2_hits_0_0.*found {count}'):
        TagePredictionStateMonitor(dut, None, None)
