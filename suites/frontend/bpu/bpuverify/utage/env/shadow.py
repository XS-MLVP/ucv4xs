"""bpuverify.utage.env.shadow components."""

from contextlib import asynccontextmanager
from bpuverify.utage.monitor.shadow import UtageShadowMonitor


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
