"""Component IO is already evaluated; no standalone top-pin launch delay."""
import asyncio
from contextlib import suppress

from toffee import DriveStable, RisingEdge, on

from bpuverify.bpu.bundle.ras_semantic import semantic_binding
from bpuverify.bpu.bundle.values import _plain
from bpuverify.ras.monitor.semantic import decode_events


class RasSemanticComponentMonitor:
    def __init__(self,agent,*,observe_resources=False):
        self.agent,self.binding = agent,semantic_binding(agent,observe_resources=observe_resources)
        self.subscriptions = []

    def start(self,checker):
        inputs = self.binding.bits.inputs.compile_sampler()
        outputs = self.binding.bits.outputs.compile_sampler()
        consumer = self.binding.bits.consumer.compile_sampler()
        def capture_input(event):
            checker.capture_input(event,decode_events(inputs()),consumer=_plain(consumer()))
        def capture_output(event):
            row = _plain(outputs())
            extra = dict(resources=row['resources']) if 'resources' in row else {}
            checker.capture_output(event,row['public'],retained=row['retained'],consumer=_plain(consumer()),**extra)
        async def delivered(_):
            pass
        for trigger,capture in ((DriveStable(self.binding.clock),capture_input),(RisingEdge(self.binding.clock),capture_output)):
            self.subscriptions.append(self.agent._execution.subscribe(on(trigger,delivery='lossless',capacity=64,
                capture=capture)(delivered).bind()))
        return self

    async def aclose(self):
        for subscription in self.subscriptions:
            self.agent._execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError):
                    await subscription.task
