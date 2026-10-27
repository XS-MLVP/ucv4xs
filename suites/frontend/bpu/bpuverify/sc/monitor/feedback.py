"""Opt-in complete defined feedback snapshots; no internal/VPI bindings."""
from toffee import Bundle

from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.monitor.cycle import CycleMonitor
from bpuverify.sc.bundle.values import _plain


class ScFeedbackMonitor(CycleMonitor):
    def __init__(self, ports):
        super().__init__(PortBinding(ports.training.clock, Bundle(
            valid=ports.training.valid, ready=ports.status.bits.train_ready,
            bits=ports.training.bits), 'sc.complete-feedback'), decoder=_plain)
