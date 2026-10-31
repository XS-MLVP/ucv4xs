"""suites.frontend.bpu.utage.env.observation components."""

from contextlib import asynccontextmanager
from suites.frontend.bpu.utage.monitor.observation import UtageUsefulMonitor


@asynccontextmanager
async def observe_useful(agent, *, observer):
    if agent._execution is None:
        raise RuntimeError('useful observation needs a started agent')
    monitor = UtageUsefulMonitor(agent)
    monitor.start(agent._execution, observer=observer)
    try:
        yield monitor
    finally:
        await monitor.aclose()
