"""Bounded, read-only boundary receipts; never export a per-cycle trace."""
import asyncio
from collections import deque
from contextlib import suppress
from copy import deepcopy

from toffee import RisingEdge,on
from suites.frontend.bpu.utage.monitor.observation import UtageUsefulMonitor


class ReadLifetimeMonitor:
    def __init__(self,agent):
        self.agent,self.native=agent,UtageUsefulMonitor(agent)
        self.recent=deque(maxlen=12)
        self.public,self.effects=[],[]
        self.offered=None
        self.subscription=None
        self.failure=None

    def arm(self):
        if self.offered is not None:raise ValueError('one original feedback per read lifetime')
        self.offered=asyncio.get_running_loop().create_future()

    def capture(self,event):
        try:
            reference=self.agent.reference
            if reference.failure is not None:return
            if reference.input_tick!=event.tick-1 or reference.last_event.tick!=event.tick:
                raise AssertionError('read witness must follow this exact independent semantic boundary')
            native=self.native.sample_at(event).value
            model=reference.model
            row=dict(tick=event.tick,events=reference.events,read=model.read,frame=model.frame,
                prediction=model.prediction,actual=self.agent.monitor.sample_at(event).value,
                effects=tuple(model.effects),native=deepcopy(native),accepted=model.accepted_feedback)
            self.recent.append(row)
            if native['public']['valid']:
                self.public.append(dict(tick=event.tick,bits=deepcopy(native['public']['bits'])))
            if model.effects:self.effects.append(row)
            if self.offered is not None and not self.offered.done() and model.offered is not None:
                self.offered.set_result(dict(tick=event.tick,kind='original-offered'))
        except Exception as error:
            self.failure=error
            if self.offered is not None and not self.offered.done():self.offered.set_exception(error)

    def start(self):
        self.native.sample_at(self.agent.reference.last_event)
        async def delivered(_):pass
        self.subscription=self.agent._execution.subscribe(on(RisingEdge(self.agent.dut.clock),
            capture=self.capture,delivery='lossless',capacity=64)(delivered).bind())
        return self

    def at(self,tick):
        if self.failure is not None:raise self.failure
        rows=[row for row in self.recent if row['tick']==tick]
        if len(rows)!=1:raise AssertionError(f'no unique current read-version witness at {tick}')
        return rows[0]

    def all_protection(self):
        return tuple(value.as_int() for value in self.native.cells.sample().counters)

    async def aclose(self):
        if self.subscription is not None:
            self.agent._execution.reactor.cancel_subscription(self.subscription)
            if self.subscription.task is not None:
                with suppress(asyncio.CancelledError):await self.subscription.task
        if self.failure is not None:raise self.failure
