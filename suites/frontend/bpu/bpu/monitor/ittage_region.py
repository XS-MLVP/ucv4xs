"""Two-phase @on observation; no waveform or per-cycle JSON export."""
import asyncio
from contextlib import suppress
from toffee import DriveStable, RisingEdge, Transfer, on
from suites.frontend.bpu.bpu.bundle.ittage_region import region_binding
from suites.frontend.bpu.bpu.bundle.values import _plain


class RegionMonitor:
    def __init__(self, agent):
        self.agent, self.binding, self.subscriptions = agent, region_binding(agent), []

    def start(self, checker):
        if self.subscriptions:
            raise RuntimeError('region monitor is already started')
        sample = self.binding.bits.compile_sampler()
        for phase, trigger in (('preedge', DriveStable), ('rising', RisingEdge)):
            def capture(event, phase=phase):
                row = _plain(sample())
                row['feedback'] = _plain(self.agent.ports.training.bits.sample()) if row['feedback_valid'] else None
                checker.capture(phase, Transfer(event=event, value=row))
            async def delivered(_):
                pass
            spec = on(trigger(self.binding.clock), delivery='lossless', capacity=64, capture=capture)(delivered)
            self.subscriptions.append(self.agent._execution.subscribe(spec.bind()))
        return self

    async def aclose(self):
        execution = self.agent._execution
        for subscription in self.subscriptions:
            execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError):
                    await subscription.task
        self.subscriptions.clear()
