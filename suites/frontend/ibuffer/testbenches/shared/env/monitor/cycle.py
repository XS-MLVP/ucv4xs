"""Cycle samplers used by the IBuffer DUT agents."""

from __future__ import annotations

from contextlib import asynccontextmanager

from toffee import DriveStable, RisingEdge, SamplingMonitor


class DualPhaseMonitor:
    """Lossless pre-edge and post-edge snapshots for a clocked DUT."""

    def __init__(self, clock, capture_before, capture_after):
        self._before = SamplingMonitor(DriveStable(clock), capture=capture_before)
        self._after = SamplingMonitor(RisingEdge(clock), capture=capture_after)

    @asynccontextmanager
    async def running(self, execution):
        async with self._before.start(execution), self._after.start(execution):
            yield self

    async def recv(self):
        return await self._before.recv(), await self._after.recv()
