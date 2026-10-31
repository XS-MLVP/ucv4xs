"""CommitQueue monitor decoding."""

from __future__ import annotations

from suites.frontend.ftq.ports import Pins
from suites.frontend.ftq.harness import Dut
from suites.frontend.ftq.oracle import CallRet


def decode_training(dut: Dut, train: Pins) -> CallRet | None:
    if not train.b("valid"):
        return None
    return CallRet(ptr=train.u("ptr"), ras=train.u("ras"))
