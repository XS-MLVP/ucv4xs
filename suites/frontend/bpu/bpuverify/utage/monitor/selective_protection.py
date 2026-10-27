"""Capture learning occurrences including base-agreement writes without useful effects."""
from bpuverify.utage.monitor.shadow import UtageShadowMonitor
from bpuverify.utage.monitor.read_lifetime import ReadLifetimeMonitor


class Monitor(ReadLifetimeMonitor):
    def __init__(self,agent):
        super().__init__(agent)
        self.shadows=tuple(UtageShadowMonitor(agent,table=table) for table in (0,1))
        self.sequences=tuple(cache.sequence for cache in agent.reference.model.updates)
        self.records=[]

    def capture(self,event):
        super().capture(event)
        if self.failure is not None or self.agent.reference.failure is not None:return
        try:
            row=self.recent[-1]
            if row['tick']!=event.tick:raise AssertionError('one current semantic boundary required')
            current=tuple(cache.sequence for cache in self.agent.reference.model.updates)
            versions={}
            for table,(old,new) in enumerate(zip(self.sequences,current,strict=True)):
                if new==old:continue
                if new!=old+1:raise AssertionError('one retained version per table per learning boundary')
                native=self.shadows[table].sample_at(event).value
                depth=len(native['cells'])
                versions[str(table)]=dict(sequence=new-1,next=native['enq'],depth=depth,
                    new_cell=native['cells'][(native['enq']-1)%depth])
            self.sequences=current
            changes=tuple(sorted(row['native'].get('changes',())))
            aged=self.agent.reference.model.aged
            if versions or changes or aged:
                self.records.append(dict(tick=event.tick,versions=versions,changes=changes,aged=aged,
                    model_useful_effects=row['effects']))
        except Exception as error:self.failure=error
