"""SDK-owned full input slots; monitors stay attached while idle time pauses.

SamplingMonitor subscriptions themselves request clock progress. Explicit
Execution.paused() prevents setup/call task changes from inventing extra commit
cycles. Only this idle-time policy extends SyncSingleCycleDriver; its ownership,
acceptance event, full payload withdrawal and cancellation remain SDK behavior.
"""
from contextlib import asynccontextmanager

from toffee import SyncSingleCycleDriver


class CommitInputDriver(SyncSingleCycleDriver):
    def __init__(self, clock, ports):
        from suites.frontend.ftq.testbenches.commit_queue.transactions.types import Input
        super().__init__(clock, ports.bits, idle=ports.encode(Input(0)),
                         encoder=ports.encode, name='commit_queue.inputs')
        self._execution = self._pause_context = None

    async def _pause(self):
        self._pause_context = self._execution.paused()
        await self._pause_context.__aenter__()

    @asynccontextmanager
    async def holding(self, execution):
        self._execution = execution
        try:
            async with self:
                await self._pause()
                try:
                    yield self
                finally:
                    context, self._pause_context = self._pause_context, None
                    if context is not None:
                        await context.__aexit__(None, None, None)
        finally:
            self._execution = None

    async def _drive_one(self, request):
        self.encoder(request)  # Reject before allowing simulation progress.
        if self._pause_context is None:
            raise RuntimeError('CommitQueue driver requires its holding lifecycle')
        context, self._pause_context = self._pause_context, None
        await context.__aexit__(None, None, None)
        try:
            return await super()._drive_one(request)
        finally:
            await self._pause()
