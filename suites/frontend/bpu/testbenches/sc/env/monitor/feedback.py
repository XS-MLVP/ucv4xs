"""Opt-in complete defined feedback snapshots; no internal/VPI bindings."""
from toffee import Bundle

from suites.frontend.bpu.testbenches.shared.env.bundle.bindings import PortBinding
from suites.frontend.bpu.testbenches.shared.env.monitor.cycle import CycleMonitor
from suites.frontend.bpu.testbenches.sc.env.bundle.values import _plain


class ScFeedbackMonitor(CycleMonitor):
    def __init__(self, ports):
        super().__init__(PortBinding(ports.training.clock, Bundle(
            valid=ports.training.valid, ready=ports.status.bits.train_ready,
            bits=ports.training.bits), 'sc.complete-feedback'), decoder=_plain)
