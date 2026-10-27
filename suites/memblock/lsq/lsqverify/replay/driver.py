from toffee import DriveStable, FallingEdge, RisingEdge, SyncDriver
from .codec import encode


class ReplayDriver(SyncDriver):
    def __init__(self, ports):
        self.ports = ports
        super().__init__(tuple(ports.inputs.values()), name="replay-cycle")

    async def _drive_one(self, inp):
        values = encode(inp)
        assert set(values) == set(self.ports.inputs)
        await FallingEdge(self.ports.dut.clock)
        for name, signal in self.ports.inputs.items():
            signal.Set(values[name])
        await DriveStable(self.ports.dut.clock)
        try:
            return await RisingEdge(self.ports.dut.clock)
        finally:
            for name, signal in self.ports.inputs.items():
                if name == "reset" or name.endswith("valid") or name.endswith("ready"):
                    signal.Set(0)
