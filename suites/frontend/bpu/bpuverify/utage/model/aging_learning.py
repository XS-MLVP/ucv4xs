"""Logical maintenance/learning programs; no DUT state seeds or timing loops."""
from dataclasses import dataclass, replace

from bpuverify.utage.model.semantic import Context, indices


POSITION = 5
RULES = ('allocate', 'reward', 'penalty')
ALLOCATION_FAILURES = 128


@dataclass(frozen=True)
class BranchContext:
    name: str
    pc: int
    history: int

    @property
    def index(self):
        return indices(self.pc, Context.from_recent(self.history))

    @property
    def short_alias(self):
        return replace(self, name=self.name + '.short-consumer', history=self.history ^ 0x40)


@dataclass(frozen=True)
class Read:
    context: BranchContext
    provider: int | None
    counter: int | None
    base: int = 1

    @property
    def taken(self):
        return self.base if self.provider is None else int(self.counter >= 4)


@dataclass(frozen=True)
class Learn:
    source: Read
    actual: int


def short(context):
    return (Learn(Read(context, None, None), 0),)


def long(context):
    return (*short(context), Learn(Read(context, 0, 3), 1))


@dataclass(frozen=True)
class AgingLearningProgram:
    table: int
    rule: str

    def __post_init__(self):
        if type(self.table) is not int or self.table not in (0, 1) or self.rule not in RULES:
            raise ValueError('maintenance overlap requires a short/long table and a semantic learning event')

    @property
    def name(self):
        return f'{"short" if self.table == 0 else "long"}-{self.rule}'

    target = BranchContext('target', 0x40000000, 0xA6B)
    neighbor = BranchContext('neighbor', 0x40000000, 0xA7E)
    failure = BranchContext('failure', 0x40000040, 0x123)

    @property
    def preparation(self):
        neighbor = self.neighbor
        steps = (*long(self.failure), *short(neighbor),
            Learn(Read(neighbor, 0, 3), 0), Learn(Read(neighbor, 0, 2), 0),
            Learn(Read(neighbor, 0, 1), 1),
            Learn(Read(neighbor.short_alias, 0, 2), 0),
            Learn(Read(neighbor, 1, 4, base=0), 1))
        if self.table == 0:
            target = () if self.rule == 'allocate' else short(self.target)
            if self.rule == 'penalty':
                target += (Learn(Read(self.target, 0, 3), 0),)
        elif self.rule == 'allocate':
            target = short(self.target)
        else:
            target = long(self.target)
            if self.rule == 'reward':
                target += (Learn(Read(self.target, 1, 4), 0),)
        return (*steps, *target)

    @property
    def preparation_failures(self):
        return int(self.table == 1 and self.rule == 'reward')

    @property
    def ordinary_failures(self):
        return ALLOCATION_FAILURES - 1 - self.preparation_failures

    def failed_source(self, previous):
        if type(previous) is not int or not 0 <= previous <= self.ordinary_failures:
            raise ValueError('failure progress is bounded by the maintenance precondition')
        source = Read(self.failure, 1, 4 - previous % 2)
        return Learn(source, 1 - source.taken)

    @property
    def target_learning(self):
        if self.table == 0:
            provider, counter = (None, None) if self.rule == 'allocate' else (0, 3 if self.rule == 'reward' else 2)
        else:
            provider, counter = (0, 3) if self.rule == 'allocate' else (1, 3 if self.rule == 'reward' else 4)
        actual = int((self.table, self.rule) in ((0, 'penalty'), (1, 'allocate')))
        return Learn(Read(self.target, provider, counter), actual)

    @property
    def before(self):
        target = {(0, 'allocate'): (0, 0), (0, 'reward'): (1, 0), (0, 'penalty'): (2, 0),
                  (1, 'allocate'): (1, 0), (1, 'reward'): (0, 1), (1, 'penalty'): (0, 2)}[self.table, self.rule]
        values = [0] * 1024
        for table in range(2):
            values[table * 512 + self.neighbor.index[table]] = 3
            values[table * 512 + self.target.index[table]] = target[table]
        return tuple(values)

    @property
    def after(self):
        return tuple(max(0, value - 1) if address < 512 else value // 2
                     for address, value in enumerate(self.before))

    @property
    def controls(self):
        source = self.target_learning.source
        # A wrong short provider also legitimately allocates the long table.
        allocate = 0 if source.provider is None else 1 if source.provider == 0 and self.target_learning.actual != source.taken else None
        return tuple(dict(age=1, allocate=int(allocate == table), update=int(source.provider == table),
            **(dict(index=self.target.index[table]) if allocate == table or source.provider == table else {}),
            **(dict(useful_valid=1, increase=int(self.rule == 'reward')) if source.provider == table else {}))
            for table in range(2))

    @property
    def consumers(self):
        target = {(0, 'allocate'): (3, None), (0, 'reward'): (2, None), (0, 'penalty'): (3, 4),
                  (1, 'allocate'): (4, 4), (1, 'reward'): (4, 2), (1, 'penalty'): (4, 3)}[self.table, self.rule]
        rows = ((Read(self.target, 0, target[0]),) if target[1] is None else
                (Read(self.target, 1, target[1]), Read(self.target.short_alias, 0, target[0])))
        return (*rows, Read(self.neighbor, 1, 5), Read(self.neighbor.short_alias, 0, 1),
            Read(self.failure, 1, 4 - (self.ordinary_failures + 1) % 2),
            Read(self.failure.short_alias, 0, 4))
