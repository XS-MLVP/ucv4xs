"""Keep bounded witnesses of an already independently compared identity reset."""
from copy import deepcopy

from bpuverify.bpu.checker.ahead_working_set import AheadWorkingSetChecks


class Checks(AheadWorkingSetChecks):
    def __init__(self, program, coverage):
        super().__init__(program, coverage)
        self.strong_replacement_examples = []

    def checked(self, tick, *candidates):
        super().checked(tick, *candidates)
        for service in self.pending_services:
            old = self._before_memory.get(service['key'])
            service['old_tag'] = None if old is None else old.tag

    def candidates(self, row, events, cycle, model, phase, previous):
        pending = deepcopy(self.pending_services)
        result = super().candidates(row, events, cycle, model, phase, previous)
        # super() first compares every actual counter and recency cell. These
        # observations are evidence only; they never feed the reference state.
        counters = row['observed']['ahead_working_state']['counters']
        for service in pending:
            if service['old_counter'] != 3 or len(self.strong_replacement_examples) >= 12:
                continue
            bank, index, way = service['key']
            self.strong_replacement_examples.append(dict(
                service, confirmed_tick=self.pipeline.current_event.tick,
                observed_new_identity_confidence=counters[(bank * 64 + index) * 4 + way],
                all_counter_and_recency_state_compared=True))
        return result

    def summary(self):
        return dict(super().summary(), strong_replacement_examples=deepcopy(self.strong_replacement_examples),
                    Main_direction_proposal_comparison_preserved=True)
