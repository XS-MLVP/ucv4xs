"""bpuverify.ittage.transaction.types components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class IttageLookup:
    """A lookup PC in bytes, not the encoded ``Pc.addr`` halfword field."""

    pc: int
    folded_history: int = 0


@dataclass(frozen=True, slots=True)
class IttagePrediction:
    """Target and both provider-target metadata fields are byte addresses."""

    hit: int
    target: int
    meta: Any


@dataclass(frozen=True, slots=True)
class IttageTraining:
    """Byte-address feedback using XiangShan's branch/RAS attributes."""

    pc: int
    position: int
    target: int
    meta: Any
    mispredict: int
    folded_history: int = 0
    branch_index: int = 0
    taken: int = 1
    branch_type: int = 3
    ras_action: int = 0
    valid: int = 1


@dataclass(frozen=True, slots=True)
class IttageBranchFeedback:
    position: int
    target: int
    taken: int
    mispredict: int = 0
    branch_type: int = 3
    ras_action: int = 0
    valid: int = 1


@dataclass(frozen=True, slots=True)
class IttageBatchTraining:
    """One FTQ feedback beat; None denotes an unoccupied branch slot."""

    pc: int
    meta: Any
    branches: tuple[IttageBranchFeedback | None, ...]
    folded_history: int = 0
