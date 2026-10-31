"""suites.frontend.bpu.bpu.checker.bypass.force components."""

from suites.frontend.bpu.bpu.checker.abtb.checks_zero import IntegratedChecks
from suites.frontend.bpu.bpu.checker.bypass.natural import CombinedChecks
from suites.frontend.bpu.bpu.checker.bypass.sram import SramChecker


class SramChecks(CombinedChecks):
    def __init__(self, case):
        self.bypass = SramChecker()
        IntegratedChecks.__init__(self, case)
