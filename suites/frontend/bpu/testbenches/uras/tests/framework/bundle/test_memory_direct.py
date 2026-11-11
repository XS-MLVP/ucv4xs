"""MicroRAS native memory and reset observations on the real Picker DUT."""
import pytest

from suites.frontend.bpu.testbenches.shared.env.memory_direct import memory_signal
from suites.frontend.bpu.testbenches.shared.env.memory_direct import require_memory_direct


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
