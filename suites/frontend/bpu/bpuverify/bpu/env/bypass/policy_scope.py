"""bpuverify.bpu.env.bypass.policy_scope components."""

from bpuverify.bpu.env.abtb.observation import IntegratedObservation
from bpuverify.bpu.env.bypass.history_base import CombinedObservation
from bpuverify.bpu.monitor.bypass.policy import SramMonitor


class NonzeroObservation(CombinedObservation):
    async def __aenter__(self):
        result = await IntegratedObservation.__aenter__(self)
        self.bypass_monitor = SramMonitor(self.agent)
        self.bypass_monitor.start(self.checker.bypass)
        return result
