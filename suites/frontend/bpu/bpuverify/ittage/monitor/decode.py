"""bpuverify.ittage.monitor.decode components."""

from __future__ import annotations
from typing import Any
from bpuverify.common.model.address import decode_pruned_pc
from bpuverify.ittage.transaction.types import IttagePrediction
from bpuverify.ittage.bundle.values import _plain


def _decode(sample: Any) -> IttagePrediction:
    meta = _plain(sample.meta)
    for field in ("providerTarget_addr", "altProviderTarget_addr"):
        meta[field] = decode_pruned_pc(meta[field])
    return IttagePrediction(
        sample.hit.as_int(), decode_pruned_pc(sample.target.as_int()), meta
    )
