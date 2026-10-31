"""suites.frontend.bpu.ittage.monitor.decode components."""

from __future__ import annotations
from typing import Any
from suites.frontend.bpu.models.address import decode_pruned_pc
from suites.frontend.bpu.ittage.transaction.types import IttagePrediction
from suites.frontend.bpu.ittage.bundle.values import _plain


def _decode(sample: Any) -> IttagePrediction:
    meta = _plain(sample.meta)
    for field in ("providerTarget_addr", "altProviderTarget_addr"):
        meta[field] = decode_pruned_pc(meta[field])
    # Whole-chip DCE removed io.meta.valid. A slot is published exactly when
    # the parent consumes it at S3 with the global enable asserted.
    enabled = getattr(sample, 'enabled', None)
    consume = getattr(sample, 'consume', None)
    meta['valid'] = 1 if enabled is None or consume is None else int(
        bool(enabled.as_int() and consume.as_int()))
    return IttagePrediction(
        sample.hit.as_int(), decode_pruned_pc(sample.target.as_int()), meta
    )
