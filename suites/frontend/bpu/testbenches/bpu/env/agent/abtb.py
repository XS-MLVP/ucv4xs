"""Exclusive integrated ABTB and bypass observation lifecycles."""

from suites.frontend.bpu.testbenches.bpu.env.agent.phr import BpuPhrObservation
from suites.frontend.bpu.testbenches.bpu.env.monitor.abtb.observation import IntegratedMonitor
from suites.frontend.bpu.testbenches.bpu.env.monitor.bypass.monitor import BypassMonitor
from suites.frontend.bpu.testbenches.bpu.env.monitor.bypass.policy import SramMonitor
from suites.frontend.bpu.testbenches.bpu.checker.abtb.write import WriteChecker
from suites.frontend.bpu.testbenches.bpu.env.monitor.abtb.write import WriteMonitor


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


class NonzeroObservation(CombinedObservation):
    async def __aenter__(self):
        result = await IntegratedObservation.__aenter__(self)
        self.bypass_monitor = SramMonitor(self.agent)
        self.bypass_monitor.start(self.checker.bypass)
        return result


class WriteObservation(NonzeroObservation):
    def __init__(self, agent, checker, *, max_frames=20000):
        super().__init__(agent, checker)
        self.write_checks, self.write_monitor = WriteChecker(checker, max_frames=max_frames), None

    async def __aenter__(self):
        result = await super().__aenter__()
        try:
            self.write_monitor = WriteMonitor(self.agent)
            self.write_monitor.start(self.write_checks)
        except BaseException:
            await self.aclose()
            raise
        return result

    async def aclose(self, *, resume_streams=True):
        monitor, self.write_monitor = self.write_monitor, None
        try:
            if monitor is not None:
                await monitor.aclose()
        finally:
            bypass = getattr(self, 'bypass_monitor', None)
            self.bypass_monitor = None
            try:
                if bypass is not None:
                    await bypass.aclose()
            finally:
                # CombinedObservation.aclose has no resume_streams argument.
                # This new scope preserves the base agent-shutdown contract.
                await BpuPhrObservation.aclose(self, resume_streams=resume_streams)
