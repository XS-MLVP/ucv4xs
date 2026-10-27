"""Owned branch records, learning decisions and immutable read transactions.

PC/target units are the existing UT API's halfwords, not full byte addresses.
Four banks contain 64 four-way rows with 24-bit partial tags and 22-bit local
targets. Predicting does not touch replacement age: accepted taken feedback
and committed writes do. Feedback metadata is an upstream UT input, never a
way/counter sampled from an internal DUT signal.

Pending writes are versioned obligations for physical (row, way) destinations.
Different branch positions must not cancel one another merely because their
partial tags agree. The visibility contract is separate from branch learning;
it does not import the old slot/dirty-mask implementation audit.
"""
from dataclasses import dataclass, replace


BANKS, ROWS, WAYS = 4, 64, 4
TAG_SIZE, TARGET_SIZE = 1 << 24, 1 << 22


def unsigned(value, limit, name):
    if type(value) is not int or not 0 <= value < limit:
        raise ValueError(f'ABTB {name} must be an unsigned integer below {limit}')


def coordinate(pc, history=0):
    unsigned(pc, 1 << 49, 'halfword PC')
    unsigned(history, 16, 'history feature')
    address = ((2 * pc) ^ history) % (BANKS * ROWS)
    return address % BANKS, address // BANKS


@dataclass(frozen=True, slots=True)
class Entry:
    valid: bool = False
    tag: int = 0
    position: int = 0
    kind: int = 0
    action: int = 0
    target: int = 0


@dataclass(frozen=True, slots=True)
class Source:
    hit: bool = False
    position: int = 0
    kind: int = 0
    action: int = 0
    target: int = 0

    def __post_init__(self):
        if type(self.hit) is not bool:
            raise ValueError('ABTB source hit must be a semantic bool')
        for value, limit, name in ((self.position, 16, 'position'), (self.kind, 4, 'branch kind'),
                                  (self.action, 4, 'stack action'), (self.target, TARGET_SIZE, 'local target')):
            unsigned(value, limit, name)


@dataclass(frozen=True, slots=True)
class Feedback:
    pc: int
    target: int
    taken: bool
    position: int
    kind: int
    action: int
    valid: bool
    row: int
    banks: int
    sources: tuple[Source, ...]

    def __post_init__(self):
        for value, limit, name in ((self.pc, 1 << 49, 'halfword PC'), (self.target, 1 << 49, 'halfword target'),
            (self.position, 16, 'position'), (self.kind, 4, 'branch kind'), (self.action, 4, 'stack action'),
            (self.row, ROWS, 'row'), (self.banks, 1 << BANKS, 'bank mask')):
            unsigned(value, limit, name)
        if type(self.taken) is not bool or type(self.valid) is not bool:
            raise ValueError('ABTB feedback qualification and direction must be semantic bools')
        if type(self.sources) is not tuple or len(self.sources) != WAYS or any(type(source) is not Source for source in self.sources):
            raise ValueError('ABTB feedback requires four immutable semantic sources')


@dataclass(frozen=True, slots=True)
class Recency:
    """A heap-ordered choice tree, independent of the RTL bit encoding."""
    oldest_half: int = 0
    oldest_members: tuple[int, int] = (0, 0)

    @property
    def victim(self):
        return 2 * self.oldest_half + self.oldest_members[self.oldest_half]

    def touch(self, way):
        unsigned(way, WAYS, 'way')
        half, member = divmod(way, 2)
        children = list(self.oldest_members)
        children[half] = 1 - member
        return Recency(1 - half, tuple(children))


@dataclass(frozen=True, slots=True)
class Write:
    row: int
    way: int
    entry: Entry
    reset_direction: bool


@dataclass(frozen=True, slots=True)
class Version:
    order: int
    priority: int
    write: Write


class PendingWrites:
    """Four reusable service positions, but ownership is destination/version.

    A completed identical write needs no repeat service. Changed writes to a
    destination compose by superseding only that destination's obligation.
    A non-backpressured capacity miss can replace an older service position;
    distinct in-capacity destinations remain independently obligated.
    """
    def __init__(self):
        self.versions = {}
        self.outstanding = set()
        self.age = Recency()
        self.order = 0
        self.overflows = 0

    def advance(self, busy, incoming=None):
        before = dict(self.versions)
        pending = sorted((item for item in before.values() if item.order in self.outstanding),
                         key=lambda item: item.priority)
        retiring = pending[0] if pending and not busy else None
        if retiring is not None:
            self.outstanding.remove(retiring.order)
        if incoming is not None:
            key = incoming.row, incoming.way
            prior = before.get(key)
            if prior is not None and prior.order not in self.outstanding and prior.write == incoming:
                # A simultaneous retirement followed by a repeated allocation
                # is still a new offer if the old offer was pending beforehand.
                if prior not in pending:
                    return None if retiring is None else retiring.write
            if prior is None:
                used = {item.priority for item in pending}
                priority = next((rank for rank in range(WAYS) if rank not in used), self.age.victim)
                evicted_key = next((old_key for old_key, item in before.items()
                                    if item.priority == priority), None)
                if evicted_key is not None:
                    removed = self.versions.pop(evicted_key)
                    if removed.order in self.outstanding:
                        self.outstanding.remove(removed.order)
                        self.overflows += 1
                self.age = self.age.touch(priority)
            else:
                priority = prior.priority
                self.outstanding.discard(prior.order)
            version = Version(self.order, priority, incoming)
            self.order += 1
            self.versions[key] = version
            self.outstanding.add(version.order)
        return None if retiring is None else retiring.write


