"""bpuverify.bpu.checker.bypass.aging_scope components."""

from bpuverify.bpu.checker.abtb.checks_aging import IntegratedChecks
from bpuverify.bpu.checker.bypass.aging_base import CombinedChecks
from bpuverify.bpu.checker.bypass.policy import SramChecker


class NonzeroChecks(CombinedChecks):
    def __init__(self, case):
        self.bypass = SramChecker()
        IntegratedChecks.__init__(self, case)
        self.bypass.owner = self
