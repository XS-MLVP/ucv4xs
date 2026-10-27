"""bpuverify.bpu.env.bypass.sram components."""

from bpuverify.bpu.env.abtb.observation import IntegratedObservation
from bpuverify.bpu.env.bypass.natural import CombinedObservation
from bpuverify.bpu.monitor.bypass.sram_reset import SramMonitor


class SramObservation(CombinedObservation):
    async def __aenter__(self):
        result = await IntegratedObservation.__aenter__(self)
        self.bypass_monitor = SramMonitor(self.agent)
        self.bypass_monitor.start(self.checker.bypass)
        return result