@dataclass(frozen=True, slots=True)
class Read:
    bank: int
    row: int
    entries: tuple[Entry, ...]


@dataclass(frozen=True, slots=True)
class Frame:
    read: Read
    pc: int
    counters: tuple[int, ...]
    valid: bool = True

    @property
    def hits(self):
        return tuple(entry.valid and entry.tag == self.pc % TAG_SIZE for entry in self.read.entries)

    def values(self, enabled=True):
        active = self.valid and enabled
        values = dict(meta_valid=int(active))
        for way, (entry, hit, counter) in enumerate(zip(self.read.entries, self.hits, self.counters, strict=True)):
            values[f'{way}.valid'] = int(active and hit)
            values[f'{way}.micro_valid'] = int(active and hit)
            if active:
                values[f'{way}.meta_hit'] = int(hit)
            if active and hit:
                values.update({f'{way}.taken': int(counter >= 2),
                    f'{way}.target': (self.pc // TARGET_SIZE) * TARGET_SIZE + entry.target,
                    f'{way}.position': entry.position, f'{way}.kind': entry.kind, f'{way}.action': entry.action,
                    f'{way}.strong': int(counter in (0, 3)), f'{way}.target_low': entry.target})
        if active:
            values.update(row=self.read.row, banks=1 << self.read.bank)
        return values


@dataclass(frozen=True, slots=True)
class Decision:
    feedback: Feedback
    matching: tuple[int, ...]
    writes: tuple[Write | None, ...]


@dataclass(frozen=True, slots=True)
class Events:
    read_pc: int = 0
    history: int = 0
    select: bool = False
    match_pc: int = 0
    consume: bool = False
    remember: bool = False
    override: str | None = None
    override_pc: int = 0
    redirect: bool = False
    feedback: Feedback | None = None
    enabled: bool = True
    ready: bool = True
    reset: bool = False

    def __post_init__(self):
        coordinate(self.read_pc, self.history)
        unsigned(self.match_pc, 1 << 49, 'match PC')
        unsigned(self.override_pc, 1 << 49, 'override PC')
        for value in (self.select, self.consume, self.remember, self.redirect, self.enabled, self.ready, self.reset):
            if type(value) is not bool:
                raise ValueError('ABTB event qualification must use semantic bools, not signal wrappers')
        if self.override not in (None, 's2', 's3'):
            raise ValueError('ABTB recovery must name s2 or s3')
        if self.feedback is not None and type(self.feedback) is not Feedback:
            raise ValueError('ABTB event feedback must be a semantic Feedback')


class AbtbReference:
    def __init__(self):
        self.reset()

    def reset(self):
        self.memory = {}
        self.counters = {}
        self.recency = {}
        self.pending = [PendingWrites() for _ in range(BANKS)]
        self.read = self.frame = self.replay = None
        self.read_ticket = False
        self.offered = self.decision = self.cleanup = None
        self.cycles = self.commits = self.feedbacks = 0

    def entries(self, bank, row):
        return tuple(self.memory.get((bank, row, way), Entry()) for way in range(WAYS))

    def directions(self, bank, row):
        return tuple(self.counters.get((bank, row, way), 0) for way in range(WAYS))

    def _decide(self, feedback):
        matching = tuple(way for way, source in enumerate(feedback.sources) if source.hit
            and (source.position, source.kind, source.action) == (feedback.position, feedback.kind, feedback.action))
        allocate = feedback.taken and not matching
        correct = bool(matching and feedback.kind == 3
                       and feedback.sources[matching[0]].target != feedback.target % TARGET_SIZE)
        entry = Entry(True, feedback.pc % TAG_SIZE, feedback.position, feedback.kind,
                      feedback.action, feedback.target % TARGET_SIZE)
        writes = tuple(Write(feedback.row,
            self.recency.get((bank, feedback.row), Recency()).victim if allocate else matching[0],
            entry, bool(allocate)) if feedback.banks & (1 << bank) and (allocate or correct) else None
            for bank in range(BANKS))
        return Decision(feedback, matching, writes)

    def advance(self, events=Events()):
        if events.reset:
            self.reset()
            return
        self.cycles += 1
        if not events.ready:
            return
        bank, row = coordinate(events.read_pc, events.history)
        reading = bool(events.select and events.enabled)
        old_read, old_frame, old_replay = self.read, self.frame, self.replay
        frame_valid = old_frame is not None and old_frame.valid
        consumed = bool(frame_valid and events.consume and not events.override and not events.redirect)
        space = consumed or not frame_valid or events.override is not None or events.redirect
        selected = bool(reading and self.read_ticket and old_read is not None and space)
        next_read = Read(bank, row, self.entries(bank, row)) if reading else old_read
        next_frame = old_frame
        if selected:
            next_frame = Frame(old_read, events.match_pc, self.directions(old_read.bank, old_read.row))
        if events.override:
            source = old_replay if events.override == 's3' else old_frame
            next_frame = replace(source, pc=events.override_pc) if source is not None else None
        elif not selected and consumed and next_frame is not None:
            next_frame = replace(next_frame, valid=False)
        if (not events.enabled or events.redirect) and next_frame is not None:
            next_frame = replace(next_frame, valid=False)
        self.frame, self.read = next_frame, next_read
        if not events.enabled:
            self.read_ticket = False
        elif reading:
            self.read_ticket = True
        elif events.redirect or selected:
            self.read_ticket = False
        if not events.enabled or events.redirect or events.override == 's3':
            self.replay = None
        elif events.remember:
            self.replay = old_frame

        next_cleanup = None
        if consumed:
            duplicates = [(first, second) for first in range(WAYS) for second in range(first + 1, WAYS)
                if old_frame.hits[first] and old_frame.hits[second]
                and old_frame.read.entries[first].position == old_frame.read.entries[second].position]
            if duplicates:
                first, _ = duplicates[-1]
                next_cleanup = old_frame.read.bank, Write(old_frame.read.row, first, Entry(), True)

        learned = self._decide(self.offered) if self.offered is not None else None
        retirement = []
        cleanup_serviced = False
        old_age = dict(self.recency)
        for number, pending in enumerate(self.pending):
            write = self.decision.writes[number] if self.decision is not None else None
            if write is None and self.cleanup is not None and self.cleanup[0] == number:
                write = self.cleanup[1]
                cleanup_serviced = True
            retired = pending.advance(reading and bank == number, write)
            if retired is not None:
                self.memory[number, retired.row, retired.way] = retired.entry
                retirement.append((number, retired))
                self.commits += 1

        if self.offered is not None:
            feedback = self.offered
            for number in range(BANKS):
                if feedback.banks & (1 << number):
                    for way, source in enumerate(feedback.sources):
                        if source.hit and source.kind == 1:
                            value = self.counters.get((number, feedback.row, way), 0)
                            if not feedback.taken or source.position < feedback.position:
                                value = max(0, value - 1)
                            elif source.position == feedback.position:
                                value = min(3, value + 1)
                            self.counters[number, feedback.row, way] = value
        if self.decision is not None and self.decision.feedback.taken and self.decision.matching:
            feedback = self.decision.feedback
            for number in range(BANKS):
                if feedback.banks & (1 << number):
                    age = old_age.get((number, feedback.row), Recency())
                    for way in self.decision.matching:
                        age = age.touch(way)
                    self.recency[number, feedback.row] = age
        for number, retired in retirement:
            if retired.reset_direction:
                self.counters[number, retired.row, retired.way] = 2
            self.recency[number, retired.row] = old_age.get((number, retired.row), Recency()).touch(retired.way)

        self.decision = learned
        self.offered = events.feedback if events.enabled and events.feedback is not None and events.feedback.valid else None
        self.feedbacks += int(self.offered is not None)
        self.cleanup = next_cleanup if next_cleanup is not None else None if cleanup_serviced else self.cleanup

    def values(self, enabled=True):
        if self.frame is not None:
            return self.frame.values(enabled)
        return dict(meta_valid=0, **{f'{way}.{key}': 0 for way in range(WAYS)
                                    for key in ('valid', 'micro_valid')})

    def state(self):
        return dict(cycles=self.cycles, commits=self.commits, accepted_feedback=self.feedbacks,
                    populated_cells=sum(entry.valid for entry in self.memory.values()),
                    pending=tuple(len(bank.outstanding) for bank in self.pending),
                    offered=self.offered, decision=self.decision, frame=self.frame, replay=self.replay)
