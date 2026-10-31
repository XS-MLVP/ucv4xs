"""Deterministic RAS call vectors and queue geometry."""

from __future__ import annotations
from suites.frontend.bpu.models.configuration import *

from dataclasses import dataclass


# The rebuilt DUT uses DefaultConfig (top/Configs.scala), not RasParameters'
# standalone defaults. Its committed stack has 16 entries and spec queue 32.
SPEC_QUEUE_SIZE = 32
STACK_COUNTER_MAX = 7


@dataclass(frozen=True, slots=True)
class CallVector:
    start_pc: int
    position: int


CALL_A = CallVector(0x8000_1004, 3)
CALL_B = CallVector(0x8000_2048, 7)
CALL_C = CallVector(0x8000_30AC, 5)


def unique_calls(count: int = SPEC_QUEUE_SIZE + 8) -> tuple[CallVector, ...]:
    return tuple(
        CallVector(0x9000_0000 + index * 0x20, index % 16)
        for index in range(count)
    )
