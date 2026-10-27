"""bpuverify.tage.transaction.types components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TageBaseBranch:
    """One MainBTB prediction slot; ``None`` denotes an invalid slot."""

    position: int
    taken: int
    base_conf: int = 0
    branch_type: int = 1


@dataclass(frozen=True, slots=True)
class TageLookup:
    pc: int
    position: int
    base_taken: int
    base_conf: int = 0
    branch_type: int = 1
    branches: tuple[TageBaseBranch | None, ...] | None = None
    history: int = 0


@dataclass(frozen=True, slots=True)
class TagePrediction:
    valid: int
    taken: int
    meta: Any
    provider_counter_valid: int
    valids: tuple[int, ...] = ()
    takens: tuple[int, ...] = ()
    metas: tuple[Any, ...] = ()
    provider_counter_valids: tuple[int, ...] = ()
    table_states: tuple[tuple[Any, ...], ...] = ()
    alternate_counters: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class TageTraining:
    pc: int
    position: int
    actual_taken: int
    base_taken: int
    meta: Any
    mispredict: int = 1
    base_counter_value: int | None = None
    branch_type: int = 1
    mbtb_hit: int = 1
    history: int = 0


@dataclass(frozen=True, slots=True)
class TageBranchFeedback:
    """One resolved branch and the prediction metadata for its BTB entry."""

    position: int
    actual_taken: int
    base_taken: int
    meta: Any
    mispredict: int = 0
    base_counter_value: int | None = None
    branch_type: int = 1
    valid: int = 1
    mbtb_hit: int = 1


@dataclass(frozen=True, slots=True)
class TageBatchTraining:
    """One FTQ feedback beat; None leaves a branch slot unoccupied."""

    pc: int
    branches: tuple[TageBranchFeedback | None, ...]
    history: int = 0
