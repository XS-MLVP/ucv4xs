"""Program comparisons and qualification; errors keep semantic expected/actual."""
from toffee import CheckContext, Scoreboard, ScoreboardMode


class UsefulnessChecks:
    def __init__(self, program, coverage):
        self.program, self.coverage = program, coverage
        self.board = Scoreboard('utage.protection-events')
        self.accepted = ()
        self.consumed = False

    def check(self, expected, actual, point):
        self.board.check(expected=expected, actual=actual, context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT, request=dict(point=point, state=self.program.state(), accepted=self.accepted)))

    def provider(self, prediction, expected, *, point):
        slot = prediction.meta['abtbResult'][0]
        self.check((1, self.program.table, expected.counter, expected.taken),
                   (prediction.hit, slot['tableId'], slot['takenCtr_value'], prediction.taken), point)

    def admissions(self, actual, expected, *, cycle_ticks):
        self.accepted = tuple(tick for tick, _ in actual)
        count = 1 if self.program.rule == 'initial-protection' else 2
        self.check((count, count), (len(expected), len(actual)), 'all required actual feedback inputs')
        self.check(expected, tuple(payload for _, payload in actual), 'complete original feedback accepted exactly once in order')
        if len(self.accepted) == 2:
            delta = self.accepted[1] - self.accepted[0]
            if self.program.mode == 'adjacent':
                self.check(cycle_ticks, delta, 'two actual adjacent feedback cycles')
            else:
                self.check(True, delta > cycle_ticks, 'serial feedback waits for its predecessor learning')
        self.coverage.record('reached', accepted=self.accepted)

    def consumers(self, target, neighbor):
        expected = self.program.initial if self.program.rule == 'initial-protection' else self.program.expected[-1]
        self.provider(target, expected, point='actual final target consumer')
        self.provider(neighbor, self.program.initial, point='actual learned neighbor consumer preserved')
        self.consumed = True

    def finish(self, frozen, current):
        self.check(True, bool(self.accepted), 'actual input qualification completed')
        self.check(True, self.consumed, 'target and learned neighbor independently consumed')
        self.check(frozen, current, 'all normally captured original source metadata remain immutable')
        self.coverage.record('checked', accepted=self.accepted)
