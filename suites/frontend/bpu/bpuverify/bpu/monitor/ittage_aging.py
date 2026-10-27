"""Two-phase @on samples, bounded lossless delivery; no trace export."""
import asyncio
from contextlib import suppress
from toffee import DriveStable,RisingEdge,Transfer,on
from bpuverify.bpu.bundle.ittage_aging import aging_binding
from bpuverify.bpu.bundle.values import _plain


class IttageAgingMonitor:
    def __init__(self,agent):
        self.agent,self.binding,self.subscriptions=agent,aging_binding(agent),[]

    def start(self,checker):
        sample=self.binding.bits.compile_sampler()
        for phase,trigger in (('preedge',DriveStable),('rising',RisingEdge)):
            def capture(event,phase=phase):
                row=_plain(sample())
                row['feedback']=_plain(self.agent.ports.training.bits.sample()) if row['feedback_valid'] else None
                checker.capture(phase,Transfer(event=event,value=row))
            async def delivered(_):pass
            spec=on(trigger(self.binding.clock),delivery='lossless',capacity=64,capture=capture)(delivered)
            self.subscriptions.append(self.agent._execution.subscribe(spec.bind()))
        return self

    async def aclose(self):
        for subscription in self.subscriptions:
            self.agent._execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError):await subscription.task
        self.subscriptions.clear()
