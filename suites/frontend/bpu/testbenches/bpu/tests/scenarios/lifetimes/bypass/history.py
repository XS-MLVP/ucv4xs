"""suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.bypass.history components."""

from suites.frontend.bpu.testbenches.bpu.env.agent.abtb import IntegratedObservation
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.bypass.history_base import CombinedObservation
from suites.frontend.bpu.testbenches.bpu.env.monitor.bypass.hash import SramMonitor


class NonzeroObservation(CombinedObservation):
    async def __aenter__(self):
        result = await IntegratedObservation.__aenter__(self)
        self.bypass_monitor = SramMonitor(self.agent)
        self.bypass_monitor.start(self.checker.bypass)
        return result
