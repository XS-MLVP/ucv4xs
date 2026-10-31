"""Bind only the actual optimized top's public ports."""
from __future__ import annotations

from .types import Observation


class Ports:
    def __init__(self, dut):
        self.dut = dut
        self.confirm = tuple(getattr(dut, f"io_doAllocate_{i}") for i in range(3))
        self.slots = tuple(getattr(dut, f"io_allocateSlot_{i}") for i in range(3))
        self.can = tuple(getattr(dut, f"io_canAllocate_{i}") for i in range(3)) if hasattr(dut, "io_canAllocate_0") else None
        self.occupied = getattr(dut, "io_validCount", None)
        self.empty = getattr(dut, "io_empty", None)

    def sample(self, event):
        return Observation(bool(self.dut.reset.U()),
                           sum(s.U() << i for i, s in enumerate(self.confirm)),
                           self.dut.io_free.U(), tuple(s.U() for s in self.slots),
                           tuple(bool(s.U()) for s in self.can) if self.can else None,
                           self.occupied.U() if self.occupied is not None else None,
                           bool(self.empty.U()) if self.empty is not None else None)
