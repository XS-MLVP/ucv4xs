"""suites.frontend.bpu.bpu.checker.bypass.history components."""

from suites.frontend.bpu.bpu.checker.abtb.checks_general import IntegratedChecks
from suites.frontend.bpu.bpu.checker.bypass.history_base import CombinedChecks
from suites.frontend.bpu.bpu.checker.bypass.hash import SramChecker


class NonzeroChecks(CombinedChecks):
    def __init__(self, case):
        self.bypass = SramChecker()
        IntegratedChecks.__init__(self, case)
        self.bypass.owner = self
