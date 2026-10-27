"""Read-only native clear snapshot and the actually consumed reset boundary."""
import asyncio
from contextlib import suppress
from toffee import RisingEdge,on
from bpuverify.mbtb.monitor.entry import MbtbEntryActivityMonitor


class CleanupMonitor:
    def __init__(self,agent):
        self.agent=agent
        self.entries=MbtbEntryActivityMonitor(agent.dut)
        self.sample=self.entries.binding.bits.compile_sampler()
        self.latest=self.reset=None
        self.failure=self.subscription=None
        self.armed=False

    def snapshot(self,tick):
        values=self.entries.decode(self.sample())
        clears=[]
        for align,row in enumerate(values['banks']):
            for bank,ways in enumerate(row):
                for way,port in enumerate(ways):
                    if port['write_valid'] and port['write_branch_type']==0:
                        clears.append(dict(align=align,bank=bank,way=way,row=port['write_set_idx'],
                            tag=port['write_tag'],position=port['write_position'],kind=port['write_branch_type'],
                            action=port['write_ras_action'],carry=port['write_carry'],lower=port['write_lower']))
        return dict(tick=tick,clears=clears,consumed_reset=bool(self.agent.reference.events.reset))

    def capture(self,event):
        if self.failure is not None:return
        try:
            reference=self.agent.reference
            if reference.input_tick!=event.tick-1:
                raise AssertionError('cleanup observer requires this exact semantic input boundary')
            self.latest=self.snapshot(event.tick)
            if self.armed and reference.events.reset and self.reset is None:
                state=reference.model.state()
                # Keep every pending-owner count in the compact evidence,
                # with JSON keys rather than Python's (align, bank) keys.
                for key in ('entry_pending','counter_pending'):
                    state[key]={'.'.join(map(str,owner)):count for owner,count in state[key].items()}
                self.reset=dict(tick=event.tick,independent_state=state)
        except Exception as error:self.failure=error

    def status(self):
        self.agent.reference.raise_failure()
        if self.failure is not None:raise self.failure
        # A predicate may run before this monitor's capture callback. Read a
        # fresh public Bundle snapshot, never last cycle's callback result.
        return self.snapshot(self.agent.reference.input_tick+1)

    def arm(self):
        if self.armed:raise RuntimeError('cleanup/reset witness is already armed')
        self.armed=True

    def start(self):
        async def delivered(_):pass
        self.subscription=self.agent._execution.subscribe(on(RisingEdge(self.agent.dut.clock),
            capture=self.capture,delivery='lossless',capacity=64)(delivered).bind())
        return self

    async def aclose(self):
        if self.subscription is not None:
            self.agent._execution.reactor.cancel_subscription(self.subscription)
            if self.subscription.task is not None:
                with suppress(asyncio.CancelledError):await self.subscription.task
