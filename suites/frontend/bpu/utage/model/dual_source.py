"""Instruction-prefix teaching of two independently learned branch experiences."""
from dataclasses import dataclass, asdict
from suites.frontend.bpu.utage.model.semantic import Context, indices, tag
from suites.frontend.bpu.utage.model.usefulness_events import ProtectionState

PC, EARLY, LATE = 0x40000000, 2, 12
RELATIONS = ('short-earlier', 'short-later')
LAYOUTS = ('in-order-holes', 'reversed-holes')
RESULTS = ('later-conditional', 'whole-window-NT', 'earlier-conditional', 'later-direct', 'later-indirect')
MODES = ('serial', 'adjacent')
COMMON_RULES = ('normal-two-provider-prestate', 'instruction-position-not-slot-order',
    'at-most-one-real-direction-error', 'complete-original-feedback-once',
    'complete-write-or-preserve-mask', 'whole-protection-isolation',
    'fresh-full-vector-consumers', 'actual-query-and-feedback-cadence',
    'immutable-distinct-originals', 'no-hidden-maintenance')


@dataclass(frozen=True)
class Experience:
    position: int
    counter: int
    useful: int

    @property
    def taken(self): return int(self.counter >= 4)
    def teach(self, original, actual):
        updated = ProtectionState(self.counter, self.useful).feedback(
            predicted=original.taken, base=int(self.position == EARLY), actual=actual)
        return Experience(self.position, updated.counter, updated.useful)


@dataclass(frozen=True)
class Step:
    ordinal: int
    name: str
    position: int
    taken: int
    kind: int
    before: tuple
    sources: tuple
    after: tuple
    writes: tuple
    error: bool
    allocation: int | None = None
    seed_position: int | None = None

    @property
    def changes(self):
        return tuple((table*512, 0 if before is None else before.useful, after.useful)
            for table, (before, after) in enumerate(zip(self.before, self.after, strict=True))
            if after is not None and (0 if before is None else before.useful) != after.useful)
    def cell(self, table):
        value = self.after[table]
        return dict(valid=1, data_valid=1, index=indices(PC, Context())[table],
            tag=tag(PC, Context(), table), position=value.position, counter=value.counter)


@dataclass(frozen=True)
class Program:
    relation: str
    layout: str
    result: str
    mode: str

    def __post_init__(self):
        if self.relation not in RELATIONS or self.layout not in LAYOUTS or self.result not in RESULTS or self.mode not in MODES:
            raise ValueError('declared provider/position relation, slot layout, resolved outcome and cadence required')
    @property
    def label(self): return '.'.join((self.relation, self.layout, self.result, self.mode))
    @property
    def short_position(self): return EARLY if self.relation == RELATIONS[0] else LATE
    @property
    def warm_steps(self):
        # A nonconditional preservation witness needs an interior later
        # confidence: an erroneous increment must not hide at saturation.
        return (2 if self.short_position == EARLY else 1) if self.result in RESULTS[3:] else 3
    @property
    def preparation_count(self): return 2+self.warm_steps
    @property
    def slots(self): return (EARLY, None, LATE, None) if self.layout == LAYOUTS[0] else (None, LATE, None, EARLY)
    def positions(self, seed_position=None): return tuple(p if seed_position is None or p == seed_position else None for p in self.slots)
    @property
    def resolved(self):
        return (LATE, 1, 1) if self.result == RESULTS[0] else (15, 0, 1) if self.result == RESULTS[1] else (
            EARLY, 1, 1) if self.result == RESULTS[2] else (LATE, 1, 2 if self.result == RESULTS[3] else 3)
    @property
    def steps(self):
        short = Experience(self.short_position, 3 if self.short_position == EARLY else 4, 1)
        rows = [Step(0, 'seed-short', short.position, short.taken, 1,
            (None, None), (None, None), (short, None), (0,), True, 0, short.position)]
        long_position = LATE if short.position == EARLY else EARLY
        after = (Experience(short.position, 2 if short.position == EARLY else 5, 2),
            Experience(long_position, 4 if long_position == LATE else 3, 2))
        rows.append(Step(1, 'establish-other-position', LATE, 1, 1,
            rows[-1].after, rows[-1].after, after, (0,1), True, 1))
        for number in range(self.warm_steps):
            before = rows[-1].after
            after = tuple(value.teach(value, int(value.position == LATE)) for value in before)
            rows.append(Step(len(rows), 'strengthen-both-'+str(number+1), LATE, 1, 1,
                before, before, after, (0,1), False))
        original = rows[-1].after
        position, taken, kind = self.resolved
        for number in range(2):
            before = rows[-1].after
            active = tuple(table for table, value in enumerate(before)
                if value.position < position or value.position == position and kind == 1)
            actuals = {table: int(before[table].position == position and taken) for table in active}
            after = tuple(value.teach(original[table], actuals[table]) if table in active else value
                for table, value in enumerate(before))
            errors = sum(original[table].taken != actuals[table] for table in active)
            assert errors <= 1
            rows.append(Step(len(rows), 'original-result-'+str(number+1), position, taken, kind,
                before, original, after, active, bool(errors)))
        return tuple(rows)
    @property
    def prepared(self): return self.steps[self.preparation_count-1].after
    @property
    def failed_allocations(self): return 2 if self.result in RESULTS[1:3] else 0
    @property
    def rules(self):
        if self.result == RESULTS[0]: extra = ('both-executed-opposed-rewards', 'both-direction-and-protection-boundaries')
        elif self.result == RESULTS[1]: extra = ('both-executed-learn-NT', 'only-wrong-source-penalized')
        elif self.result == RESULTS[2]: extra = ('only-earlier-executed', 'later-full-version-preserved', 'old-feedback-accumulates-current-confidence')
        else: extra = ('same-position-nonconditional-is-ineligible', 'qualified-earlier-still-learns', 'later-full-version-preserved')
        if self.result in RESULTS[1:3]:
            wrong_position = LATE if self.result == RESULTS[1] else EARLY
            extra += ('protected-companion-not-overwritten' if wrong_position == self.short_position else 'no-deeper-allocation-for-long-provider',)
        return COMMON_RULES + extra
    def protection_after(self, count):
        if type(count) is not int or not 0 <= count <= len(self.steps): raise ValueError('declared complete feedback prefix required')
        result = [0]*1024
        for step in self.steps[:count]:
            for table, value in enumerate(step.after):
                if value is not None: result[table*512] = value.useful
        return tuple(result)
    def state(self):
        return dict(relation=self.relation, layout=self.layout, result=self.result, mode=self.mode,
            pc=PC, slots=self.slots, short_position=self.short_position,
            prepared=tuple(asdict(e) for e in self.prepared), feedbacks=len(self.steps),
            max_direction_errors_per_feedback=1, physical_enumeration=False, full_FTQ_reachability_claimed=False)


PROGRAMS = tuple(Program(r,l,o,m) for r in RELATIONS for l in LAYOUTS for o in RESULTS for m in MODES)
OBLIGATIONS = tuple(p.label+'.'+rule for p in PROGRAMS for rule in p.rules)
