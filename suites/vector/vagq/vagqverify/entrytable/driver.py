"""EntryTable input ownership and clock advancement."""
from toffee import ClockCycles

from .probe import encode
from .types import Beat


class Driver:
    def __init__(self, dut, ports):
        self.clock = ports.clock
        self.reset = ports.reset
        self.ports = ports
        self.reset.AsImmWrite()
        for signal in ports.inputs.values():
            signal.AsImmWrite()

    def drive(self, beat: Beat):
        self.ports.inputs.drive(encode(beat))

    async def reset_dut(self):
        self.drive(Beat())
        self.reset.Set(1)
        await ClockCycles(self.clock, 2)
        self.reset.Set(0)
        await ClockCycles(self.clock, 1)

    async def tick(self):
        await ClockCycles(self.clock, 1)
