"""Small shared runtime helpers for running a DUT under toffee's main framework."""
from __future__ import annotations

from contextlib import asynccontextmanager

from toffee import Execution, XCommClockBackend


@asynccontextmanager
async def execution(target, *, max_batch_ticks: int = 64):
    """Run a native DUT or an environment that owns one.

    Tests pass the suite environment; the native handle stays inside this
    runtime helper.  Passing a generated DUT object directly is retained for
    infrastructure code and smoke probes.
    """

    dut = getattr(target, 'dut', target) if not hasattr(target, 'GetXClock') else target
    backend = XCommClockBackend(dut.GetXClock())
    try:
        async with Execution(backend, max_batch_ticks=max_batch_ticks):
            yield backend
    finally:
        backend.close()


def refresh(env) -> None:
    """Refresh combinational logic through the environment boundary."""
    env.dut.RefreshComb()
