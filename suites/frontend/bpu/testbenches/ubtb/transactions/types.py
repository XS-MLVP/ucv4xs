"""MicroBTB transactions use aligned 50-bit unguarded byte PC/target values.

Only standalone driver/monitor adapters convert to/from PrunedAddr halfwords.
The integrated BPU keeps its own halfword API and converts once for model reuse.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BranchTraining:
    pc: int
    target: int
    taken: int
    position: int
    branch_type: int
    ras_action: int = 0
    mispredict: int = 1


@dataclass(frozen=True, slots=True)
class UbtbBranchFeedback:
    """One resolve branch; addresses keep MicroBTB's existing byte units."""

    target: int
    taken: int
    position: int
    branch_type: int
    ras_action: int = 0
    mispredict: int = 0
    valid: int = 1


@dataclass(frozen=True, slots=True)
class UbtbBatchTraining:
    """An FTQ resolve beat; None denotes a masked/unoccupied branch slot."""

    pc: int
    branches: tuple[UbtbBranchFeedback | None, ...]
    fire: int = 1


@dataclass(frozen=True, slots=True)
class UbtbPrediction:
    valid: int
    taken: int
    target: int
    position: int
    branch_type: int
    ras_action: int = 0


@dataclass(frozen=True, slots=True)
class PredictRequest:
    pc: int
