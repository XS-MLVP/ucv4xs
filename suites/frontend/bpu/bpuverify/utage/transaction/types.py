"""bpuverify.utage.transaction.types components."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class UtageBaseBranch:
    """One AheadBTB slot; ``None`` in a lookup denotes an invalid slot."""

    position: int
    taken: int
    branch_type: int = 1
    strong_bias: int = 0


@dataclass(frozen=True, slots=True)
class UtageLookup:
    """Logical tag/CFI request, with an optional older A0 index context.

    ``pc`` and ``folded_history`` describe A1 tag comparison and subsequent
    training. A real ahead pipeline can index with a different PC/history;
    omitting the two keyword-only fields preserves same-context lookups.
    """
    pc: int
    position: int
    base_taken: int
    override: str | None = None
    override_pc: int | None = None
    folded_history: int = 0
    branches: tuple[UtageBaseBranch | None, ...] | None = None
    index_pc: int | None = field(default=None, kw_only=True)
    index_history: int | None = field(default=None, kw_only=True)
    redirect: bool = field(default=False, kw_only=True)

    def __post_init__(self):
        if self.index_pc is not None and (type(self.index_pc) is not int or not 0 <= self.index_pc < 1 << 49):
            raise ValueError('index_pc must be an unsigned 49-bit halfword address')
        if self.index_history is not None and (type(self.index_history) is not int
                                               or not 0 <= self.index_history < 1 << 532):
            raise ValueError('index_history must fit the 532-bit configured PHR')

    @property
    def read_pc(self):
        return self.pc if self.index_pc is None else self.index_pc

    @property
    def read_history(self):
        return self.folded_history if self.index_history is None else self.index_history


@dataclass(frozen=True, slots=True)
class UtagePrediction:
    hit: int
    taken: int
    meta: Any
    hits: tuple[int, ...] = ()
    takens: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class UtageTraining:
    pc: int
    position: int
    actual_taken: int
    meta: Any
    mispredict: int = 1
    branch_type: int = 1
    ras_action: int = 0
