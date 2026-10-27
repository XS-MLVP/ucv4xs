"""Read-only public/native witnesses and phase notifications via @on capture."""
import asyncio
from contextlib import suppress
from copy import deepcopy

from toffee import RisingEdge, on
from bpuverify.utage.monitor.observation import UtageUsefulMonitor


class LearningBoundaryMonitor:
    def __init__(self, agent):
        self.agent = agent
        self.monitor = UtageUsefulMonitor(agent)
        self.rows = []
        self.trigger = None
        self.phase = None
        self.subscription = None

    def arm(self, phase):
        if self.trigger is not None:
            raise ValueError('one disable boundary per lifetime')
        self.phase = phase
        self.trigger = asyncio.get_running_loop().create_future()

    def capture(self, event):
        row = self.monitor.sample_at(event).value
        model, events = self.agent.reference.model, self.agent.reference.events
        witness = dict(tick=event.tick, enabled=row['enable'], public=deepcopy(row['public']),
            tables=deepcopy(row['tables']), changes=deepcopy(row.get('changes', ())),
            logical=dict(enabled=None if events is None else events.enabled,
                offered=model.offered is not None, qualified=model.learning is not None,
                accepted=model.accepted_feedback, effects=tuple(model.effects)))
        self.rows.append(witness)
        # Raw input capture precedes the qualification boundary. An offered
        # original has advanced one stage; changing enable now leaves that
        # qualified learning alive while its effect becomes visible disabled.
        ready = row['public']['valid'] if self.phase == 'before-qualification' else model.offered is not None
        if self.trigger is not None and not self.trigger.done() and ready:
            self.trigger.set_result(witness)

    def start(self):
        # Start the actual delta observer at its already-warm state. This is
        # NOT golden initialization: the complete state is separately checked
        # against the reset-derived closed form before any new feedback.
        self.monitor.sample_at(self.agent.reference.last_event)
        async def delivered(_): pass
        self.subscription = self.agent._execution.subscribe(on(RisingEdge(self.agent.dut.clock),
            capture=self.capture, delivery='lossless', capacity=64)(delivered).bind())
        return self

    async def aclose(self):
        if self.subscription is not None:
            self.agent._execution.reactor.cancel_subscription(self.subscription)
            if self.subscription.task is not None:
                with suppress(asyncio.CancelledError):
                    await self.subscription.task

    def all_protection(self):
        snapshot = self.monitor.cells.sample()
        return tuple(value.as_int() for value in snapshot.counters)
