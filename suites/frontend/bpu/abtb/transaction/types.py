"""suites.frontend.bpu.abtb.transaction.types components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AbtbLookup:
    pc: int
    path_hash: int = 0
    override: str | None = None
    override_pc: int | None = None
    redirect: bool = False


@dataclass(frozen=True, slots=True)
class AbtbEntry:
    valid: int
    taken: int
    target: int
    position: int
    branch_type: int
    ras_action: int


@dataclass(frozen=True, slots=True)
class AbtbPrediction:
    """S2 prediction snapshot; ``micro_tage.result`` is S2, fastPositions is live S1."""

    entries: tuple[AbtbEntry, ...]
    meta: Any
    micro_tage: Any = None


@dataclass(frozen=True, slots=True)
class AbtbTraining:
    pc: int
    target: int
    taken: int
    position: int
    branch_type: int
    meta: Any
    ras_action: int = 0
    mispredict: int = 1
