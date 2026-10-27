"""Reset-derived MicroTAGE index tokens with fire/override/hold, not fixed tick offsets."""
from copy import deepcopy
from bpuverify.bpu.case.bypass.history_plan import read_indices

class IndexPipeline:
    def __init__(self):
        self.a1=None
        self.a2=self.a3=dict(indices=(0,0),pc=None,folds=None,source_tick=None)
    def advance(self, *, reset, enable, fire0, fire2, s2, s3, pc, normal_folds, tick):
        a1,a2,a3=deepcopy((self.a1,self.a2,self.a3))
        active=bool(enable and fire0)
        # a1 is RegEnable, not RegInit: reset does not suppress a0-fire capture.
        if active:
            self.a1=dict(indices=read_indices(pc,normal_folds),pc=pc,
                folds=tuple(normal_folds),source_tick=tick)
        if reset:
            self.a2=dict(indices=(0,0),pc=None,folds=None,source_tick=None)
            self.a3=deepcopy(self.a2)
        else:
            if active:
                self.a2=a3 if s3 else a2 if s2 else a1
            if enable and fire2:
                self.a3=a2
