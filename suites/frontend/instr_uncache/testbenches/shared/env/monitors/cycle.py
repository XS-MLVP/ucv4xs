"""Cycle samplers used by the three DUT agents."""

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


class SinglePhaseMonitor:
    """One post-edge snapshot for the combinational response arbiter."""

    def __init__(self, clock, capture):
        self._monitor = SamplingMonitor(RisingEdge(clock), capture=capture)

    @asynccontextmanager
    async def running(self, execution):
        async with self._monitor.start(execution):
            yield self

    async def recv(self):
        return await self._monitor.recv()
