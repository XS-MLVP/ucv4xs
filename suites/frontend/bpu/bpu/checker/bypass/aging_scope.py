"""suites.frontend.bpu.bpu.checker.bypass.aging_scope components."""

from suites.frontend.bpu.bpu.checker.abtb.checks_aging import IntegratedChecks
from suites.frontend.bpu.bpu.checker.bypass.aging_base import CombinedChecks
from suites.frontend.bpu.bpu.checker.bypass.policy import SramChecker


class NonzeroChecks(CombinedChecks):
    def __init__(self, case):
        self.bypass = SramChecker()
        IntegratedChecks.__init__(self, case)
        self.bypass.owner = self
