"""suites.frontend.bpu.utage.monitor.decode components."""

from __future__ import annotations
from typing import Any
from suites.frontend.bpu.utage.transaction.types import UtagePrediction
from suites.frontend.bpu.utage.bundle.values import _plain
from suites.frontend.bpu.models.folded_history import PHR_FOLD_LAYOUT


def dense_meta(meta, training_indices):
    """Restore the full configured folded-history ctx from sparse leaves.

    Whole-chip DCE keeps only the fold indices MicroTage consumes. Consumers
    of the training metadata (checkers and the independent model) reason in
    the full configured domain, so place the sparse rows back into their
    indexed positions and leave the removed indices at zero.
    """

    dense = dict(meta)
    rows = [dict(foldedHist=0) for _ in PHR_FOLD_LAYOUT]
    for index, row in zip(training_indices, meta['foldedPathHistForTrain_hist'],
                          strict=True):
        rows[index] = dict(row)
    dense['foldedPathHistForTrain_hist'] = tuple(rows)
    return dense


def _decode(sample: Any, training_indices: tuple[int, ...] | None = None) -> UtagePrediction:
    hits = tuple(_plain(sample.hits))
    takens = tuple(_plain(sample.takens))
    return UtagePrediction(
        hits[0], takens[0],
        dense_meta(_plain(sample.meta), training_indices)
        if training_indices is not None else _plain(sample.meta),
        hits, takens
    )
