"""suites.frontend.bpu.bpu.checker.bypass.aging_base components."""

from suites.frontend.bpu.bpu.checker.abtb.checks_aging import IntegratedChecks
from suites.frontend.bpu.bpu.checker.bypass.checker import BypassChecker


class CombinedChecks(IntegratedChecks):
    def __init__(self, case):
        self.bypass = BypassChecker()
        super().__init__(case)

    def raise_failure(self):
        super().raise_failure()
        self.bypass.raise_failure()
