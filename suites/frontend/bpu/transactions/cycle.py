"""suites.frontend.bpu.transactions.cycle components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CycleTransaction:
    values: Any
    cycles: int = 1
