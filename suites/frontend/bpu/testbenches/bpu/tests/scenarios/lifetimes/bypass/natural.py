"""suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.bypass.natural components."""

from suites.frontend.bpu.testbenches.bpu.env.agent.abtb import IntegratedObservation
from suites.frontend.bpu.testbenches.bpu.env.monitor.bypass.monitor import BypassMonitor


class CombinedObservation(IntegratedObservation):
    async def __aenter__(self):
        result = await super().__aenter__()
        self.bypass_monitor = BypassMonitor(self.agent)
        self.bypass_monitor.start(self.checker.bypass)
        return result

    async def aclose(self):
        monitor = getattr(self, 'bypass_monitor', None)
        if monitor is not None:
            await monitor.aclose()
            self.bypass_monitor = None
        await super().aclose()
