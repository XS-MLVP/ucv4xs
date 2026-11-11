"""CommitQueue typed transactions."""

from __future__ import annotations

from dataclasses import dataclass

from suites.frontend.ftq.testbenches.ftq.model import CallRet


WIDTH = 8
EMPTY = (None,) * WIDTH


def lane_rows(rows):
    rows = tuple(rows)
    if len(rows) != WIDTH or any(row is not None and type(row) is not CallRet for row in rows):
        raise ValueError('CommitQueue requires eight validated CallRet transactions or None')
    return rows


@dataclass(frozen=True, slots=True)
class Input:
    slot: int
    rows: tuple[CallRet | None, ...] = EMPTY
    reset: bool = False

    def __post_init__(self):
        if type(self.slot) is not int or self.slot < 0 or type(self.reset) is not bool:
            raise ValueError('CommitQueue needs a nonnegative input slot and boolean reset')
        object.__setattr__(self, 'rows', lane_rows(self.rows))
        if self.reset and any(self.rows):
            raise ValueError('reset slots cannot offer commit actions')


@dataclass(frozen=True, slots=True)
class Snapshot:
    reset: bool
    rows: tuple[CallRet | None, ...]
    head: CallRet | None


@dataclass(frozen=True, slots=True)
class OwnedAction:
    # Environment identity, never an alleged hardware tag. Equal payloads in
    # different lanes/cycles remain distinct ordered obligations.
    uid: tuple[int, int, int]  # epoch, input slot, lane
    value: CallRet
    accepted_tick: int


@dataclass(frozen=True, slots=True)
class Terminal:
    action: OwnedAction
    status: str
    tick: int


__all__ = ['CallRet', 'Input', 'Snapshot', 'OwnedAction', 'Terminal', 'EMPTY', 'WIDTH', 'lane_rows']
