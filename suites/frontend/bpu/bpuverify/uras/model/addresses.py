"""bpuverify.uras.model.addresses components."""

from __future__ import annotations
from bpuverify.common.model.configuration import *


def call_target(start_pc: int, position: int) -> int:
    # GuardedPc.addr omits architectural bit 0.  Fetch-block 32-byte
    # alignment therefore clears four bits in the picker-visible domain.
    return (start_pc // ALIGN_HALFWORDS * ALIGN_HALFWORDS) + position + 1
