"""bpuverify.ubtb.monitor.decode components."""

from __future__ import annotations
from bpuverify.ubtb.transaction.types import UbtbPrediction
from bpuverify.common.model.address import decode_pruned_pc


def _decode_prediction_sample(sample) -> UbtbPrediction:
    return UbtbPrediction(
        valid=sample.valid.as_int(),
        taken=sample.bits.taken.as_int(),
        target=decode_pruned_pc(sample.bits.target_addr.as_int()),
        position=sample.bits.cfiPosition.as_int(),
        branch_type=sample.bits.attribute.branchType.as_int(),
        ras_action=sample.bits.attribute.rasAction.as_int(),
    )
