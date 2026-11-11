"""CommitQueue monitor decoding."""

from __future__ import annotations

from collections import deque

from toffee import SamplingMonitor

from suites.frontend.ftq.testbenches.shared.env.ports import Pins
from suites.frontend.ftq.testbenches.shared.env.harness import Dut
from suites.frontend.ftq.testbenches.ftq.model import CallRet


def decode_training(dut: Dut, train: Pins) -> CallRet | None:
    if not train.b("valid"):
        return None
    return CallRet(ptr=train.u("ptr"), ras=train.u("ras"))


class CommitMonitor(SamplingMonitor):
    """One immutable full-channel snapshot per requested framework event.

    history/latest are checked, non-consuming views, not a second subscription.
    sample_fn is the explicit decoder injection seam used only by selftests.
    """
    def __init__(self, trigger, dut, ports):
        self.sample_fn = lambda d: decode_training(d, ports.train)
        self.latest = None
        self.history = deque(maxlen=256)
        super().__init__(trigger, capture=lambda _: ports.capture(dut, self.sample_fn(dut)),
                         delivery='lossless', capacity=8)

    def record(self, value):
        self.latest = value
        if value is not None:
            self.history.append(value)
