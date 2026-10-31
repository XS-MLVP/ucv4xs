"""Native split DUT binding and one-cycle drive/observe protocol."""
from __future__ import annotations

from suites.vector.vagq.split.probe import bind, encode
from suites.vector.vagq.split.types import Beat


class NativeSplit:
    def __init__(self, dut):
        self.dut = dut
        self.ports, self.sample = bind(dut)
        self.ports.reset.AsImmWrite()
        for signal in self.ports.inputs.values():
            signal.AsImmWrite()
        self.drive(Beat())
        self.ports.reset.Set(1)
        dut.Step(2)
        self.ports.reset.Set(0)
        dut.Step(1)

    def drive(self, beat):
        self.ports.inputs.drive(encode(beat))
        self.dut.RefreshComb()

    def cycle(self, beat):
        self.drive(beat)
        before = self.sample()
        self.dut.Step(1)
        after = self.sample()
        return before, after
