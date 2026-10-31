"""The older original was cold, not invalid; logical ownership still survives."""
from suites.frontend.bpu.bpu.model.main_original_order import Program as CurrentProgram,ORDERS,PHASES,COUNTERS,RULES


class Program(CurrentProgram):
    def state(self):
        return dict(super().state(),older_origin='actual cold miss retained continuously',
            no_redirect_older_than_cold_after_publication=True)
