"""bpuverify.bpu.checker.bypass.history_base components."""

from bpuverify.bpu.checker.abtb.checks_general import IntegratedChecks
from bpuverify.bpu.checker.bypass.checker import BypassChecker


class CombinedChecks(IntegratedChecks):
    def __init__(self, case):
        self.bypass = BypassChecker()
        super().__init__(case)

    def raise_failure(self):
        super().raise_failure()
        self.bypass.raise_failure()
