"""suites.frontend.bpu.utage.env.partial_wrap components."""

from contextlib import asynccontextmanager
from suites.frontend.bpu.utage.monitor.shadow import UtageShadowMonitor


@asynccontextmanager
async def observe_partial_wrap(agent, checker):
    if agent._execution is None:
        raise RuntimeError('partial-wrap observation needs a started agent')
    monitor = UtageShadowMonitor(agent, table=1)
    def observe(observation):
        monitor.observe(observation)
        checker.capture(observation)
    monitor.start(agent._execution, observer=observe)
    try:
        yield monitor
        checker.raise_failure()
    finally:
        await monitor.aclose()
