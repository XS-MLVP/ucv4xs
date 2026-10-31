"""suites.frontend.bpu.sc.transaction.types components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ScHistory:
    """Semantic upstream features, not preselected table indices or weights."""

    path: int = 0
    global_history: int = 0
    backward: int = 0
    loop: int = 0
    common_valid: bool = True

    def __post_init__(self):
        for name, width in (('path', 397), ('global_history', 16), ('backward', 8), ('loop', 8)):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value < 1 << width:
                raise ValueError(f'SC {name} history must fit {width} bits')
        if type(self.common_valid) is not bool:
            raise ValueError('SC common history validity must be boolean')


@dataclass(frozen=True, slots=True)
class ScBaseBranch:
    """One MainBTB/TAGE S2 slot; ``None`` denotes an invalid slot."""

    position: int
    tage_counter: int
    provider_valid: int = 1
    mbtb_valid: int = 1
    branch_type: int = 1


@dataclass(frozen=True, slots=True)
class ScLookup:
    pc: int
    position: int
    tage_counter: int
    provider_valid: int = 1
    mbtb_valid: int = 1
    branch_type: int = 1
    branches: tuple[ScBaseBranch | None, ...] | None = None
    history: ScHistory = ScHistory()


@dataclass(frozen=True, slots=True)
class ScPrediction:
    taken: int
    used: int
    meta: Any
    takens: tuple[int, ...] = ()
    useds: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ScTraining:
    pc: int
    position: int
    actual_taken: int
    meta: Any
    mbtb_hit: int = 1
    branch_type: int = 1
    history: ScHistory = ScHistory()


@dataclass(frozen=True, slots=True)
class ScBranchFeedback:
    """One resolved branch and its slot in the preceding MainBTB prediction."""

    position: int
    actual_taken: int
    prediction_slot: int
    mbtb_hit: int = 1
    branch_type: int = 1


@dataclass(frozen=True, slots=True)
class ScBatchTraining:
    """One FTQ feedback beat; ``None`` leaves a resolved-branch slot invalid."""

    pc: int
    meta: Any
    branches: tuple[ScBranchFeedback | None, ...]
    history: ScHistory = ScHistory()
