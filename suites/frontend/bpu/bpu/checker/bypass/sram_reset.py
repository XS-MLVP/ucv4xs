"""Retain v5 comparisons, using actual committed reset at the boundary."""
from copy import deepcopy

from suites.frontend.bpu.bpu.checker.bypass import sram_base as _v5


class SramChecker(_v5.SramChecker):
    def __init__(self):
        super().__init__()
        self.reset_cache_divergences = []
        self.failed_frame = None

    def observe(self, phase, observation):
        row, event = observation.value, observation.event
        if row['requested_reset'] != row['reset']:
            self.reset_cache_divergences.append(dict(tick=event.tick, phase=phase,
                requested=row['requested_reset'], committed=row['reset']))
        try:
            for table, actual in enumerate(row['sram']):
                self.check_sram(row['reset'], actual['reset'], event, table=table,
                    point='both table reset wires equal committed RTL reset')
            super().observe(phase, observation)
        except BaseException:
            self.failed_frame = dict(phase=phase, tick=event.tick, value=deepcopy(row))
            raise

    def finish(self):
        result = super().finish()
        result.update(reset_taken_from_committed_RTL_wire_not_pending_input_cache=True,
            reset_cache_divergences=self.reset_cache_divergences)
        return result
