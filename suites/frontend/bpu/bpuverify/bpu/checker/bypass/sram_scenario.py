"""bpuverify.bpu.checker.bypass.sram_scenario components."""

from bpuverify.bpu.checker.abtb.checks_zero import IntegratedChecks
from bpuverify.bpu.checker.bypass.natural import CombinedChecks
from bpuverify.bpu.checker.bypass.sram_reset import SramChecker


class SramChecks(CombinedChecks):
    def __init__(self, case):
        self.bypass = SramChecker()
        IntegratedChecks.__init__(self, case)
