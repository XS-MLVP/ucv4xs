from toffee import DriveStable, FallingEdge, RisingEdge, SyncDriver


class VirtualLoadQueueDriver(SyncDriver):
    def __init__(self, ports):
        self.ports = ports
        super().__init__(ports.driven, name="vlq-cycle")

    async def _drive_one(self, inp):
        if len(inp.dispatch) != self.ports.spec["dispatch_width"] or len(inp.writebacks) != self.ports.spec["writeback_width"]:
            raise ValueError("VLQ request must bind every actual lane")
        for d in inp.dispatch:
            if not (0 <= d.rob.value < 256 and 0 <= d.start.value < 128 and 0 <= d.flows < 32):
                raise ValueError("dispatch exceeds actual signal widths")
        if any(not 0 <= w.index < 128 for w in inp.writebacks) or not 0 <= inp.redirect.rob.value < 256:
            raise ValueError("VLQ input exceeds actual signal widths")
        if inp.reset and (any(d.valid for d in inp.dispatch) or any(w.valid for w in inp.writebacks) or inp.redirect.valid):
            raise ValueError("reset requires idle VLQ transactions")
        await FallingEdge(self.ports.dut.clock)
        self.ports.dut.reset.Set(int(inp.reset))
        for signals, request in zip(self.ports.dispatch, inp.dispatch, strict=True):
            values = (request.valid, request.rob.flag, request.rob.value, request.rob.former,
                      request.start.flag, request.start.value, request.flows)
            for signal, value in zip(signals, values, strict=True):
                signal.Set(int(value))
        for signals, wb in zip(self.ports.writebacks, inp.writebacks, strict=True):
            for signal, value in zip(signals, (wb.valid, wb.index, wb.update_address, wb.replay), strict=True):
                signal.Set(int(value))
        redir = inp.redirect
        for signal, value in zip(self.ports.redirect, (redir.valid, redir.rob.flag, redir.rob.value, redir.rob.former, redir.flush_self), strict=True):
            signal.Set(int(value))
        await DriveStable(self.ports.dut.clock)
        try:
            return await RisingEdge(self.ports.dut.clock)
        finally:
            self.ports.dut.reset.Set(0)
            self.ports.redirect[0].Set(0)
            for lane in (*self.ports.dispatch, *self.ports.writebacks):
                lane[0].Set(0)
