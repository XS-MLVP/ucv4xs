from toffee import DriveStable, FallingEdge, RisingEdge, SyncDriver
from .types import encode


class UnalignDriver(SyncDriver):
    def __init__(self, ports):
        self.ports = ports
        super().__init__(tuple(ports.inputs.values()), name="unalign-cycle")

    async def _drive_one(self, inp):
        values = encode(inp)
        assert set(values) == set(self.ports.inputs)
        await FallingEdge(self.ports.dut.clock)
        for name, pin in self.ports.inputs.items():
            pin.Set(values[name])
        await DriveStable(self.ports.dut.clock)
        try:
            return await RisingEdge(self.ports.dut.clock)
        finally:
            for name, pin in self.ports.inputs.items():
                if name == "reset" or name.endswith("valid") or name.endswith("ready"):
                    pin.Set(0)
