"""Bounded query windows and learning-event snapshots, never cycle exports."""
from bpuverify.utage.monitor.shadow import UtageShadowMonitor
from bpuverify.utage.monitor.read_lifetime import ReadLifetimeMonitor


class Monitor(ReadLifetimeMonitor):
    def __init__(self,agent,table):
        super().__init__(agent)
        self.table=table
        self.shadow=UtageShadowMonitor(agent,table=table)
        self.versions=[]

    def capture(self,event):
        super().capture(event)
        if self.failure is not None or not self.recent or self.recent[-1]['tick']!=event.tick:return
        try:
            row=self.recent[-1]
            if row['effects'] and any(table==self.table for table,*_ in row['effects']):
                native=self.shadow.sample_at(event).value
                depth=len(native['cells'])
                self.versions.append(dict(tick=event.tick,next=native['enq'],
                    new_cell=native['cells'][(native['enq']-1)%depth],
                    logical_sequence=self.agent.reference.model.updates[self.table].sequence-1,
                    depth=depth))
        except Exception as error:self.failure=error
