"""suites.frontend.bpu.mbtb.transaction.types components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MbtbLookup:
    pc: int


@dataclass(frozen=True, slots=True)
class MbtbEntry:
    valid: int
    taken: int
    target: int
    position: int
    branch_type: int
    ras_action: int


@dataclass(frozen=True, slots=True)
class MbtbPrediction:
    entries: tuple[MbtbEntry, ...]
    meta_entries: Any


@dataclass(frozen=True, slots=True)
class MbtbTraining:
    pc: int
    target: int
    taken: int
    position: int
    branch_type: int
    meta_entries: Any
    ras_action: int = 0
    mispredict: int = 1


@dataclass(frozen=True, slots=True)
class MbtbBranchFeedback:
    target: int
    taken: int
    position: int
    branch_type: int
    ras_action: int = 0
    mispredict: int = 0


@dataclass(frozen=True, slots=True)
class MbtbBatchTraining:
    """One FTQ feedback beat with multiple resolved branches."""

    pc: int
    meta_entries: Any
    branches: tuple[MbtbBranchFeedback, ...]
