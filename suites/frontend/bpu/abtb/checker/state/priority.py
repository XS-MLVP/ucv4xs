"""Qualify SAME-CYCLE, SAME-CELL reset/train collisions from real observed ports."""
from copy import deepcopy
from suites.frontend.bpu.abtb.checker.state.counter import CounterChecker
from suites.frontend.bpu.abtb.model.state.counter import index


class PriorityChecker(CounterChecker):
    def __init__(self, *, scope, coverage):
        super().__init__(scope=scope, coverage=coverage)
        self.accepted_events = []
        self.collision_candidates = []
        self.collisions = []

    def observe(self, observation):
        row = observation.value
        candidates = []
        tx = self.reference.pending1
        if tx is not None and not row['reset']:
            for bank, write in enumerate(row['writes']):
                if not (write['valid'] and write['reset_counter']
                        and tx['meta']['bankMask'] & (1 << bank)
                        and tx['meta']['setIdx'] == write['set_index']):
                    continue
                way = write['way']
                entry = tx['meta']['entries'][way]
                if not entry['hit'] or entry['attribute']['branchType'] != 1:
                    continue
                old = self.reference.cells[index(bank, write['set_index'], way)]
                operation = ('dec' if not tx['taken'] or entry['position'] < tx['position']
                             else 'inc' if entry['position'] == tx['position'] else None)
                if operation is not None:
                    ordinary = max(0, old - 1) if operation == 'dec' else min(3, old + 1)
                    candidates.append(dict(tick=observation.event.tick, bank=bank,
                        set_index=write['set_index'], way=way, before=old, operation=operation,
                        without_reset=ordinary, expected=2, discriminating=ordinary != 2,
                        training=deepcopy(tx), write=deepcopy(write)))
        old_accepted = self.accepted
        super().observe(observation)
        if self.accepted != old_accepted:
            self.accepted_events.append(observation.event)
        for candidate in self.collision_candidates:
            self.check(2, row['cells'][index(candidate['bank'], candidate['set_index'], candidate['way'])],
                       phase='same-cell-reset-dominates-training', collision=candidate)
            self.collisions.append(dict(candidate, checked_tick=observation.event.tick,
                                        actual=row['cells'][index(candidate['bank'], candidate['set_index'], candidate['way'])]))
        self.collision_candidates = candidates
