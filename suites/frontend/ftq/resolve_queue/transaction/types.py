"""ResolveQueue typed transactions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResolveReport:
    """One branch resolution addressed to an FTQ entry."""

    index: int
    pc: int
    offset: int
    target: int
    taken: int = 1
    mispredict: int = 1
    branch_type: int = 1
    ras_action: int = 0
    flag: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.index < 64 or self.flag not in (0, 1):
            raise ValueError(f"illegal FTQ identity: {self.flag}:{self.index}")
        if not 0 <= self.pc < (1 << 50) or not 0 <= self.target < (1 << 50):
            raise ValueError("address outside the 50-bit virtual domain")
        if not 0 <= self.offset < 32:
            raise ValueError(f"offset {self.offset} outside 0..31")
        if self.taken not in (0, 1) or self.mispredict not in (0, 1):
            raise ValueError("taken/mispredict must be a single bit")
        if not 0 <= self.branch_type < 4 or not 0 <= self.ras_action < 4:
            raise ValueError("branch type/ras action outside the 2-bit domain")


@dataclass(frozen=True, slots=True)
class Branch:
    position: int
    target: int
    taken: int
    mispredict: int
    branch_type: int
    ras_action: int


@dataclass(frozen=True, slots=True)
class Training:
    """One owned ResolveEntry offered to the BPU training port."""

    index: int
    flag: int
    start_pc: int
    branches: tuple[Branch, ...]


@dataclass(frozen=True, slots=True)
class Ownership:
    """Internal circular-pointer state, used only for identity evidence."""

    enq: int
    deq: int
