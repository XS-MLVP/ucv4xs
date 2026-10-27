"""Domain-cycle checking; no native phases, pin access, clock waits or subscriptions."""
from toffee import CheckContext, Scoreboard, ScoreboardMode

from .coverage import obligations
from .model import State


class ManagerChecker:
    def __init__(self, coverage=None):
        self.state = State()
        self.board = Scoreboard('manager.ring-reference')
        self.coverage = coverage
        self.initialized = False
        self.checked_cycles = 0

    def observe(self, cycle):
        if cycle.index != self.checked_cycles + 1:
            raise AssertionError('domain cycle missing, duplicated or reordered')
        before, after = cycle.before, cycle.after
        initial = State() if before.reset else self.state
        if not self.initialized and not before.reset:
            raise AssertionError('model must start from an observed reset')
        rules = obligations(initial, before)
        if self.coverage is not None:
            self.coverage.sample('reached', rules, cycle.index)
        following = initial.following(before.beat, reset=before.reset)
        if after.reset:
            following = State()
        for name, state, boundary in (('consumed', initial, before),
                                      ('newly_offered', following, after)):
            self.board.check(expected=state.decision(boundary.beat), actual=boundary.allocation,
                context=CheckContext(self.board.name, ScoreboardMode.DIRECT,
                    sequence_id=cycle.index,
                    request={'boundary': name, 'beat': boundary.beat, 'state': state}))
        # Actual outputs never supply expected occupancy; failed comparisons
        # leave the independent state unchanged and earn no checked credit.
        self.state, self.initialized = following, True
        self.checked_cycles += 1
        if self.coverage is not None:
            self.coverage.sample('checked', rules, cycle.index)

    def finish(self):
        if not self.checked_cycles:
            raise AssertionError('no checked domain cycles')
