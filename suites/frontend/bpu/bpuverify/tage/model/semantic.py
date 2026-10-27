"""Independent history-conditioned branch learning and visibility semantics.

The model owns four 4-bank/128-row/two-way tables, useful values, selector
confidence, immutable reads and versioned learning obligations. Prediction
metadata is an isolated-UT feedback input, never an SRAM/dirty-mask oracle.
Branch identity is (row, tag); useful learning follows that identity's retained
owner. Random allocation evolves from a reset seed, not an observed choice.
PC units are the existing UT API's halfwords.
"""
from dataclasses import dataclass, replace
from copy import copy

from bpuverify.common.model.folded_history import PHR_FOLD_LAYOUT


HISTORIES = (6, 9, 17, 31)
TABLES, BANKS, ROWS, WAYS = 4, 4, 128, 2
FOLD_IDS = tuple(tuple(PHR_FOLD_LAYOUT.index((length, min(length, width)))
                      for width in (7, 13, 12)) for length in HISTORIES)


def unsigned(value, limit, name):
    if type(value) is not int or not 0 <= value < limit:
        raise ValueError(f'TAGE {name} must be an unsigned integer below {limit}')


def clamp(value, maximum):
    return max(0, min(maximum, value))


@dataclass(frozen=True, slots=True)
class Context:
    folds: tuple[int, ...] = (0,) * len(PHR_FOLD_LAYOUT)

    def __post_init__(self):
        if type(self.folds) is not tuple or len(self.folds) != len(PHR_FOLD_LAYOUT):
            raise ValueError('TAGE context requires nineteen immutable public folds')
        for value, (_, width) in zip(self.folds, PHR_FOLD_LAYOUT, strict=True):
            unsigned(value, 1 << width, 'history fold')

    @classmethod
    def from_recent(cls, recent):
        unsigned(recent, 1 << 31, 'recent path history')
        return cls(tuple(sum((sum((recent >> position) & 1
            for position in range(bit, length, width)) % 2) << bit
            for bit in range(width)) for length, width in PHR_FOLD_LAYOUT))


