"""bpuverify.tage.monitor.decode components."""

from __future__ import annotations
from typing import Any
from bpuverify.tage.transaction.types import TagePrediction
from bpuverify.tage.bundle.values import _plain


def _decode(sample: Any) -> TagePrediction:
    valids = tuple(entry.valid.as_int() for entry in sample.taken_vec)
    takens = tuple(entry.bits.as_int() for entry in sample.taken_vec)
    metas = tuple(_plain(entry) for entry in sample.meta_vec)
    provider_counter_valids = tuple(
        entry.as_int() for entry in sample.provider_counter_valid_vec
    )
    return TagePrediction(
        valids[0], takens[0], metas[0], provider_counter_valids[0],
        valids, takens, metas, provider_counter_valids,
    )
