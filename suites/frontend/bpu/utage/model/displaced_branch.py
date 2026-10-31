"""A late original cannot reclaim an experience owned by another instruction.

This declares a finite instruction lifetime, not another predictor algorithm.
All states are independently replayed through the unchanged UtageReference.
"""
from dataclasses import dataclass, asdict
from suites.frontend.bpu.utage.model.dual_source import Program as VectorProgram, Experience, Step, PC, EARLY, LATE

OWNERS = ('same-branch-refresh', 'different-branch-takeover')
QUALIFICATIONS = ('original-correct-opposition', 'original-wrong')
MODES = ('serial', 'adjacent')
RULES = ('normal-two-provider-prestate', 'real-distinct-originals',
    'normal-release-and-takeover', 'original-before-takeover',
    'actual-resident-instruction-identity', 'original-qualified-write-mask',
    'companion-still-learns', 'every-complete-native-version',
    'all-protection-and-neighbors', 'fresh-three-instruction-consumers',
    'actual-original-feedback-cadence', 'immutable-originals')


@dataclass(frozen=True)
class Program:
    owner: str
    qualification: str
    mode: str

    def __post_init__(self):
        if self.owner not in OWNERS or self.qualification not in QUALIFICATIONS or self.mode not in MODES:
            raise ValueError('declared resident identity, original contribution and cadence required')

    rules = RULES
    @property
    def label(self): return '.'.join((self.owner, self.qualification, self.mode))
    @property
    def replacement_position(self): return EARLY if self.owner == OWNERS[0] else 7
    @property
    def original_wrong(self): return self.qualification == QUALIFICATIONS[1]
    @property
    def initial_steps(self):
        return VectorProgram('short-earlier', 'reversed-holes', 'later-conditional', 'serial').steps[:4]
    @property
    def capture_after(self): return 8 if self.original_wrong else 4
    @property
    def preparation_count(self): return 9
    @property
    def failed_allocations(self): return 4 + 2 * int(self.original_wrong)

    def positions(self, seed_position=None, *, consumer=False):
        if seed_position is not None: return (None, None, seed_position, None)
        return (7 if consumer else None, LATE, None, EARLY)

    @property
    def steps(self):
        rows = list(self.initial_steps)
        # Four distinct fresh wrong sources release protection3→0, hold its
        # lower boundary, and change direction0→4. The companion is unexecuted.
        for number in range(4):
            before = rows[-1].after
            short = before[0].teach(before[0], 1)
            rows.append(Step(len(rows), 'release-original-'+str(number+1), EARLY, 1, 1,
                before, before, (short, before[1]), (0,), True))
        originals = rows[self.capture_after-1].after
        before = rows[-1].after
        position = self.replacement_position
        replacement = Experience(position, 3 if position == EARLY else 4, 1)
        # A DIFFERENT genuine cold occurrence is retained from reset. Even in
        # the same-instruction control it has not taught once before refresh.
        rows.append(Step(len(rows), 'cold-original-installs-current-owner', position,
            replacement.taken, 1, before, (None, None), (replacement, before[1]), (0,), True,
            allocation=0, seed_position=position))
        for number in range(2):
            before = rows[-1].after
            short = before[0] if position != EARLY else before[0].teach(originals[0], 0)
            long = before[1].teach(originals[1], 1)
            writes = (1,) if position != EARLY else (0, 1)
            rows.append(Step(len(rows), 'late-original-'+str(number+1), LATE, 1, 1,
                before, originals, (short, long), writes, self.original_wrong))
        return tuple(rows)

    def protection_after(self, count):
        if type(count) is not int or not 0 <= count <= len(self.steps):
            raise ValueError('complete declared feedback prefix required')
        values = [0] * 1024
        for step in self.steps[:count]:
            for table, entry in enumerate(step.after):
                if entry is not None: values[table * 512] = entry.useful
        return tuple(values)

    def state(self):
        return dict(owner=self.owner, qualification=self.qualification, mode=self.mode,
            pc=PC, original_position=EARLY, companion_position=LATE,
            replacement_position=self.replacement_position, capture_after=self.capture_after,
            original_state=[asdict(e) for e in self.steps[-1].sources],
            replacement_state=[asdict(e) for e in self.steps[self.preparation_count-1].after],
            feedbacks=len(self.steps), physical_enumeration=False, full_FTQ_reachability_claimed=False)


PROGRAMS = tuple(Program(o,q,m) for o in OWNERS for q in QUALIFICATIONS for m in MODES)
OBLIGATIONS = tuple(p.label+'.'+rule for p in PROGRAMS for rule in RULES)
