"""Passive input ownership only; no predictor, weights or reference outputs.

The existing port adapter owns physical launch/sample timing. This observer
just carries actual PC/history through the two declared lookup stages and
attaches the actual base branches at selection. Nothing is learned here.
"""
from collections import OrderedDict

from bpuverify.sc.monitor.semantic import ScSemanticMonitor


class InputWitnessLedger:
    def __init__(self):
        self.read=self.selection=None
        self.records=OrderedDict()
        self.failure=None

    def capture_input(self,event,events):
        if self.failure is not None:return
        try:
            if events.reset:
                self.read=self.selection=None
                self.records.clear()
                return
            if not events.ready:return
            old_read,old_selection=self.read,self.selection
            if events.select:
                if old_selection is None:
                    raise AssertionError('selected SC query has no observed original PC/history')
                pc,context=old_selection
                self.records[event.tick+1]=dict(pc=pc,enabled=events.enabled,
                    history=(context.path,context.global_history,context.backward,context.loop,
                             context.common_valid),branches=events.branches)
                while len(self.records)>64:self.records.popitem(last=False)
            if events.advance:self.selection=old_read
            if events.pc is not None:self.read=(events.pc,events.context)
        except Exception as error:
            self.failure=error

    def capture_output(self,event,actual):
        # The shared port adapter calls this method. Deliberately ignore all
        # actual outputs: they must never define an input witness or golden.
        pass

    def input_for(self,transfer):
        if self.failure is not None:raise self.failure
        tick=transfer.completed_event.tick
        if tick not in self.records:
            raise AssertionError(f'completed SC query at tick {tick} has no original observed inputs')
        return self.records[tick]


class EligibilityInputMonitor(InputWitnessLedger):
    def __init__(self,agent):
        super().__init__()
        self.monitor=ScSemanticMonitor(agent.dut,agent.ports)

    def start(self,execution):
        self.monitor.start(execution,self)
        return self

    async def aclose(self):
        await self.monitor.aclose()
        if self.failure is not None:raise self.failure
