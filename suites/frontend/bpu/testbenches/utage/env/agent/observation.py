"""Started-agent scopes for useful-bit and shadow-state observation."""

from contextlib import asynccontextmanager
from suites.frontend.bpu.testbenches.utage.env.monitor.observation import UtageUsefulMonitor
from suites.frontend.bpu.testbenches.utage.env.monitor.shadow import UtageShadowMonitor


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


@asynccontextmanager
async def observe_shadow(agent, *, table):
    if agent._execution is None:
        raise RuntimeError('shadow observation needs a started agent')
    monitor = UtageShadowMonitor(agent, table=table)
    monitor.start(agent._execution, observer=monitor.observe)
    try:
        yield monitor
    finally:
        await monitor.aclose()


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
