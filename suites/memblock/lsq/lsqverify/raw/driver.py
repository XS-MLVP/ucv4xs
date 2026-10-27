from toffee import DriveStable, FallingEdge, RisingEdge, SyncDriver


class RawDriver(SyncDriver):
    def __init__(self, ports):
        self.ports = ports
        super().__init__(ports.driven, name="raw-cycle")

    async def _drive_one(self, inp):
        spec = self.ports.spec
        if len(inp.queries) != spec["query_width"] or len(inp.stores) != spec["store_width"]:
            raise ValueError("RAW input must bind every actual lane")
        if any(len(values) != spec["query_width"] for values in (inp.revoke_last, inp.revoke_older)):
            raise ValueError("RAW revoke width mismatch")
        for query in inp.queries:
            if not (0 <= query.paddr < 1 << 48 and 0 <= query.mask < 1 << 16 and 0 <= query.rob.value < 256
                    and 0 <= query.sq.value < 64 and 0 <= query.ftq.value < 64 and 0 <= query.ftq_offset < 32
                    and 0 <= query.checkpoint < 1 << 64):
                raise ValueError("RAW query exceeds actual pin width")
        for store in inp.stores:
            if not (0 <= store.paddr < 1 << 48 and 0 <= store.mask < 1 << 16 and 0 <= store.rob.value < 256
                    and 0 <= store.ftq_value < 64 and 0 <= store.ftq_offset < 32):
                raise ValueError("RAW store exceeds actual pin width")
        await FallingEdge(self.ports.dut.clock)
        self.ports.dut.reset.Set(int(inp.reset))
        for signal, value in zip(self.ports.head, (inp.head.first, inp.head.second, inp.head.value), strict=True):
            signal.Set(int(value))
        red = inp.redirect
        for signal, value in zip(self.ports.redirect, (red.valid, red.rob.flag, red.rob.value, red.rob.former, red.flush_self), strict=True):
            signal.Set(int(value))
        for lane, query in enumerate(inp.queries):
            values = (query.valid, query.rob.flag, query.rob.value, query.rob.former, query.sq.first, query.sq.second, query.sq.value,
                      query.paddr, query.mask, query.data_valid, query.is_rvc, query.ftq.flag, query.ftq.value, query.ftq_offset,
                      query.checkpoint, inp.revoke_last[lane], inp.revoke_older[lane])
            for signal, value in zip(self.ports.query[lane], values, strict=True):
                signal.Set(int(value))
        for signals, store in zip(self.ports.stores, inp.stores, strict=True):
            values = (store.valid, store.rob.flag, store.rob.value, store.rob.former, store.paddr, store.mask, store.wline, store.tlb_miss,
                      store.ftq_flag, store.ftq_value, store.ftq_offset, store.is_rvc)
            for signal, value in zip(signals, values, strict=True):
                signal.Set(int(value))
        await DriveStable(self.ports.dut.clock)
        try:
            return await RisingEdge(self.ports.dut.clock)
        finally:
            self.ports.dut.reset.Set(0)
            self.ports.redirect[0].Set(0)
            for lane in self.ports.query:
                lane[0].Set(0)
                lane[-2].Set(0)
                lane[-1].Set(0)
            for lane in self.ports.stores:
                lane[0].Set(0)
