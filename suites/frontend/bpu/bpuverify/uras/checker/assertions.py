"""Reusable MicroRAS expected results."""

from __future__ import annotations

from bpuverify.uras.transaction.types import UrasResult
from bpuverify.uras.model.addresses import call_target
from bpuverify.uras.case.definitions import CallVector


def pushed(vector: CallVector) -> UrasResult:
    return UrasResult(1, call_target(vector.start_pc, vector.position))
