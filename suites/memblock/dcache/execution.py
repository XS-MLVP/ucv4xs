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


def _native(target):
    return target if hasattr(target, 'GetXClock') else target.dut


def step(target, cycles: int = 1) -> None:
    """Advance an environment's native DUT without exposing the handle."""
    _native(target).Step(cycles)


def refresh(target) -> None:
    """Refresh an environment's combinational logic."""
    _native(target).RefreshComb()


def set_reset(target, value: int) -> None:
    """Drive the generated reset input through the environment boundary."""
    _native(target).reset.Set(int(value))


def pulse_reset(target, asserted: int = 3, settle: int = 2) -> None:
    """Apply the project reset sequence used by the legacy environments."""
    set_reset(target, 1)
    step(target, asserted)
    set_reset(target, 0)
    step(target, settle)
