from toffee import DriveStable, FallingEdge, RisingEdge, SyncDriver


class CamDriver(SyncDriver):
    def __init__(self, ports):
        self.ports = ports
        super().__init__(ports.driven, name="cam-cycle")

    async def _drive_one(self, request):
        spec = self.ports.spec
        if len(request.writes) != spec["write_width"] or len(request.queries) != len(spec["queries"]):
            raise ValueError("CAM request must bind all real ports")
        active = [w.address for w in request.writes if w.enabled]
        if len(set(active)) != len(active):
            raise ValueError("conflicting CAM writes are outside the legal contract")
        if any(not 0 <= w.address < spec["size"] or not 0 <= w.value < 1 << spec["width"] for w in request.writes):
            raise ValueError("invalid CAM write payload")
        if any(not 0 <= q.value < 1 << spec["width"] or q.line and spec["kind"] != "address_line" for q in request.queries):
            raise ValueError("invalid CAM query")
        await FallingEdge(self.ports.dut.clock)
        for i, write in enumerate(request.writes):
            self.ports.wen[i].Set(int(write.enabled))
            self.ports.waddr[i].Set(write.address)
            self.ports.wdata[i].Set(write.value)
        for i, query in enumerate(request.queries):
            self.ports.qdata[i].Set(query.value)
            if self.ports.qline[i] is not None:
                self.ports.qline[i].Set(int(query.line))
        await DriveStable(self.ports.dut.clock)
        try:
            return await RisingEdge(self.ports.dut.clock)
        finally:
            # Queries remain stable across the observation; idle clocks must
            # never accidentally repeat the last accepted write notification.
            for signal in self.ports.wen:
                signal.Set(0)
