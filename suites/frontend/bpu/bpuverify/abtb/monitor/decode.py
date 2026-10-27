"""bpuverify.abtb.monitor.decode components."""

from __future__ import annotations
from typing import Any
from bpuverify.abtb.transaction.types import AbtbEntry
from bpuverify.abtb.transaction.types import AbtbPrediction
from bpuverify.abtb.bundle.values import _plain


def _decode(sample: Any) -> AbtbPrediction:
    entries = tuple(
        AbtbEntry(
            valid=entry.valid.as_int(),
            taken=entry.bits.taken.as_int(),
            target=entry.bits.target_addr.as_int(),
            position=entry.bits.cfiPosition.as_int(),
            branch_type=entry.bits.attribute.branchType.as_int(),
            ras_action=entry.bits.attribute.rasAction.as_int(),
        )
        for entry in sample.entries
    )
    return AbtbPrediction(
        entries,
        _plain(sample.meta),
        _plain(sample.micro_tage),
    )
