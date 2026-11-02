"""Use Toffee's single-cycle template with held configuration and pulse idle."""
from toffee import SyncSingleCycleDriver

from .transactions import Cycle


class SbufferDriver(SyncSingleCycleDriver[Cycle]):
    def __init__(self, ports):
        self.ports = ports
        super().__init__(ports.dut.clock, ports.bits, idle=ports.encode(Cycle()),
                         encoder=ports.encode, name='sbuffer.public_inputs')

    async def _drive_one(self, request):
        # Runs inside SyncDriver's serialized input slot. Keep external level
        # inputs stable; withdraw every pulse and its payload after this edge.
        self.ports.encode(request)
        self.idle = self.ports.encode(Cycle(controls=request.controls))
        return await super()._drive_one(request)
