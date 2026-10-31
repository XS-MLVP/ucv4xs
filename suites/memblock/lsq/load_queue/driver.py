from toffee import DriveStable, FallingEdge, RisingEdge, SyncDriver

from .codec import encode


class LoadQueueDriver(SyncDriver):
    def __init__(self, ports):
        self.ports = ports
        super().__init__(tuple(ports.inputs.values()), name="actual-load-queue-cycle")

    async def _drive_one(self, inp):
        values = encode(inp)
        await FallingEdge(self.ports.dut.clock)
        for name, signal in self.ports.inputs.items():
            signal.Set(values[name])
        await DriveStable(self.ports.dut.clock)
        try:
            return await RisingEdge(self.ports.dut.clock)
        finally:
            for name, signal in self.ports.inputs.items():
                if name == "reset" or name.endswith("valid") or "revokeLast" in name or name.endswith("_ready"):
                    signal.Set(0)
