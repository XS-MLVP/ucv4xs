"""Logical learning lifetimes across retained and persistent storage."""
from dataclasses import dataclass

from bpuverify.utage.case.definitions import SHADOW_CAPACITY
from bpuverify.utage.model.semantic import Context, indices, tag

PC, SHORT_POSITION, POSITION = 0x40000000, 5, 6
MODES = ('serial', 'adjacent')
PROFILES = ('retained-window', 'first-retirement', 'chronological-lap')
RULES = ('normally-learned-short-prerequisites', 'unique-original-feedback-once',
    'actual-feedback-cadence', 'complete-owned-version-writes',
    'actual-persistent-service-and-storage-agree', 'retired-versions-remain-consumable',
    'fresh-reward-accumulates-after-turnover', 'all-protection-and-short-neighbors-preserved',
    'completed-originals-immutable', 'all-final-learning-persists')


@dataclass(frozen=True)
class Program:
    profile: str
    mode: str

    def __post_init__(self):
        if self.profile not in PROFILES or self.mode not in MODES:
            raise ValueError('declared logical lifetime and feedback cadence required')

    @property
    def count(self):
        return dict(zip(PROFILES, (SHADOW_CAPACITY, SHADOW_CAPACITY + 1,
                                  2 * SHADOW_CAPACITY + 1), strict=True))[self.profile]

    @property
    def histories(self):
        return tuple(number ^ (number >> 1) for number in range(self.count))

    @property
    def label(self):
        return self.profile + '.' + self.mode

    def order(self, phase):
        if phase not in ('short', 'allocate', 'reward', 'reward-again'):
            raise ValueError('declared learning phase required')
        return tuple(reversed(self.histories)) if phase == 'reward' else self.histories

    @staticmethod
    def identity(history, table):
        context = Context.from_recent(history)
        return (table, indices(PC, context)[table], tag(PC, context, table),
                SHORT_POSITION if table == 0 else POSITION)

    @staticmethod
    def counter(phase):
        return {'short': 4, 'allocate': 4, 'reward': 5, 'reward-again': 6}[phase]

    @staticmethod
    def actual(phase):
        return 1

    def protection(self, phase):
        values = [0] * 1024
        for history in self.histories:
            values[self.identity(history, 0)[1]] = 1
            if phase != 'short':
                values[512 + self.identity(history, 1)[1]] = 2 if phase == 'allocate' else 3
        return tuple(values)

    def state(self):
        return dict(profile=self.profile, mode=self.mode, count=self.count,
            promised_recent_capacity=SHADOW_CAPACITY, histories=self.histories,
            phases=('short', 'allocate', 'reward', 'reward-again'),
            physical_enumeration=False, full_FTQ_reachability_claimed=False)

    def lookup(self, history, table, *, phase=None):
        from bpuverify.utage.transaction.types import UtageLookup
        return UtageLookup(PC, SHORT_POSITION if table == 0 else POSITION, 0, folded_history=history)

    def expected(self, history, table, counter, *, phase=None):
        from bpuverify.utage.model.working_set import expected
        from bpuverify.utage.model.usefulness_events import ProtectionState
        state = None if counter is None else ProtectionState(counter, 1 if table == 0 else 2)
        return expected(history, 0, state, table=table, position=SHORT_POSITION if table == 0 else POSITION)
