"""Framework-backed single-cycle input slot with paused idle time.

SamplingMonitor subscriptions also request clock progress.  This wrapper adds
only idle-time control to Toffee's single-cycle template; ownership, frame
drive/withdrawal and completion events remain framework code.  The pattern is
shared with the IFU/InstrUncache suites (copied here so this suite does not
import another suite's implementation).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from toffee import SyncSingleCycleDriver


class ExplicitSlotDriver(SyncSingleCycleDriver):
    def __init__(self, clock, bits, *, idle, encoder, name):
        super().__init__(clock, bits, idle=idle, encoder=encoder, name=name)
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
        self.encoder(request)  # Reject malformed work before resuming simulation.
        if self._pause_context is None:
            raise RuntimeError(f"{self.name}: driver requires its holding lifecycle")
        context, self._pause_context = self._pause_context, None
        await context.__aexit__(None, None, None)
        try:
            return await super()._drive_one(request)
        finally:
            await self._pause()
