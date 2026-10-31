"""Passive reference scope with bounded foreground operations."""
import asyncio
from contextlib import suppress

from toffee import AnyOf, SimTimeout, TaskComplete, XEventKind

from suites.frontend.bpu.bpu.checker.ras.semantic import RasSemanticComponentChecker
from suites.frontend.bpu.bpu.monitor.ras.semantic import RasSemanticComponentMonitor


class RasSemanticEnvironment:
    def __init__(self,agent,*,coverage=None,return_pc=None,reference=None,observe_resources=False):
        self.agent = agent
        self.reference = reference if reference is not None else RasSemanticComponentChecker(coverage=coverage,return_pc=return_pc)
        self.monitor = RasSemanticComponentMonitor(agent,observe_resources=observe_resources)

    async def __aenter__(self):
        self.monitor.start(self.reference)
        return self

    async def __aexit__(self,exc_type,exc,traceback):
        await self.monitor.aclose()
        if exc_type is None:
            self.reference.finish()

    async def wait(self,operation,name,*,timeout_cycles=512):
        task = asyncio.create_task(operation)
        try:
            result = await AnyOf(TaskComplete(task),SimTimeout(timeout_cycles,clock=self.agent.dut.clock))
            self.reference.raise_failure()
            if result.kind is XEventKind.TIMEOUT:
                raise TimeoutError(f'RAS semantic operation did not complete: {name}, state={self.reference.model.state()!r}')
            return result.value
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