def coordinate(pc, context, table):
    unsigned(pc, 1 << 49, 'halfword PC')
    unsigned(table, TABLES, 'table')
    index_fold, primary, secondary = (context.folds[index] for index in FOLD_IDS[table])
    return pc % BANKS, ((pc // BANKS) ^ index_fold) % ROWS, ((pc // (BANKS * ROWS)) ^ primary ^ (2 * secondary)) % 8192


def lfsr_next(value):
    unsigned(value, 1 << 15, 'allocation generator')
    if not value:
        raise ValueError('TAGE allocation generator cannot have the zero state')
    return ((value * 2) % (1 << 15)) + (((value // (1 << 13)) ^ (value // (1 << 14))) % 2)


@dataclass(frozen=True, slots=True)
class Entry:
    valid: bool = False
    tag: int = 0
    counter: int = 0


@dataclass(frozen=True, slots=True)
class Write:
    row: int
    way: int
    entry: Entry
    taken: bool


@dataclass(frozen=True, slots=True)
class Version:
    sequence: int
    rank: int
    write: Write


class LearningDestinationConflict(ValueError):
    """Two complete logical results need an as-yet unspecified arbitration."""
    def __init__(self, destination, claims, resident):
        self.destination = destination
        self.claims = claims
        self.resident = resident
        owner, rank = destination
        super().__init__(f'TAGE simultaneous updates share a retained destination '
                         f'(owner={owner}, rank={rank}); arbitration is undefined; '
                         f'claims={claims!r}; resident={resident!r}')


class RecentLearning:
    """Four reusable service ranks per owner, keyed by logical branch identity.

    Same-key learning composes using the latest counter and retains its owner.
    Same-destination replacement supersedes the older key. No physical dirty
    bitmap/slot from the DUT is consumed; pending versions own their lifetime.
    Every accepted learning access refreshes tree-PLRU recency, including a
    retained-key hit. The explicitly non-backpressured capacity boundary
    permits full eviction. Insertion-only policy is diagnostic, not a fallback.
    """
    def __init__(self, *, retention_policy='learning'):
        if retention_policy not in ('insertion','learning'):
            raise ValueError('TAGE retention policy must be insertion or learning')
        self.retention_policy = retention_policy
        self.records = {}
        self.pending = set()
        self.recency = [[0, 0, 0] for _ in range(WAYS)]
        self.sequence = self.overflows = 0

    def find(self, row, tag):
        return self.records.get((row, tag))

    def owner(self, write):
        old = self.find(write.row, write.entry.tag)
        return write.way if old is None else old.write.way

    def victim(self, owner):
        half, left, right = self.recency[owner]
        return 2 * half + (right if half else left)

    def touch(self, owner, rank):
        half, member = divmod(rank, 2)
        self.recency[owner][0] = 1 - half
        self.recency[owner][1 + half] = 1 - member

    def _plan(self, incoming):
        """Resolve all claims from one prestate, before retiring or learning."""
        plans, destinations = [], {}
        for offered in incoming:
            key = offered.row, offered.entry.tag
            old = self.records.get(key)
            owner = offered.way if old is None else old.write.way
            if old is not None:
                rank = old.rank
            else:
                same_destination = next((item for item in self.records.values()
                    if item.write.way == owner and item.write.row == offered.row), None)
                used = {item.rank for item in self.records.values()
                        if item.write.way == owner and item.sequence in self.pending}
                rank = same_destination.rank if same_destination is not None else next(
                    (rank for rank in range(4) if rank not in used), self.victim(owner))
            destination = owner, rank
            if destination in destinations:
                resident = next((item for item in self.records.values()
                    if (item.write.way, item.rank) == destination), None)
                raise LearningDestinationConflict(destination,
                    (destinations[destination], offered), resident)
            destinations[destination] = offered
            plans.append((offered, key, old, owner, rank))
        return tuple(plans)

    def advance(self, busy, incoming=()):
        before, pending = dict(self.records), set(self.pending)
        plans = self._plan(incoming)
        retired = []
        for owner in range(WAYS):
            candidates = sorted((item for item in before.values()
                if item.write.way == owner and item.sequence in pending), key=lambda item: item.rank)
            if candidates and not busy:
                item = candidates[0]
                retired.append(item.write)
                self.pending.remove(item.sequence)
        for offered, key, old, owner, rank in plans:
            if old is not None:
                entry = replace(offered.entry, counter=clamp(old.write.entry.counter + (1 if offered.taken else -1), 7))
                self.pending.discard(old.sequence)
                if self.retention_policy == 'learning':
                    self.touch(owner, rank)
            else:
                entry = offered.entry
                removed_key = next((key for key, item in self.records.items()
                                    if item.write.way == owner and item.rank == rank), None)
                if removed_key is not None:
                    removed = self.records.pop(removed_key)
                    if removed.sequence in self.pending:
                        self.pending.remove(removed.sequence)
                        self.overflows += 1
                self.touch(owner, rank)
            version = Version(self.sequence, rank, replace(offered, way=owner, entry=entry))
            self.sequence += 1
            self.records[key] = version
            self.pending.add(version.sequence)
        return tuple(retired)


@dataclass(frozen=True, slots=True)
class UsefulWrite:
    row: int
    value: int


class UsefulLearning:
    def __init__(self):
        self.pending = []
        self.drops = 0

    def advance(self, busy, incoming=None, *, flush=False):
        if flush:
            self.pending.clear()
            return None
        retiring = self.pending.pop(0) if self.pending and not busy else None
        if incoming is not None:
            if not busy and retiring is None:
                retiring = incoming
            elif len(self.pending) < 4:
                self.pending.append(incoming)
            else:
                self.drops += 1
        return retiring


@dataclass(frozen=True, slots=True)
class Base:
    valid: bool = False
    position: int = 0
    taken: bool = False
    confident: bool = False
    kind: int = 0

    def __post_init__(self):
        unsigned(self.position, 16, 'base position')
        unsigned(self.kind, 4, 'base kind')
        if any(type(value) is not bool for value in (self.valid, self.taken, self.confident)):
            raise ValueError('TAGE base requires semantic bools')


@dataclass(frozen=True, slots=True)
class Hint:
    provider: bool = False
    alternate: bool = False
    use_provider: bool = False
    table: int = 0
    way: int = 0
    counter: int = 0
    useful: int = 0
    alternative: bool = False
    confident: bool = False

    def __post_init__(self):
        for value, limit, name in ((self.table, TABLES, 'provider table'), (self.way, WAYS, 'provider way'),
                                  (self.counter, 8, 'provider confidence'), (self.useful, 4, 'useful')):
            unsigned(value, limit, name)
        if any(type(value) is not bool for value in (self.provider, self.alternate, self.use_provider,
                                                   self.alternative, self.confident)):
            raise ValueError('TAGE metadata must use semantic bools')
        if (self.use_provider or self.alternate) and not self.provider:
            raise ValueError('TAGE provider/alternate metadata must have a provider')


@dataclass(frozen=True, slots=True)
class Branch:
    position: int
    taken: bool
    kind: int
    mispredict: bool
    matched: bool
    base_counter: int = 0
    hint: Hint = Hint()

    def __post_init__(self):
        unsigned(self.position, 16, 'branch position')
        unsigned(self.kind, 4, 'branch kind')
        unsigned(self.base_counter, 4, 'base counter')
        if any(type(value) is not bool for value in (self.taken, self.mispredict, self.matched)):
            raise ValueError('TAGE feedback qualification must use semantic bools')


@dataclass(frozen=True, slots=True)
class Feedback:
    pc: int
    context: Context
    branches: tuple[Branch, ...]

    def __post_init__(self):
        unsigned(self.pc, 1 << 49, 'training halfword PC')
        if type(self.context) is not Context or type(self.branches) is not tuple or len(self.branches) > 8:
            raise ValueError('TAGE feedback requires an immutable context and at most eight branches')
        if any(type(branch) is not Branch for branch in self.branches):
            raise ValueError('TAGE feedback requires semantic branches, not signal wrappers')
        if len({branch.position for branch in self.branches}) != len(self.branches):
            raise ValueError('TAGE resolved positions must be unique')
        if sum(branch.mispredict for branch in self.branches) > 1:
            raise ValueError('TAGE feedback has at most one mispredicted branch')

    @property
    def reread(self):
        return any(branch.kind == 1 and branch.matched and (branch.mispredict or (
            not branch.hint.use_provider and branch.hint.alternate)) for branch in self.branches)


@dataclass(frozen=True, slots=True)
class Read:
    pc: int
    context: Context
    bank: int
    rows: tuple[int, ...]
    entries: tuple[tuple[Entry, ...], ...]
    useful: tuple[tuple[int, ...], ...]

    def matches(self, position):
        result = []
        for table in range(TABLES):
            intended = coordinate(self.pc, self.context, table)[2] ^ position
            ways = [way for way, entry in enumerate(self.entries[table]) if entry.valid and entry.tag == intended]
            if ways:
                way = ways[0]
                result.append((table, way, self.entries[table][way].counter, self.useful[table][way]))
        return tuple(result)

    def allocation(self, minimum, random_mask):
        """Prefer invalid, then weak unused, then any unused owner per table."""
        unsigned(minimum, TABLES + 1, 'minimum allocation history')
        unsigned(random_mask, 1 << TABLES, 'allocation table preference')
        candidates = {}
        for table in range(minimum, TABLES):
            entries, values = self.entries[table], self.useful[table]
            invalid = [way for way, entry in enumerate(entries) if not entry.valid]
            weak = [way for way, entry in enumerate(entries) if entry.counter in (3,4) and not values[way]]
            unused = [way for way, value in enumerate(values) if not value]
            available = invalid or weak or unused
            if available:
                candidates[table] = available[0]
        if not candidates:
            return None
        preferred = [table for table in candidates if random_mask & (1 << table)]
        table = min(preferred or list(candidates))
        return table, candidates[table]


@dataclass(frozen=True, slots=True)
class Frame:
    read: Read
    positions: tuple[int, ...]


def decide(frame, bases, selectors, *, enabled=True):
    expected = {}
    for slot, base in enumerate(bases):
        expected[f'{slot}.sc_valid'] = 0
        if not base.valid:
            continue
        matches = frame.read.matches(frame.positions[slot])
        provider = matches[-1] if matches else None
        alternate = matches[-2] if len(matches) > 1 else None
        alt_prediction = alternate[2] >= 4 if alternate is not None else base.taken
        confident = alternate[2] not in (3, 4) if alternate is not None else base.confident
        use_provider = provider is not None and not (provider[2] in (3, 4) and selectors[2 * provider[0] + int(confident)] >= 16)
        valid = bool(enabled and (use_provider or alternate is not None))
        expected.update({f'{slot}.valid': int(valid), f'{slot}.has_provider': int(provider is not None),
            f'{slot}.has_alt': int(alternate is not None), f'{slot}.use_provider': int(use_provider),
            f'{slot}.alternative': int(alt_prediction), f'{slot}.alt_conf': int(confident),
            f'{slot}.fast_valid': int(provider is not None)})
        if valid:
            expected[f'{slot}.taken'] = int(provider[2] >= 4 if use_provider else alternate[2] >= 4)
        if provider is not None:
            table, way, counter, useful = provider
            expected.update({f'{slot}.table': table, f'{slot}.way': way, f'{slot}.counter': counter,
                f'{slot}.useful': useful, f'{slot}.fast_taken': int(counter >= 4),
                f'{slot}.sc_valid': int(enabled)})
            if enabled:
                expected[f'{slot}.sc_counter'] = counter
    return expected


@dataclass(frozen=True, slots=True)
class Accepted:
    feedback: Feedback
    read: Read | None


@dataclass(frozen=True, slots=True)
class Outcome:
    branch: Branch
    provider: tuple | None
    alternate: tuple | None
    use_provider: bool
    alternative: bool
    confident: bool
    allocate: bool


@dataclass(frozen=True, slots=True)
class Learning:
    feedback: Feedback
    read: Read | None
    outcomes: tuple[Outcome, ...]


@dataclass(frozen=True, slots=True)
class Events:
    pc: int = 0
    context: Context = Context()
    positions: tuple[int, ...] = (0, 0, 0, 0)
    select: bool = False
    advance: bool = False
    feedback: Feedback | None = None
    enabled: bool = True
    ready: bool = True
    reset: bool = False

    def __post_init__(self):
        unsigned(self.pc, 1 << 49, 'halfword PC')
        if type(self.context) is not Context or type(self.positions) is not tuple or len(self.positions) != 4:
            raise ValueError('TAGE prediction requires a context and four fast positions')
        for position in self.positions:
            unsigned(position, 16, 'fast position')
        if any(type(value) is not bool for value in (self.select, self.advance, self.enabled, self.ready, self.reset)):
            raise ValueError('TAGE events require semantic bools')
        if self.feedback is not None and type(self.feedback) is not Feedback:
            raise ValueError('TAGE events require semantic feedback')


class TageReference:
    def __init__(self, *, retention_policy='learning'):
        if retention_policy not in ('insertion','learning'):
            raise ValueError('TAGE retention policy must be insertion or learning')
        self.retention_policy = retention_policy
        self.reset()

    def reset(self):
        self.memory, self.useful = {}, {}
        self.cache = {(table, bank): RecentLearning(retention_policy=self.retention_policy)
                      for table in range(TABLES) for bank in range(BANKS)}
        self.useful_queue = {(table, bank, way): UsefulLearning()
                            for table in range(TABLES) for bank in range(BANKS) for way in range(WAYS)}
        self.offers, self.useful_offers = {}, {}
        self.read = self.frame = self.accepted = self.info = self.mature = None
        self.selectors = [16] * 8
        self.random = 1
        self.tick = 0
        self.aging = False
        self.clear_cursor = {}
        self.cycles = self.feedbacks = self.allocations = self.failures = self.commits = 0

    def _read(self, pc, context):
        bank = pc % BANKS
        rows = tuple(coordinate(pc, context, table)[1] for table in range(TABLES))
        entries = tuple(tuple(self.memory.get((table, bank, row, way), Entry()) for way in range(WAYS))
                        for table, row in enumerate(rows))
        useful = tuple(tuple(0 if (table, bank) in self.clear_cursor else self.useful.get((table, bank, row, way), 0)
                             for way in range(WAYS)) for table, row in enumerate(rows))
        return Read(pc, context, bank, rows, entries, useful)

    def lookup_snapshot(self,pc,context):
        """Own an immutable prediction read without advancing model time."""
        unsigned(pc,1<<49,'prediction halfword PC')
        if type(context) is not Context:raise ValueError('prediction needs a semantic history context')
        return self._read(pc,context)

    def _describe(self, accepted):
        feedback, read = accepted.feedback, accepted.read
        outcomes = []
        for branch in feedback.branches:
            if branch.kind != 1 or not branch.matched:
                continue
            if read is None:
                hint = branch.hint
                provider = (hint.table, hint.way, hint.counter, hint.useful) if hint.provider else None
                alternate = None
                alternative, confident, use_provider = hint.alternative, hint.confident, hint.use_provider
            else:
                matches = read.matches(branch.position)
                provider = matches[-1] if matches else None
                alternate = matches[-2] if len(matches) > 1 else None
                alternative = alternate[2] >= 4 if alternate is not None else branch.base_counter >= 2
                confident = alternate[2] not in (3, 4) if alternate is not None else branch.base_counter in (0, 3)
                use_provider = provider is not None and not (provider[2] in (3, 4) and
                    self.selectors[2 * provider[0] + int(confident)] >= 16)
            final = provider[2] >= 4 if use_provider and provider is not None else alternative
            allocate = bool(branch.mispredict and final != branch.taken and
                not (provider is not None and (provider[0] == TABLES - 1 or
                    (not use_provider and provider[2] in (3, 4) and (provider[2] >= 4) == branch.taken))))
            outcomes.append(Outcome(branch, provider, alternate, use_provider, alternative, confident, allocate))
        return Learning(feedback, read, tuple(outcomes))

    def allocation_at_next_accept(self, feedback):
        """Plan a quiescent learning event using only owned state.

        The next accepted event passes through accepted -> info -> mature
        before scheduling; the independent generator advances at every step.
        This is a semantic pipeline forecast, not a sleep or an observed RTL
        allocation proposal. Callers must keep reads/configuration quiescent
        until acceptance; concurrent learning is explicitly unsupported here.
        """
        if type(feedback) is not Feedback or not feedback.reread:
            raise ValueError('allocation planning requires a semantic reread feedback')
        if any(value is not None for value in (self.accepted,self.info,self.mature)) or self.offers or self.useful_offers:
            raise ValueError('allocation planning requires quiescent learning')
        if self.aging or self.clear_cursor or any(cache.pending for cache in self.cache.values()) or any(
                queue.pending for queue in self.useful_queue.values()):
            raise ValueError('allocation planning requires committed learning and no maintenance')
        learning = self._describe(Accepted(feedback,self._read(feedback.pc,feedback.context)))
        allocating = [outcome for outcome in learning.outcomes if outcome.allocate]
        if len(allocating) > 1:
            raise ValueError('allocation planning permits only one allocating branch')
        if not allocating:
            return None
        provider = allocating[0].provider
        random = self.random
        for _ in range(3):
            random = lfsr_next(random)
        return learning.read.allocation(0 if provider is None else provider[0]+1,random % 16)

    def _schedule(self, learning, random_mask):
        feedback = learning.feedback
        bank = feedback.pc % BANKS
        writes, useful, votes = {}, {}, [0] * 8
        allocators = [outcome for outcome in learning.outcomes if outcome.allocate]
        if len(allocators) > 1:
            raise ValueError('TAGE one feedback beat can allocate only one branch')
        for outcome in learning.outcomes:
            branch, provider = outcome.branch, outcome.provider
            for role, source in (('provider', provider), ('alternate', outcome.alternate if not outcome.use_provider else None)):
                if source is None:
                    continue
                table, way, counter, old_useful = source
                _, row, raw_tag = coordinate(feedback.pc, feedback.context, table)
                intended = raw_tag ^ branch.position
                latest = self.cache[table, bank].find(row, intended)
                current = counter if latest is None else latest.write.entry.counter
                updated = clamp(current + (1 if branch.taken else -1), 7)
                proposal = clamp(counter + (1 if branch.taken else -1), 7)
                if proposal != counter or updated != current:
                    key = table, bank, way
                    if key in writes:
                        raise ValueError('TAGE feedback branches cannot update the same requested way')
                    writes[key] = Write(row, way, Entry(True, intended, proposal), branch.taken)
                if role == 'provider' and (counter >= 4) == branch.taken and (counter >= 4) != outcome.alternative and old_useful < 3:
                    useful[table, bank, way] = UsefulWrite(row, old_useful + 1)
            if provider is not None and provider[2] in (3, 4) and (provider[2] >= 4) != outcome.alternative:
                votes[2 * provider[0] + int(outcome.confident)] += 1 if outcome.alternative == branch.taken else -1
        failed = False
        if allocators:
            outcome = allocators[0]
            minimum = outcome.provider[0] + 1 if outcome.provider is not None else 0
            read = learning.read
            destination = read.allocation(minimum, random_mask)
            if destination is None:
                failed = True
                self.failures += 1
            else:
                table, way = destination
                _, row, raw_tag = coordinate(feedback.pc, feedback.context, table)
                branch = outcome.branch
                writes[table, bank, way] = Write(row, way,
                    Entry(True, raw_tag ^ branch.position, 4 if branch.taken else 3), branch.taken)
                useful[table, bank, way] = UsefulWrite(row, 0)
                self.allocations += 1
        for index, vote in enumerate(votes):
            self.selectors[index] = clamp(self.selectors[index] + vote, 31)
        start = self.tick == 255 and not self.aging
        if start:
            self.tick = 0
        elif failed and not self.aging:
            self.tick = min(255, self.tick + 1)
        return writes, useful, start

    def preview_learning(self):
        """Pure current learning offers, before the next boundary consumes them.

        Only _schedule's scalar accounting and selector votes need an owned
        copy. Memories and retained versions are read-only in this operation.
        """
        if self.mature is None:
            return {}, {}, False
        view=copy(self)
        view.selectors=list(self.selectors)
        return view._schedule(self.mature,self.random % 16)

    def advance(self, events=Events()):
        if events.reset:
            self.reset()
            return
        if events.ready:
            # An unsupported joint claim must not advance any other cache,
            # SRAM, useful queue, read pipeline, clock or allocation generator.
            for key, incoming in self.offers.items():
                if len(incoming) > 1:
                    self.cache[key]._plan(incoming)
        old_random = self.random
        self.random = lfsr_next(old_random)
        self.cycles += 1
        if not events.ready:
            return
        old_read, old_info, old_accepted = self.read, self.info, self.accepted
        reading = bool(events.select and events.enabled)
        read = self._read(events.pc, events.context) if reading else old_read
        feedback = events.feedback if events.enabled and events.feedback is not None and any(
            branch.kind == 1 for branch in events.feedback.branches) else None
        training_read = self._read(feedback.pc, feedback.context) if feedback is not None and feedback.reread else None
        if reading and training_read is not None and training_read.bank == read.bank:
            raise ValueError('TAGE accepted SRAM reread conflicts with prediction bank')
        busy = {read.bank} if reading else set()
        if training_read is not None:
            busy.add(training_read.bank)
        if events.advance and events.enabled and old_read is not None:
            self.frame = Frame(old_read, events.positions)
        self.read = read
        for (table, bank), cache in self.cache.items():
            for retired in cache.advance(bank in busy, self.offers.get((table, bank), ())):
                self.memory[table, bank, retired.row, retired.way] = retired.entry
                self.commits += 1
        writes, useful, start = self._schedule(self.mature, old_random % 16) if self.mature is not None else ({}, {}, False)
        for key, queue in self.useful_queue.items():
            table, bank, way = key
            retiring = queue.advance(bank in busy, self.useful_offers.get(key), flush=start or (table, bank) in self.clear_cursor)
            if retiring is not None:
                self.useful[table, bank, retiring.row, way] = retiring.value
        if start:
            for table in range(TABLES):
                for bank in range(BANKS):
                    if bank not in busy:
                        for way in range(WAYS):
                            self.useful[table, bank, 0, way] = 0
                    self.clear_cursor[table, bank] = 0
            self.aging = True
        else:
            was_active = bool(self.clear_cursor)
            for (table, bank), row in tuple(self.clear_cursor.items()):
                for way in range(WAYS):
                    self.useful[table, bank, row, way] = 0
                if row == ROWS - 1:
                    del self.clear_cursor[table, bank]
                else:
                    self.clear_cursor[table, bank] = row + 1
            if self.aging and not was_active:
                self.aging = False
        entry_offers, useful_offers = {}, {}
        for (table, bank, way), write in writes.items():
            entry_offers.setdefault((table, bank), []).append(write)
        for (table, bank, way), write in useful.items():
            identity = writes.get((table, bank, way))
            if identity is None:
                # Useful-only provider learning has no entry write, but still
                # belongs to its independently computed logical tag identity.
                outcome = next(outcome for outcome in self.mature.outcomes if outcome.provider is not None
                               and outcome.provider[:2] == (table, way))
                intended = coordinate(self.mature.feedback.pc, self.mature.feedback.context, table)[2] ^ outcome.branch.position
                identity = Write(write.row, way, Entry(True, intended), outcome.branch.taken)
            owner = self.cache[table, bank].owner(identity)
            if (table, bank, owner) in useful_offers:
                raise ValueError('TAGE useful updates cannot share a retained owner')
            useful_offers[table, bank, owner] = write
        self.offers = {key: tuple(value) for key, value in entry_offers.items()}
        self.useful_offers = useful_offers
        self.mature = old_info
        self.info = self._describe(old_accepted) if old_accepted is not None else None
        self.accepted = Accepted(feedback, training_read) if feedback is not None else None
        self.feedbacks += int(feedback is not None)

    def state(self):
        return dict(cycles=self.cycles, accepted_feedback=self.feedbacks, allocations=self.allocations,
            failures=self.failures, commits=self.commits, populated=len(self.memory), random=self.random,
            tick=self.tick, aging=self.aging, clear_cursors=dict(self.clear_cursor),
            selectors=tuple(self.selectors), accepted=self.accepted, info=self.info, mature=self.mature, frame=self.frame)
