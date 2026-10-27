"""bpuverify.utage.monitor.decode components."""

from __future__ import annotations
from typing import Any
from bpuverify.utage.transaction.types import UtagePrediction
from bpuverify.utage.bundle.values import _plain


def _decode(sample: Any) -> UtagePrediction:
    hits = tuple(_plain(sample.hits))
    takens = tuple(_plain(sample.takens))
    return UtagePrediction(
        hits[0], takens[0], _plain(sample.meta), hits, takens
    )
