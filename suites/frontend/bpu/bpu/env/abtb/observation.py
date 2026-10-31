"""suites.frontend.bpu.bpu.env.abtb.observation components."""

from suites.frontend.bpu.bpu.env.phr.observation import BpuPhrObservation
from suites.frontend.bpu.bpu.monitor.abtb.observation import IntegratedMonitor


class IntegratedObservation(BpuPhrObservation):
    async def __aenter__(self):
        agent = self.agent
        agent._require_started()
        if agent._phr_observation is not None or self._active or self.monitor is not None:
            raise RuntimeError('integrated ABTB observation requires a new exclusive scope')
        self.monitor = IntegratedMonitor(agent)
        agent._phr_observation, self._active = self, True
        try:
            await agent.prediction_monitor.aclose()
            await agent.meta_monitor.aclose()
            self.monitor.start(agent._execution, observer=self.checker.capture)
        except BaseException:
            await self.aclose()
            raise
        return self
