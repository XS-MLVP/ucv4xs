"""The older original was cold, not invalid; logical ownership still survives."""
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import Program as CurrentProgram
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import ORDERS
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import PHASES
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import COUNTERS
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import RULES


class Program(CurrentProgram):
    def state(self):
        return dict(super().state(),older_origin='actual cold miss retained continuously',
            no_redirect_older_than_cold_after_publication=True)
