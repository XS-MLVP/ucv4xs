"""Small shared runtime helpers for running a DUT under toffee's main framework."""
from __future__ import annotations

from contextlib import asynccontextmanager

from toffee import Execution, XCommClockBackend


@asynccontextmanager
async def execution(dut, *, max_batch_ticks: int = 64):
    backend = XCommClockBackend(dut.GetXClock())
    try:
        async with Execution(backend, max_batch_ticks=max_batch_ticks):
            yield backend
    finally:
        backend.close()
