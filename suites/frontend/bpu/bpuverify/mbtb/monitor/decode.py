"""bpuverify.mbtb.monitor.decode components."""

from __future__ import annotations
from typing import Any
from bpuverify.mbtb.transaction.types import MbtbEntry
from bpuverify.mbtb.transaction.types import MbtbPrediction
from bpuverify.mbtb.bundle.values import _plain


def _decode(sample: Any) -> MbtbPrediction:
    entries = tuple(
        MbtbEntry(
            valid=entry.valid.as_int(),
            taken=entry.bits.taken.as_int(),
            target=entry.bits.target_addr.as_int(),
            position=entry.bits.cfiPosition.as_int(),
            branch_type=entry.bits.attribute.branchType.as_int(),
            ras_action=entry.bits.attribute.rasAction.as_int(),
        )
        for entry in sample.entries
    )
    return MbtbPrediction(entries, _plain(sample.meta_entries))
