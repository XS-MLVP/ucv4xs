"""Small runtime helper for toffee's main execution framework."""
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


def sweep_inputs(env, value: int, exclude=()) -> None:
    """Drive every generated input to all-ones/all-zeros.

    Structural stress probes own this bit-level sweep; keeping it in the
    runtime means testcases never iterate the native DUT directly.
    """
    dut = env.dut
    excluded = set(exclude)
    for name, signal in vars(dut).items():
        if name in excluded or not hasattr(signal, 'IsInIO'):
            continue
        if signal.IsInIO() and not signal.IsOutIO():
            width = max(1, int(getattr(signal, 'mWidth', 1)))
            signal.Set(((1 << width) - 1) if value else 0)
