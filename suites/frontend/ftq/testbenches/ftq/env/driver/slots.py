"""SDK-owned input slots with explicit combinational staging and withdrawal.

Unlike SingleCycleDriver, a staged request may intentionally remain asserted
over multiple explicit edges, and independent channels may be composed before
the next edge. SyncDriver supplies exclusive ownership and active-work checks;
the shared harness supplies continuous lossless sampling and idle-time pause.
The returned event is the slot edge, not proof every source was accepted.
"""
from toffee import SyncDriver
from toffee.data import drive_data

from suites.frontend.ftq.testbenches.ftq.transactions.cycle import FtqInput


class FtqInputDriver(SyncDriver):
    def __init__(self, dut, ports):
        self.dut, self.ports = dut, ports
        self.frame = FtqInput()
        super().__init__(ports.inputs.values(), name='ftq.inputs')

    def present(self, frame):
        values = self.ports.encode(frame)
        self._claim()
        drive_data(self.ports.bits, values, self.name)
        self.frame = frame
        self.dut.refresh()

    async def _drive_one(self, frame):
        self.present(frame)
        try:
            return await self.dut.edge(1)
        except BaseException:
            # Physical withdrawal is cleanup, never cancellation/completion
            # credit for an input whose accepting edge may already have run.
            self.present(FtqInput(consumers=frame.consumers))
            raise

    def close(self):
        claimed = self._claimed
        # Let SDK reject active work BEFORE cleanup changes any physical input.
        super().close()
        if claimed:
            self.frame = FtqInput()
            drive_data(self.ports.bits, self.ports.encode(self.frame), self.name)
            self.dut.refresh()
