from toffee import DriveStable, FallingEdge, RisingEdge, SyncDriver


class RarDriver(SyncDriver):
    def __init__(self, ports):
        self.ports = ports
        super().__init__(ports.driven, name="rar-cycle")

    async def _drive_one(self, inp):
        if any(len(values) != self.ports.spec["query_width"] for values in (inp.queries, inp.revoke_last, inp.revoke_older)):
            raise ValueError("RAR request must bind every actual lane")
        if not 0 <= inp.head.value < 128 or not 0 <= inp.redirect.rob.value < 256:
            raise ValueError("RAR pointer outside actual bit width")
        if not 0 <= inp.release.paddr < 1 << self.ports.spec["paddr_bits"]:
            raise ValueError("release exceeds physical-address width")
        for q in inp.queries:
            if not (0 <= q.rob.value < 256 and 0 <= q.lq.value < 128 and 0 <= q.paddr < 1 << self.ports.spec["paddr_bits"]):
                raise ValueError("query exceeds actual signal width")
        await FallingEdge(self.ports.dut.clock)
        self.ports.dut.reset.Set(int(inp.reset))
        self.ports.dut.io_ldWbPtr_flag.Set(int(inp.head.flag))
        self.ports.dut.io_ldWbPtr_value.Set(inp.head.value)
        self.ports.dut.io_release_valid.Set(int(inp.release.valid))
        self.ports.dut.io_release_bits_paddr.Set(inp.release.paddr)
        redir = inp.redirect
        for signal, value in zip(self.ports.redirect, (redir.valid, redir.rob.flag, redir.rob.value, redir.rob.former, redir.flush_self), strict=True):
            signal.Set(int(value))
        for lane, q in enumerate(inp.queries):
            values = (q.valid, q.rob.flag, q.rob.value, q.rob.former, q.lq.flag, q.lq.value, q.paddr, q.data_valid, q.nc,
                      inp.revoke_last[lane], inp.revoke_older[lane])
            for signal, value in zip(self.ports.query[lane], values, strict=True):
                signal.Set(int(value))
        await DriveStable(self.ports.dut.clock)
        try:
            return await RisingEdge(self.ports.dut.clock)
        finally:
            self.ports.dut.reset.Set(0)
            self.ports.dut.io_release_valid.Set(0)
            self.ports.redirect[0].Set(0)
            for lane in self.ports.query:
                lane[0].Set(0)
                lane[-2].Set(0)
                lane[-1].Set(0)
