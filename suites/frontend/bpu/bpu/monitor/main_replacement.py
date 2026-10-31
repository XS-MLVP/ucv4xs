"""Lossless SDK response capture; actual values never update a golden model."""
from collections import deque
from contextlib import suppress
import asyncio

from toffee import RisingEdge, on
from suites.frontend.bpu.bpu.bundle.main_replacement import main_replacement_binding
from suites.frontend.bpu.bpu.bundle.values import _plain


class MainReplacementMonitor:
    def __init__(self,agent):
        self.agent=agent
        self.binding=main_replacement_binding(agent)
        self.samples=deque(maxlen=128)
        self.subscription=None

    async def __aenter__(self):
        sampler=self.binding.bits.compile_sampler()
        def capture(event):
            row=_plain(sampler())
            if not row['reset'] and row['valid']:self.samples.append((event.tick,row))
        async def delivered(_):pass
        self.subscription=self.agent._execution.subscribe(on(RisingEdge(self.binding.clock),capture=capture,
            delivery='lossless',capacity=64)(delivered).bind())
        return self

    async def __aexit__(self,*exc):
        self.agent._execution.reactor.cancel_subscription(self.subscription)
        if self.subscription.task is not None:
            with suppress(asyncio.CancelledError):await self.subscription.task

    def response_for(self,source):
        # Association follows the real public lifetime, not a hard-coded
        # response delay or an opportunistic nearby matching data value.
        matches=[(tick,row) for tick,row in self.samples if row['pc']==source.prediction.start_pc
                 and source.prediction_tick<tick<source.meta_tick]
        if len(matches)!=1:
            raise AssertionError(dict(point='one MainBTB response for exact public source',
                prediction_tick=source.prediction_tick,meta_tick=source.meta_tick,matches=matches))
        return matches[0]
