"""Ownership and clock advancement for the single-slot pipe protocol."""
from toffee import ClockCycles

from suites.vector.vagq.testbenches.pipeline.env.encoding import encode
from suites.vector.vagq.testbenches.pipeline.env.specs import Spec
from suites.vector.vagq.testbenches.pipeline.transactions import Beat


class Driver:
    def __init__(self, dut, ports, spec: Spec):
        self.clock = ports.clock
        self.reset = ports.reset
        self.ports = ports
        self.spec = spec
        self.reset.AsImmWrite()
        for signal in ports.inputs.values():
            signal.AsImmWrite()

    def drive(self, beat: Beat):
        self.ports.inputs.drive(encode(self.spec, beat))

    async def reset_dut(self):
        self.drive(Beat(payload=self.spec.payload_type()))
        self.reset.Set(1)
        await ClockCycles(self.clock, 2)
        self.reset.Set(0)
        await ClockCycles(self.clock, 1)

    async def tick(self):
        await ClockCycles(self.clock, 1)
