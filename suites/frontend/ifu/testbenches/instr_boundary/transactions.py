"""Immutable slot identity and batch evidence; there is no hardware handshake."""
from dataclasses import dataclass

from suites.frontend.ifu.testbenches.instr_boundary.model.boundary import BoundaryInput
from suites.frontend.ifu.testbenches.instr_boundary.model.boundary import BoundaryOutput


@dataclass(frozen=True)
class Interface:
    slots: int = 32
    cross_block_slots: int = 31  # Slot31 is a proven pruned zero, not optional I/O.


@dataclass(frozen=True)
class CheckedBoundary:
    sequence: int
    sample_tick: int
    result: BoundaryOutput


@dataclass(frozen=True)
class BatchSummary:
    checked: int
    failed_indices: tuple[int, ...]


class BoundaryBatchMismatch(AssertionError):
    def __init__(self, summary, examples):
        self.summary = summary
        super().__init__(f'InstrBoundary batch: checked {summary.checked}, '
                         f'failed indices {summary.failed_indices}; '
                         + '; '.join(examples))


IDLE = BoundaryInput(32, 0, 31, 0, 0, 0, 0, 31)
