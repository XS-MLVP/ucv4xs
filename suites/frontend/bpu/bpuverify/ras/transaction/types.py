"""bpuverify.ras.transaction.types components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RasState:
    top: int
    redirect_meta: Any
    commit_meta: Any


@dataclass(frozen=True, slots=True)
class RasOperation:
    """One logical speculative operation; the agent owns launch timing."""

    action: int
    start_pc: int = 0
    position: int = 0
    enable: int = 1
    branch_type: int | None = None

    def __post_init__(self) -> None:
        for name, value, bound in (
            ("action", self.action, 4), ("start_pc", self.start_pc, 1 << 51),
            ("position", self.position, 16), ("enable", self.enable, 2),
        ):
            if type(value) is not int or not 0 <= value < bound:
                raise ValueError(f"RAS {name} must be an unsigned integer below {bound}")
        if self.branch_type is not None and (
            type(self.branch_type) is not int or not 0 <= self.branch_type < 4
        ):
            raise ValueError("RAS branch_type must be an unsigned two-bit integer")

    def frame(self) -> dict[str, int]:
        return dict(
            enable=self.enable, action=self.action,
            branch_type=self.branch_type if self.branch_type is not None else (3 if self.action in (1, 3) else 2),
            position=self.position, start_pc=self.start_pc,
        )
