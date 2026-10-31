"""Exercise coverage-v2 programs on a real memory-direct picker DUT."""
import pytest
from toffee import Bundle, ClockCycles, Execution, RisingEdge, Sequence, Wait, Within, XCommClockBackend, xtrigger
from toffee.ir import signal_expr
from toffee.declarative import Bin, CoverPoint, Fields, PatternCoverPoint, SignalCoverGroup, covergroup, coverpoint

from suites.frontend.bpu.drivers.signal import ResetDriver


class ResetPins(Bundle):
    reset: object

    def __init__(self, clock, reset):
        super().__init__(reset=reset)
        self.clock = clock


@xtrigger(sample=RisingEdge('clock'))
def reset_release(pins: ResetPins):
    return Sequence(Wait(signal_expr(pins.reset) == 1),
                    Within(1, 8, signal_expr(pins.reset) == 0))


@coverpoint
class ResetLevel(CoverPoint[bool]):
    asserted = Bin.values(True)
    released = Bin.values(False)


class ResetSequence(PatternCoverPoint[ResetPins]):
    released = reset_release
    repeated = Bin.pattern(reset_release, at_least=2)


fields = Fields(ResetPins)


@covergroup(schema_id='suites.frontend.bpu.native-reset-probe', contract='actual-reset-pins/v1')
class ResetCoverage(SignalCoverGroup[ResetPins]):
    level = ResetLevel(source=fields.signal(lambda pins: pins.reset, value_type=bool))
    sequence = ResetSequence()


@pytest.mark.dut('uras')
async def test_native_mixed_value_and_shared_temporal_bins(dut_factory, monkeypatch):
    dut = dut_factory.create('uras')
    clock = dut.GetXClock()
    pins = ResetPins(clock, dut.reset)
    coverage = ResetCoverage(instance='native-reset-probe')
    coverage.bind(pins=pins, sample=RisingEdge(clock), strategy='native')

    def forbidden_python_sampling(*args, **kwargs):
        raise AssertionError('native coverage must not call Python sample()')

    monkeypatch.setattr(coverage.runtime, 'sample', forbidden_python_sampling)
    backend = XCommClockBackend(clock)
    try:
        async with Execution(backend, coverage=[coverage.runtime]):
            async with ResetDriver(dut) as reset:
                await reset.send(3)
                await ClockCycles(dut.clock, 2)
    finally:
        backend.close()
    assert coverage.level.count(ResetLevel.asserted) > 0
    assert coverage.level.count(ResetLevel.released) > 0
    assert coverage.sequence.count(ResetSequence.released) == 1
    assert coverage.sequence.count(ResetSequence.repeated) == 1
