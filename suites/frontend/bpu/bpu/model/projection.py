"""Reviewed public projections, separate from the autonomous semantic model.

An abstract model test may retain circular-pointer flags and perf/target echo.
The real whole-chip export has none of those fields. This is a declared ABI,
never a capability inferred from a missing sample or an AttributeError.
"""
from copy import deepcopy
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PipelineProjection:
    pointer_flag: bool
    prediction_target: bool
    perf_pc: bool
    early_source: bool
    base_strong: bool = True
    dense_training_folds: bool = True

    def history(self, checkpoint):
        result = deepcopy(checkpoint.metadata())
        if not self.pointer_flag:
            del result['phrPtr']['flag']
        return result


ABSTRACT_PIPELINE = PipelineProjection(True, True, True, True)
INTEGRATED_PIPELINE = PipelineProjection(False, False, False, False, False, False)
