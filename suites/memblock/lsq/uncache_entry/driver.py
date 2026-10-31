from toffee import DriveStable, FallingEdge, RisingEdge, SyncDriver

from .types import SOURCE_EXCEPTION_BITS, SOURCE_EXCEPTION_MASK


class EntryDriver(SyncDriver):
    def __init__(self, ports):
        self.ports = ports
        super().__init__(ports.driven, name="uncache-entry-cycle")

    async def _drive_one(self, inp):
        q = inp.request
        if not (0 <= q.rob.value < 256 and 0 <= q.lq.value < 128 and 0 <= q.vaddr < 1 << 50
                and 0 <= q.fullva < 1 << 64 and 0 <= q.paddr < 1 << 48 and 0 <= q.gpaddr < 1 << 64
                and 0 <= q.mask < 1 << 16 and q.exceptions & ~SOURCE_EXCEPTION_MASK == 0):
            raise ValueError("entry request exceeds actual exported pins")
        if not (0 <= inp.id_response.mid < 128 and 0 <= inp.id_response.sid < 16 and 0 <= inp.response.data < 1 << 64):
            raise ValueError("entry response exceeds actual exported pins")
        if not self.ports.spec["wakeup_backpressure"] and not (inp.mmio_wake_ready and inp.nc_wake_ready):
            raise ValueError("entry0 has no real wakeup backpressure inputs")
        await FallingEdge(self.ports.dut.clock)
        self.ports.dut.reset.Set(int(inp.reset))
        values = (q.valid, q.rob.flag, q.rob.value, q.rob.former, q.lq.flag, q.lq.value, q.vaddr, q.fullva, q.paddr, q.gpaddr,
                  q.mask, q.nc, q.mmio, q.memory_backed, q.hyper, q.nonleaf, *((q.exceptions >> bit) & 1 for bit in SOURCE_EXCEPTION_BITS))
        for signal, value in zip(self.ports.request, values, strict=True):
            signal.Set(int(value))
        groups = ((self.ports.pending, (inp.pending.flag, inp.pending.value, inp.pending.former)),
                  (self.ports.redirect, (inp.redirect.valid, inp.redirect.rob.flag, inp.redirect.rob.value, inp.redirect.rob.former, inp.redirect.flush_self)),
                  (self.ports.id_response, (inp.id_response.valid, inp.id_response.mid, inp.id_response.sid)),
                  (self.ports.response, (inp.response.valid, inp.response.data, inp.response.error, inp.response.nderr)),
                  (self.ports.ready, (inp.bus_ready, inp.mmio_ready, inp.nc_ready)))
        for signals, values in groups:
            for signal, value in zip(signals, values, strict=True):
                signal.Set(int(value))
        if self.ports.wake_ready:
            for signal, value in zip(self.ports.wake_ready, (inp.mmio_wake_ready, inp.nc_wake_ready), strict=True):
                signal.Set(int(value))
        await DriveStable(self.ports.dut.clock)
        try:
            return await RisingEdge(self.ports.dut.clock)
        finally:
            self.ports.dut.reset.Set(0)
            self.ports.request[0].Set(0)
            self.ports.redirect[0].Set(0)
            self.ports.id_response[0].Set(0)
            self.ports.response[0].Set(0)
            for signal in self.ports.ready:
                signal.Set(0)
