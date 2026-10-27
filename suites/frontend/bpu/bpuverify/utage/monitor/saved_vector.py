"""Retain only the bounded compound protocol, not a cycle trace export."""
from collections import deque
from bpuverify.utage.monitor.dual_source import Monitor as LearningMonitor


class Monitor(LearningMonitor):
    def __init__(self,agent):
        super().__init__(agent)
        self.window=None

    def arm_window(self):
        if self.window is not None: raise ValueError('one bounded recovery occurrence required')
        self.window=deque(maxlen=32)

    def capture(self,event):
        super().capture(event)
        if self.failure is None and self.window is not None and self.recent:
            self.window.append(self.recent[-1])

    def recovery_rows(self,stage):
        if self.failure is not None: raise self.failure
        rows=tuple(self.window or ())
        selected=[i for i,row in enumerate(rows) if row['events'].override==stage]
        if len(selected)!=1 or selected[0]<3:
            raise AssertionError(dict(point='one complete actual four-input recovery',stage=stage,matches=selected))
        last=selected[0]
        return rows[last-3:last+1]
