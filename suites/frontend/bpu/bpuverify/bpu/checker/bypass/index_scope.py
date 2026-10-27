"""bpuverify.bpu.checker.bypass.index_scope components."""

from bpuverify.bpu.checker.abtb.checks_general import IntegratedChecks
from bpuverify.bpu.checker.bypass.history_base import CombinedChecks
from bpuverify.bpu.checker.bypass.index import SramChecker


class NonzeroChecks(CombinedChecks):
    def __init__(self, case):
        self.bypass = SramChecker()
        IntegratedChecks.__init__(self, case)
        self.bypass.owner = self
