"""PredChecker's complete frame and idle policy over the shared slot scheduler."""
from suites.frontend.ifu.testbenches.shared.env.driver.explicit_slots import ExplicitSlotDriver

from suites.frontend.ifu.testbenches.pred_checker.transactions import Frame


class PredCheckerDriver(ExplicitSlotDriver):
    def __init__(self, clock, ports):
        super().__init__(clock, ports.bits, idle=ports.encode(Frame()), encoder=ports.encode,
                         name='ifu.pred_checker.inputs')
