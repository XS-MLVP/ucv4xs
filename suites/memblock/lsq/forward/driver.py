from toffee import DriveStable, FallingEdge, RisingEdge, SyncDriver
from .codec import encode


class ForwardDriver(SyncDriver):
    def __init__(self, ports):
        self.ports = ports
        super().__init__(tuple(ports.inputs.values()), name="forward-cycle")

    async def _drive_one(self, inp):
        pins = encode(inp)
        assert set(pins) == set(self.ports.inputs)
        await FallingEdge(self.ports.dut.clock)
        for name, pin in self.ports.inputs.items():
            pin.Set(pins[name])
        await DriveStable(self.ports.dut.clock)
        try:
            return await RisingEdge(self.ports.dut.clock)
        finally:
            for name, pin in self.ports.inputs.items():
                if name.endswith("s0Req_valid") or name.endswith("s1Kill"):
                    pin.Set(0)
