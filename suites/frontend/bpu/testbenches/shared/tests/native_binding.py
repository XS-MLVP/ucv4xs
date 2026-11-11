"""Shared native binding smoke, with DUT-specific observations supplied by owners."""
from suites.frontend.bpu.testbenches.shared.env.memory_direct import require_memory_direct


def check_observation_bindings(dut, observation_layers):
    def forbidden(*args, **kwargs):
        raise AssertionError('production observations must not call legacy internal getters')
    dut.GetInternalSignal = dut.GetInternalSignalList = forbidden
    view = require_memory_direct(dut)
    assert view.base > 0 and view.names()
    assert not dut.clock.IsVPIBinded() and not dut.reset.IsVPIBinded()
    # These are infrastructure checks, not functional credit: no internal writes.
    monitors = observation_layers(dut)
    dut.Step(2)
    dut.reset.Set(0)
    dut.Step(4)
    for monitor in monitors:
        assert monitor.binding.bits.sample() is not None
    assert not dut.internal_signals
    assert all(not signal.IsVPIBinded() for signal in view._signals.values())
