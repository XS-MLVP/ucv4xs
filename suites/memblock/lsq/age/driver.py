from toffee import DriveStable, FallingEdge, RisingEdge, SyncDriver

from .types import bitmap


class AgeDriver(SyncDriver):
    def __init__(self, ports):
        self.ports = ports
        super().__init__(ports.driven, name="age-cycle")

    async def _drive_one(self, request):
        if len(request.enqueues) != self.ports.spec["enqueue_width"]:
            raise ValueError("age request must bind each actual enqueue lane")
        incoming = [item for item in request.enqueues if item is not None]
        for values in (incoming, request.removes, request.ready):
            if len(set(values)) != len(values) or any(not 0 <= item < self.ports.spec["size"] for item in values):
                raise ValueError("invalid age-selector ID set")
        if request.reset and (incoming or request.removes or request.ready):
            raise ValueError("reset requires idle age-selector inputs")
        await FallingEdge(self.ports.dut.clock)
        self.ports.dut.reset.Set(int(request.reset))
        self.ports.dut.io_deq.Set(bitmap(request.removes))
        self.ports.dut.io_ready.Set(bitmap(request.ready))
        for signal, item in zip(self.ports.enq, request.enqueues, strict=True):
            signal.Set(0 if item is None else 1 << item)
        await DriveStable(self.ports.dut.clock)
        try:
            return await RisingEdge(self.ports.dut.clock)
        finally:
            self.ports.dut.reset.Set(0)
            self.ports.dut.io_deq.Set(0)
            for signal in self.ports.enq:
                signal.Set(0)
