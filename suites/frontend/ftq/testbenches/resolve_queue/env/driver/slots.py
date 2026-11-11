"""SDK exclusive full-slot driver using the shared dual-phase clock stream."""
from toffee import SyncDriver
from toffee.data import drive_data

from suites.frontend.ftq.testbenches.resolve_queue.transactions.cycle import ResolveInput


class ResolveInputDriver(SyncDriver):
    def __init__(self, dut, ports):
        self.dut, self.ports = dut, ports
        super().__init__(ports.inputs.values(), name='resolve_queue.inputs')

    async def _drive_one(self, frame):
        values = self.ports.encode(frame)
        drive_data(self.ports.bits, values, self.name)
        try:
            return await self.dut.edge(1)
        finally:
            # Withdrawal is complete. Holding ready is not a fake response or
            # an accepted report; the next explicit slot still supplies it.
            drive_data(self.ports.bits, self.ports.encode(ResolveInput(ready=frame.ready)), self.name)
            self.dut.refresh()
