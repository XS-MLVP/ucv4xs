"""Clock ownership for the OrderedPermitCtrl level protocol."""
from toffee import ClockCycles

from suites.vector.vagq.testbenches.ordered.env.encoding import encode
from suites.vector.vagq.testbenches.ordered.transactions import Beat


class Driver:
    def __init__(self, dut, ports):
        self.dut = dut
        self.ports = ports
        self.clock = ports.clock
        self.reset_signal = ports.reset
        self.reset_signal.AsImmWrite()
        for signal in ports.inputs.values():
            signal.AsImmWrite()

    def drive(self, beat: Beat):
        self.ports.inputs.drive(encode(beat))

    async def reset(self):
        self.drive(Beat())
        self.reset_signal.Set(1)
        await ClockCycles(self.clock, 2)
        self.reset_signal.Set(0)
        await ClockCycles(self.clock, 1)

    async def tick(self):
        await ClockCycles(self.clock, 1)
