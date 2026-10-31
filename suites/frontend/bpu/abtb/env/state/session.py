"""Own a coherent state observation and optional temporary training writer."""
from contextlib import AsyncExitStack
import sys


class StateObservation:
    def __init__(self, agent, monitor, checker, *, driver=None):
        self.agent, self.monitor, self.checker, self.driver = agent, monitor, checker, driver
        self._stack = None

    async def __aenter__(self):
        if self._stack is not None:
            raise RuntimeError("state observation is already active")
        stack = self._stack = AsyncExitStack()
        try:
            stack.push_async_callback(self.monitor.aclose)
            self.monitor.start(self.agent.execution, observer=self.checker.capture)
            if self.driver is not None:
                await stack.enter_async_context(self.agent.using_training_driver(self.driver))
            await self.agent.reset()
            self.checker.raise_failure()
        except BaseException:
            self._stack = None
            await stack.__aexit__(*sys.exc_info())
            raise
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        stack, self._stack = self._stack, None
        if stack is not None:
            return await stack.__aexit__(exc_type, exc, traceback)
        return False
