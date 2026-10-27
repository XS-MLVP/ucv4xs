"""Lossless passive comparison of actual unexecuted-indirect learning boundaries."""
import asyncio
from contextlib import asynccontextmanager, suppress
from toffee import RisingEdge, on
from bpuverify.bpu.bundle.indirect_guard import indirect_guard_binding
from bpuverify.bpu.bundle.values import _plain


@asynccontextmanager
async def actual_target_guard(agent, checks):
    binding = indirect_guard_binding(agent)
    sampler = binding.bits.compile_sampler()
    def capture(event):
        try: checks.actual(event, _plain(sampler()))
        except Exception as error:
            checks.pipeline.failure = error
            raise
    async def delivered(_): pass
    subscription = agent._execution.subscribe(on(RisingEdge(agent.dut.clock), capture=capture,
        delivery='lossless', capacity=64)(delivered).bind())
    try: yield
    finally:
        agent._execution.reactor.cancel_subscription(subscription)
        if subscription.task is not None:
            with suppress(asyncio.CancelledError): await subscription.task
