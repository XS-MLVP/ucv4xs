"""suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.bypass.monitor components."""

from contextlib import asynccontextmanager
from suites.frontend.bpu.testbenches.bpu.env.monitor.bypass.monitor import BypassMonitor


@asynccontextmanager
async def observe_bypass(agent, checker):
    monitor = BypassMonitor(agent)
    monitor.start(checker)
    try:
        yield monitor
        checker.raise_failure()
    finally:
        await monitor.aclose()
