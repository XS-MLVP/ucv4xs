"""suites.frontend.bpu.ubtb.monitor.decode components."""

from __future__ import annotations
from suites.frontend.bpu.ubtb.transaction.types import UbtbPrediction
from suites.frontend.bpu.models.address import decode_pruned_pc


def _decode_prediction_sample(sample) -> UbtbPrediction:
    # The trimmed whole-chip output exposes `taken`, not a separate `valid`.
    # A disabled always-taken cache produces no prediction even on a hit.
    return UbtbPrediction(
        valid=int(sample.valid.as_int() and sample.enabled.as_int()),
        taken=sample.bits.taken.as_int(),
        target=decode_pruned_pc(sample.bits.target_addr.as_int()),
        position=sample.bits.cfiPosition.as_int(),
        branch_type=sample.bits.attribute.branchType.as_int(),
        ras_action=sample.bits.attribute.rasAction.as_int(),
    )
