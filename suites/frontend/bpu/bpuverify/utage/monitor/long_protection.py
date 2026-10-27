"""Keep one public readonly snapshot to prove actual retained-cache departure."""
from copy import deepcopy
from bpuverify.utage.monitor.selective_protection import Monitor as SelectiveMonitor


class Monitor(SelectiveMonitor):
    def __init__(self,agent):
        super().__init__(agent);self.long_snapshot=None

    def capture(self,event):
        before=len(self.records);super().capture(event)
        if self.failure is not None or len(self.records)==before:return
        if '1' in self.records[-1]['versions']:
            try:
                observed=self.shadows[1].sample_at(event)
                self.long_snapshot=dict(tick=event.tick,cells=deepcopy(observed.value['cells']))
            except Exception as error:self.failure=error
