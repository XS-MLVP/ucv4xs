"""Reusable MicroRAS expected results."""

from __future__ import annotations

from suites.frontend.bpu.testbenches.uras.transactions.types import UrasResult
from suites.frontend.bpu.testbenches.uras.model.addresses import call_target
from suites.frontend.bpu.testbenches.uras.model.vectors import CallVector


def pushed(vector: CallVector) -> UrasResult:
    return UrasResult(1, call_target(vector.start_pc, vector.position))
