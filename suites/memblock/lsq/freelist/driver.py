from toffee import DriveStable, FallingEdge, RisingEdge, SyncDriver


class FreeListDriver(SyncDriver):
    def __init__(self, ports):
        self.ports = ports
        self.clock = ports.dut.clock
        super().__init__((ports.dut.reset, ports.dut.io_free, *ports.confirm), name="freelist-cycle")

    async def _drive_one(self, request):
        if request.allocate not in range(4) or request.mask.bit_count() != request.allocate or request.mask >> 3:
            raise ValueError("invalid allocation confirmation")
        if len(set(request.returns)) != len(request.returns):
            raise ValueError("duplicate return notification")
        await FallingEdge(self.clock)
        self.ports.dut.reset.Set(int(request.reset))
        self.ports.dut.io_free.Set(sum(1 << i for i in request.returns))
        for i, signal in enumerate(self.ports.confirm):
            signal.Set(request.mask >> i & 1)
        await DriveStable(self.clock)
        try:
            return await RisingEdge(self.clock)
        finally:
            self.ports.dut.reset.Set(0)
            self.ports.dut.io_free.Set(0)
            for signal in self.ports.confirm:
                signal.Set(0)
