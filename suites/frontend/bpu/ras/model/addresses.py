"""suites.frontend.bpu.ras.model.addresses components."""

from __future__ import annotations
from suites.frontend.bpu.models.configuration import *


def return_addr(start_pc: int, position: int) -> int:
    return ((start_pc // ALIGN_BYTES * ALIGN_BYTES) + (position << 1) + 2) >> 1
