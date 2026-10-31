"""suites.frontend.bpu.bpu.env.bypass.force components."""

from suites.frontend.bpu.bpu.env.abtb.observation import IntegratedObservation
from suites.frontend.bpu.bpu.env.bypass.natural import CombinedObservation
from suites.frontend.bpu.bpu.monitor.bypass.sram import SramMonitor


class SramObservation(CombinedObservation):
    async def __aenter__(self):
        result = await IntegratedObservation.__aenter__(self)
        self.bypass_monitor = SramMonitor(self.agent)
        self.bypass_monitor.start(self.checker.bypass)
        return result
