"""Closed-form branch learning across disable, with no sampled-state seeds."""
from dataclasses import dataclass, asdict

from bpuverify.utage.model.semantic import Context, indices
from bpuverify.utage.model.usefulness_events import (
    ProtectionState, PC, POSITION, HISTORY, NEIGHBOR_HISTORY, UsefulnessProgram)

PHASES = ('before-qualification', 'after-qualification')
TABLES = (0, 1)
RULES = ('warm-owned-sources', 'one-complete-original-feedback',
         'declared-qualification-lifetime', 'disabled-visible-effect',
         'all-other-protection-preserved', 'reopened-without-replay',
         'fresh-learning-after-reopen', 'immutable-originals')


@dataclass(frozen=True, slots=True)
class Program:
    table: int
    phase: str

    def __post_init__(self):
        if type(self.table) is not int or self.table not in TABLES or self.phase not in PHASES:
            raise ValueError('short/long provider and declared qualification lifetime required')

    @property
    def label(self): return str(self.table) + '.' + self.phase

    @property
    def seed(self): return UsefulnessProgram(self.table, 'initial-protection')

    @property
    def initial(self): return self.seed.initial

    @property
    def qualifies(self): return self.phase == 'after-qualification'

    @staticmethod
    def reward(state):
        return state.feedback(predicted=state.taken, base=1 - state.taken, actual=state.taken)

    @property
    def disabled(self): return self.reward(self.initial) if self.qualifies else self.initial

    @property
    def reopened_learning(self): return self.reward(self.disabled)

    def protection(self, state):
        values = [[0] * 512 for _ in TABLES]
        for history in (HISTORY, NEIGHBOR_HISTORY):
            identity = indices(PC, Context.from_recent(history))
            values[0][identity[0]] = 1 if self.table == 0 else 0
            if self.table == 1:
                values[1][identity[1]] = 2
        selected = indices(PC, Context.from_recent(HISTORY))[self.table]
        values[self.table][selected] = state.useful
        return tuple(value for table in values for value in table)

    def state(self):
        return dict(table=self.table, phase=self.phase, initial=asdict(self.initial),
            expected_while_disabled=asdict(self.disabled), expected_after_fresh_learning=asdict(self.reopened_learning))
