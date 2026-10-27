"""Exclusive passive ABTB write/SRAM scope with a configurable observation budget."""
from bpuverify.bpu.env.bypass.aging_scope import NonzeroObservation
from bpuverify.bpu.env.phr.observation import BpuPhrObservation
from bpuverify.bpu.checker.abtb.write import WriteChecker
from bpuverify.bpu.monitor.abtb.write import WriteMonitor


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
