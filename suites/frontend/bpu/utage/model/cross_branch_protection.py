"""Four branch identities, original contribution and current protection law."""
from dataclasses import dataclass
from suites.frontend.bpu.utage.model.semantic import Context, indices, tag
from suites.frontend.bpu.utage.model.usefulness_events import ProtectionState

PC, POSITION = 0x40000000, 5
# Two neighboring halfword entries in each of two code blocks. The program
# distinguishes actual matching PCs as well as independent read ancestors.
PCS = (PC, PC+1, PC+0x40, PC+0x41)
LINEAGES = ('same-ancestor', 'different-ancestor')
MODES = ('serial', 'adjacent')
ORDERS = ('capture-order', 'reverse-order')
RULES = ('four-real-matching-branches', 'exact-read-and-match-ancestors',
    'distinct-originals-before-direction-flips', 'four-real-opposite-learnings',
    'old-correct-opposition-reward', 'old-base-agreement-no-reward',
    'old-wrong-not-retroactively-correct', 'current-confidence-keeps-original-owner',
    'complete-short-and-long-learning', 'all-protection-neighbors-preserved',
    'fresh-consumers-at-every-phase', 'all-originals-immutable',
    'actual-cadence-and-return-order', 'no-unrequested-maintenance')


@dataclass(frozen=True, slots=True)
class Step:
    ordinal: int
    owner: int
    phase: str
    pc: int
    read_pc: int
    original: ProtectionState | None
    current: ProtectionState | None
    after: ProtectionState
    base: int
    actual: int

    @property
    def before(self): return self.original
    @property
    def history(self): return 64 if self.phase == 'late-wrong' else 0
    @property
    def indices(self): return indices(self.read_pc, Context())
    @property
    def expected(self): return (0, None, None, None) if self.original is None else (1, 0, self.original.counter, self.original.taken)
    @property
    def companion_allocation(self): return self.phase == 'flip'
    @property
    def counter_cell(self):
        return dict(valid=1, data_valid=1, index=self.indices[0], tag=tag(self.pc, Context.from_recent(self.history), 0),
            position=POSITION, counter=self.after.counter)
    @property
    def current_cell(self): return dict(self.counter_cell, counter=self.current.counter)
    @property
    def companion_cell(self):
        return dict(valid=1, data_valid=1, index=self.indices[1], tag=tag(self.pc, Context(), 1),
            position=POSITION, counter=4 if self.actual else 3)
    @property
    def changes(self):
        previous = 0 if self.current is None else self.current.useful
        result = [] if previous == self.after.useful else [(self.indices[0], previous, self.after.useful)]
        if self.companion_allocation: result.append((512+self.indices[1], 0, 2))
        return tuple(sorted(result))


@dataclass(frozen=True, slots=True)
class Program:
    lineage: str
    mode: str
    order: str

    def __post_init__(self):
        if self.lineage not in LINEAGES or self.mode not in MODES or self.order not in ORDERS:
            raise ValueError('declared source lineage, feedback cadence and original return order required')
    @property
    def label(self): return '.'.join((self.lineage, self.mode, self.order))
    @property
    def owners(self): return tuple(range(4))
    def pc(self, owner): return PCS[owner]
    def read_pc(self, owner): return self.pc(owner) if self.lineage == LINEAGES[0] else self.pc(owner)^0x180
    def read_indices(self, owner): return indices(self.read_pc(owner), Context())
    @staticmethod
    def taken(owner): return 1-owner%2
    @staticmethod
    def initial(owner): return ProtectionState(4 if Program.taken(owner) else 3, 1)
    @property
    def return_order(self): return self.owners if self.order == ORDERS[0] else tuple(reversed(self.owners))
    @property
    def groups(self):
        states = [None]*4
        groups = []
        for phase, owners in (('allocate', self.owners), ('flip', self.owners),
                ('late-correct', self.return_order), ('late-wrong', self.return_order)):
            group = []
            for owner in owners:
                initial = self.initial(owner)
                current = states[owner]
                if phase == 'allocate':
                    original, base, actual, after = None, 1-initial.taken, initial.taken, initial
                elif phase == 'flip':
                    original, base, actual = initial, 1-initial.taken, 1-initial.taken
                    after = current.feedback(predicted=original.taken, base=base, actual=actual)
                elif phase == 'late-correct':
                    original, actual = initial, initial.taken
                    base = 1-initial.taken if owner < 2 else initial.taken
                    after = current.feedback(predicted=original.taken, base=base, actual=actual)
                else:
                    original = ProtectionState(3 if initial.taken else 4, 0)
                    base, actual = initial.taken, initial.taken
                    after = current.feedback(predicted=original.taken, base=base, actual=actual)
                group.append(Step(len(groups)*4+len(group), owner, phase, self.pc(owner), self.read_pc(owner),
                    original, current, after, base, actual))
                states[owner] = after
            groups.append(tuple(group))
        return tuple(groups)
    @property
    def steps(self): return tuple(s for group in self.groups for s in group)
    def step(self, phase, owner): return next(s for s in self.steps if s.phase == phase and s.owner == owner)
    def protection_after(self, count):
        if type(count) is not int or not 0 <= count <= 16: raise ValueError('declared accepted-learning prefix required')
        result = [0]*1024
        for step in self.steps[:count]:
            result[step.indices[0]] = step.after.useful
            if step.companion_allocation: result[512+step.indices[1]] = 2
        return tuple(result)
    def state(self):
        return dict(lineage=self.lineage, mode=self.mode, order=self.order, matching_pcs=PCS,
            read_pcs=tuple(self.read_pc(o) for o in self.owners), late_correct_roles=('reward', 'reward', 'agreement', 'agreement'),
            feedbacks=16, physical_enumeration=False, full_FTQ_reachability_claimed=False)


PROGRAMS = tuple(Program(l, m, o) for l in LINEAGES for m in MODES for o in ORDERS)
