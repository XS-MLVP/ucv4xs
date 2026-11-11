"""MicroTAGE address folds and reset-derived fire/override/hold index tokens."""
from copy import deepcopy
from suites.frontend.bpu.testbenches.bpu.model.configuration import PHR_FOLDS


def read_indices(pc, normal_folds):
    return ((pc & 511) ^ normal_folds[0], (pc & 511) ^ normal_folds[1])


def concatenate(pc, bits):
    result = 0
    for bit in bits:
        result = (result << 1) | ((pc >> bit) & 1)
    return result


def full_tags(pc, folded):
    f=lambda length,width: folded[PHR_FOLDS.index((length,width))]
    low = (concatenate(pc, (10,8,6,4,2)) ^ f(5,5) ^ (f(5,4)<<1)) & 31
    long = (concatenate(pc, (14,12,10,8,6,4,2,0)) ^ f(9,8) ^ (f(9,7)<<1)) & 255
    return (concatenate(pc,(3,2,1))<<5)|low, long


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
