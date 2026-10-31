"""Original prediction contribution and current learning state are distinct."""
from dataclasses import dataclass
from suites.frontend.bpu.utage.model.query_identity import PC, POSITION, READ_PCS
from suites.frontend.bpu.utage.model.usefulness_events import ProtectionState

MODES = ('serial', 'adjacent')
ORDERS = ('interleaved', 'finish-each')
RULES = ('normal-opposed-short-identities', 'every-feedback-distinct-original',
    'actual-direction-flipped-before-return', 'originally-correct-still-rewarded',
    'originally-wrong-still-penalized', 'confidence-composes-current-version',
    'original-survives-other-history-learning', 'all-protection-cells-preserved',
    'long-companions-preserved', 'fresh-consumers-all-phases',
    'actual-feedback-cadence', 'original-snapshots-immutable')


@dataclass(frozen=True, slots=True)
class Step:
    ordinal: int
    owner: int
    phase: str
    before: ProtectionState | None
    current: ProtectionState | None
    after: ProtectionState

    @property
    def history(self): return 64 if self.phase == 'late-wrong' else 0
    @property
    def base(self): return 1-self.owner if self.phase == 'late-wrong' else self.owner
    @property
    def actual(self): return self.owner if self.phase == 'flip' else 1-self.owner
    @property
    def indices(self): return READ_PCS[self.owner] % 512, READ_PCS[self.owner] % 512
    @property
    def expected(self): return (0, None, None, None) if self.before is None else (1, 0, self.before.counter, self.before.taken)
    @property
    def companion_allocation(self): return self.phase == 'flip'
    @property
    def counter_cell(self): return dict(valid=1, data_valid=1, index=self.indices[0], tag=0,
        position=POSITION, counter=self.after.counter)
    @property
    def current_cell(self): return dict(self.counter_cell, counter=self.current.counter)
    @property
    def companion_cell(self): return dict(valid=1, data_valid=1, index=self.indices[1], tag=0,
        position=POSITION, counter=4 if self.actual else 3)
    @property
    def changes(self):
        old = 0 if self.current is None else self.current.useful
        rows = [] if old == self.after.useful else [(self.indices[0], old, self.after.useful)]
        if self.companion_allocation: rows.append((512+self.indices[1], 0, 2))
        return tuple(sorted(rows))


@dataclass(frozen=True, slots=True)
class Program:
    mode: str
    order: str

    def __post_init__(self):
        if self.mode not in MODES or self.order not in ORDERS:
            raise ValueError('declared feedback cadence and semantic return order required')
    @property
    def label(self): return self.mode+'.'+self.order
    @property
    def groups(self):
        recipe = [('allocate', (0, 1))]
        recipe.extend([(phase, (0, 1)) for phase in ('flip', 'late-correct', 'late-wrong')] if self.order == 'interleaved'
            else [(phase, (owner,)) for owner in (0, 1) for phase in ('flip', 'late-correct', 'late-wrong')])
        states = [None, None]; result = []; ordinal = 0
        for phase, owners in recipe:
            group = []
            for owner in owners:
                current = states[owner]
                original = None if phase == 'allocate' else ProtectionState(
                    (3 if owner == 0 else 4) if phase == 'late-wrong' else (4 if owner == 0 else 3),
                    0 if phase == 'late-wrong' else 1)
                after = ProtectionState(4 if owner == 0 else 3, 1) if phase == 'allocate' else current.feedback(
                    predicted=original.taken, base=1-owner if phase == 'late-wrong' else owner,
                    actual=owner if phase == 'flip' else 1-owner)
                step = Step(ordinal, owner, phase, original, current, after)
                states[owner] = after; group.append(step); ordinal += 1
            result.append(tuple(group))
        return tuple(result)
    @property
    def steps(self): return tuple(step for group in self.groups for step in group)
    def step(self, phase, owner): return next(s for s in self.steps if s.phase == phase and s.owner == owner)
    @staticmethod
    def read_indices(owner): return (READ_PCS[owner] % 512,)*2
    def protection_after(self, count):
        if type(count) is not int or not 0 <= count <= len(self.steps): raise ValueError('declared learning prefix required')
        result = [0]*1024
        for step in self.steps[:count]:
            result[step.indices[0]] = step.after.useful
            if step.companion_allocation: result[512+step.indices[1]] = 2
        return tuple(result)
    def state(self): return dict(mode=self.mode, order=self.order, actual_feedbacks=8,
        initial=((4, 1), (3, 1)), final=((5, 0), (2, 0)),
        original_correctness_is_not_current_direction=True, physical_enumeration=False,
        full_FTQ_source_eligibility_proved=False)


PROGRAMS = tuple(Program(mode, order) for mode in MODES for order in ORDERS)
