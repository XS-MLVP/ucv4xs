"""Independent MainBTB branch records and versioned visibility contracts.

MinimalConfig: two eight-halfword alignment windows, two internal banks,
64 rows, two ways, 16-bit tags and 20-bit local targets with adjacent-region
carry. No DUT objects, actual SRAM/counter state or old prepared snapshots
enter this model. Metadata is a declared upstream input at the isolated UT.

Entry coalescing owns a logical (row, tag, position) record. Direction learning
requires a matching conditional source; resetting a coalesced record belongs
to its retained owner, not an unrelated nominated allocation way. Feedback
counter snapshots are checked prediction provenance, not observed SRAM seeds.
"""
from dataclasses import dataclass, replace


ALIGNMENTS, INTERNAL_BANKS, ROWS, WAYS = 2, 2, 64, 2
ADDRESS_LIMIT, TARGET_SPAN, TAG_SPAN = 1 << 49, 1 << 20, 1 << 16


def unsigned(value, limit, name):
    if type(value) is not int or not 0 <= value < limit:
        raise ValueError(f'MBTB {name} must be an unsigned integer below {limit}')


def coordinate(pc):
    unsigned(pc, ADDRESS_LIMIT, 'halfword PC')
    return (pc // 8) % 2, (pc // 16) % 2, (pc // 32) % ROWS


def tag(pc):
    unsigned(pc, ADDRESS_LIMIT, 'halfword PC')
    return (pc // (8 * ALIGNMENTS * INTERNAL_BANKS * ROWS)) % TAG_SPAN


def replacement_row(pc):
    return (pc // 16) % ROWS


def window(pc):
    """Physical alignment -> (address, ordinal); not a packed rotate network."""
    unsigned(pc, ADDRESS_LIMIT, 'halfword PC')
    values = [None] * ALIGNMENTS
    for ordinal in range(ALIGNMENTS):
        address = pc if ordinal == 0 else ((pc // 8 + ordinal) * 8) % ADDRESS_LIMIT
        values[coordinate(address)[0]] = address, ordinal
    return tuple(values)


@dataclass(frozen=True, slots=True)
class Target:
    offset: int = 0
    region_delta: int = 0

    @classmethod
    def encode(cls, pc, target):
        unsigned(target, ADDRESS_LIMIT, 'halfword target')
        difference = target // TARGET_SPAN - pc // TARGET_SPAN
        return cls(target % TARGET_SPAN, (difference > 0) - (difference < 0))

    def at(self, pc):
        region = (pc // TARGET_SPAN + self.region_delta) % (ADDRESS_LIMIT // TARGET_SPAN)
        return region * TARGET_SPAN + self.offset


@dataclass(frozen=True, slots=True)
class Entry:
    tag: int = 0
    position: int = 0
    kind: int = 0
    action: int = 0
    target: Target = Target()

    @property
    def valid(self):
        return self.kind != 0


@dataclass(frozen=True, slots=True)
class Source:
    hit: bool = False
    position: int = 0
    kind: int = 0
    action: int = 0
    counter: int = 0

    def __post_init__(self):
        if type(self.hit) is not bool:
            raise ValueError('MBTB source hit must be a semantic bool')
        for value, limit, name in ((self.position, 16, 'position'), (self.kind, 4, 'kind'),
                                  (self.action, 4, 'stack action'), (self.counter, 4, 'direction counter')):
            unsigned(value, limit, name)


@dataclass(frozen=True, slots=True)
class Branch:
    target: int
    taken: bool
    position: int
    kind: int
    action: int = 0
    mispredict: bool = False

    def __post_init__(self):
        for value, limit, name in ((self.target, ADDRESS_LIMIT, 'halfword target'),
            (self.position, 16, 'position'), (self.kind, 4, 'kind'), (self.action, 4, 'stack action')):
            unsigned(value, limit, name)
        if type(self.taken) is not bool or type(self.mispredict) is not bool:
            raise ValueError('MBTB outcome and feedback qualification require semantic bools')


@dataclass(frozen=True, slots=True)
class Feedback:
    pcs: tuple[int, int]
    sources: tuple[tuple[Source, ...], ...]
    branches: tuple[Branch, ...]

    def __post_init__(self):
        if type(self.pcs) is not tuple or len(self.pcs) != ALIGNMENTS:
            raise ValueError('MBTB feedback requires two public window addresses')
        for pc in self.pcs:
            unsigned(pc, ADDRESS_LIMIT, 'halfword PC')
        if self.pcs[1] != ((self.pcs[0] // 8 + 1) * 8) % ADDRESS_LIMIT:
            raise ValueError('MBTB feedback windows must be contiguous')
        if type(self.sources) is not tuple or len(self.sources) != ALIGNMENTS or any(
            type(row) is not tuple or len(row) != WAYS or any(type(source) is not Source for source in row)
            for row in self.sources):
            raise ValueError('MBTB feedback requires two pairs of immutable semantic sources')
        if type(self.branches) is not tuple or len(self.branches) > 8 or any(type(branch) is not Branch for branch in self.branches):
            raise ValueError('MBTB feedback requires at most eight semantic branches')
        if len({branch.position for branch in self.branches}) != len(self.branches):
            raise ValueError('MBTB feedback cannot resolve one position twice')
        if sum(branch.mispredict for branch in self.branches) > 1:
            raise ValueError('MBTB feedback permits only one entry correction')


@dataclass(frozen=True, slots=True)
class Write:
    row: int
    way: int
    entry: Entry | None  # None is an explicit destination invalidation.


@dataclass(frozen=True, slots=True)
class Version:
    sequence: int
    rank: int
    write: Write


class RetainedEntries:
    """Logical identity -> owner/version, with two service ranks per owner.

    Same-record updates preserve the owner; same-destination replacement
    supersedes only that destination. Completed versions remain reusable.
    Explicit invalidations are destination operations, not tag-zero aliases.
    A non-backpressured full miss can evict a service rank; that capacity
    boundary is separate from the in-capacity ownership invariants.
    Concurrent hits reserve their existing capacity before any new obligation
    allocates. Distinct requests may resolve to the same service owner, so
    allocating independently from the old free set would silently lose work.
    """
    def __init__(self):
        self.records = {}
        self.outstanding = set()
        self.oldest_rank = [0] * WAYS
        self.sequence = self.overflows = 0

    @staticmethod
    def key(write):
        return ('clear', write.row, write.way) if write.entry is None else (
            'branch', write.row, write.entry.tag, write.entry.position)

    def owner(self, write):
        version = self.records.get(self.key(write))
        return write.way if version is None else version.write.way

    def advance(self, busy, incoming=()):
        before = dict(self.records)
        old_pending = set(self.outstanding)
        requests=[]
        for offered in incoming:
            key=self.key(offered)
            prior=before.get(key)
            owner=offered.way if prior is None or offered.entry is None else prior.write.way
            requests.append((key,prior,owner,replace(offered,way=owner)))
        if len(requests)>2 or len({key for key,_,_,_ in requests})!=len(requests):
            raise ValueError('at most two distinct Main entry obligations may be accepted together')
        reserved={(owner,prior.rank) for _,prior,owner,offered in requests
            if prior is not None and (prior.sequence in old_pending or prior.write!=offered)}
        retired = []
        for owner in range(WAYS):
            ready = sorted((version for version in before.values()
                if version.write.way == owner and version.sequence in old_pending), key=lambda version: version.rank)
            if ready and not busy:
                version = ready[0]
                retired.append(version.write)
                self.outstanding.remove(version.sequence)
        for key,prior,owner,offered in requests:
            if prior is not None and prior.sequence not in old_pending and prior.write == offered:
                continue
            if prior is not None:
                rank = prior.rank
                self.outstanding.discard(prior.sequence)
            else:
                same_destination = next((item for item in before.values()
                    if item.write.way == owner and item.write.row == offered.row), None)
                pending_ranks = {item.rank for item in before.values()
                    if item.write.way == owner and item.sequence in old_pending}
                candidates=[rank for rank in range(2) if (owner,rank) not in reserved]
                if same_destination is not None:
                    rank=same_destination.rank
                    if (owner,rank) in reserved:
                        raise ValueError('simultaneous replacement of the same SRAM destination needs explicit priority')
                else:
                    if not candidates:raise ValueError('same-cycle Main obligations exceed owner capacity')
                    available=[rank for rank in candidates if rank not in pending_ranks]
                    rank=(available[0] if available else self.oldest_rank[owner]
                        if self.oldest_rank[owner] in candidates else candidates[0])
                reserved.add((owner,rank))
                removed_key = next((old_key for old_key, item in self.records.items()
                                   if item.write.way == owner and item.rank == rank), None)
                if removed_key is not None:
                    removed = self.records.pop(removed_key)
                    if removed.sequence in self.outstanding:
                        self.outstanding.remove(removed.sequence)
                        self.overflows += 1
                self.oldest_rank[owner] = 1 - rank
            version = Version(self.sequence, rank, offered)
            self.sequence += 1
            self.records[key] = version
            self.outstanding.add(version.sequence)
        return tuple(retired)


@dataclass(frozen=True, slots=True)
class CounterPatch:
    row: int
    values: tuple[int | None, ...]


class DirectionWrites:
    """Depth-two FIFO, empty flow-through and full simultaneous retirement."""
    def __init__(self):
        self.pending = []
        self.drops = 0

    def advance(self, busy, incoming=None):
        retiring = self.pending.pop(0) if self.pending and not busy else None
        if incoming is not None:
            if not busy and retiring is None:
                retiring = incoming
            elif len(self.pending) < 2:
                self.pending.append(incoming)
            else:
                self.drops += 1
        return retiring


@dataclass(frozen=True, slots=True)
class BankRead:
    pc: int
    ordinal: int
    bank: int
    row: int
    entries: tuple[Entry, ...]
    counters: tuple[int, ...]
    cross_page: bool


@dataclass(frozen=True, slots=True)
class Frame:
    pc: int
    banks: tuple[BankRead, ...]

    def values(self, enabled=True):
        values = {}
        for alignment, read in enumerate(self.banks):
            for way, (entry, counter) in enumerate(zip(read.entries, read.counters, strict=True)):
                slot = alignment * WAYS + way
                raw_hit = entry.valid and entry.tag == tag(read.pc)
                position = read.ordinal * 8 + entry.position
                visible = raw_hit and entry.position >= read.pc % 8 and not read.cross_page
                values[f'{slot}.valid'] = int(visible)
                values[f'{slot}.raw_hit'] = int(raw_hit and enabled)
                if raw_hit and enabled:
                    values.update({f'{slot}.meta_position': position, f'{slot}.meta_kind': entry.kind,
                        f'{slot}.meta_action': entry.action, f'{slot}.counter': counter})
                if visible:
                    values.update({f'{slot}.taken': int(counter >= 2), f'{slot}.target': entry.target.at(read.pc),
                        f'{slot}.position': position, f'{slot}.kind': entry.kind, f'{slot}.action': entry.action})
        return values


@dataclass(frozen=True, slots=True)
class Accepted:
    feedback: Feedback
    victims: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Events:
    pc: int = 0
    select: bool = False
    advance: bool = False
    consume: bool = False
    feedback: Feedback | None = None
    enabled: bool = True
    ready: bool = True
    reset: bool = False

    def __post_init__(self):
        unsigned(self.pc, ADDRESS_LIMIT, 'halfword PC')
        if any(type(value) is not bool for value in (self.select, self.advance, self.consume,
                                                    self.enabled, self.ready, self.reset)):
            raise ValueError('MBTB events require semantic bools, not signal wrappers')
        if self.feedback is not None and type(self.feedback) is not Feedback:
            raise ValueError('MBTB event feedback requires a semantic Feedback')


class MbtbReference:
    def __init__(self):
        self.reset()

    def reset(self):
        self.memory, self.counters, self.recency = {}, {}, {}
        self.entries = {(align, bank): RetainedEntries() for align in range(2) for bank in range(2)}
        self.directions = {(align, bank): DirectionWrites() for align in range(2) for bank in range(2)}
        self.entry_offers = {key: () for key in self.entries}
        self.offered = self.read = self.frame = None
        self.cleanup = {}
        self.cycles = self.accepted_feedback = self.entry_commits = self.counter_commits = 0

    def _read(self, pc):
        banks = []
        for alignment, (address, ordinal) in enumerate(window(pc)):
            _, bank, row = coordinate(address)
            banks.append(BankRead(address, ordinal, bank, row,
                tuple(self.memory.get((alignment, bank, row, way), Entry()) for way in range(WAYS)),
                tuple(self.counters.get((alignment, bank, row, way), 0) for way in range(WAYS)),
                address // 2048 != pc // 2048))
        return Frame(pc, tuple(banks))

    def lookup_snapshot(self,pc):
        """Capture an immutable owned lookup without advancing model time."""
        return self._read(pc)

    def direction_proposals(self):
        """Pure next learning effects, before any SRAM service is accepted.

        Entry ownership determines which allocated counter resets; updates
        require a genuinely matching original conditional source. A miss's
        unqualified payload position cannot grant an unrelated update.
        """
        if self.offered is None:
            return {}
        _, patches, _ = self._learning_effects(self.offered)
        return patches

    def _learn(self, accepted):
        writes, patches, touches = self._learning_effects(accepted)
        self.recency.update(touches)
        return writes, patches

    def _learning_effects(self, accepted):
        """Compute owned effects without advancing queues, history or recency."""
        feedback = accepted.feedback
        writes, patches, touches = {}, {}, {}
        selected = next((branch for branch in feedback.branches if branch.mispredict), None)
        for alignment, (pc, ordinal) in enumerate(window(feedback.pcs[0])):
            # Use independently validated public training windows, not a DUT
            # internal bank/select/way packet.
            pc = feedback.pcs[ordinal]
            _, bank, row = coordinate(pc)
            sources = feedback.sources[alignment]
            correction = selected if selected is not None and selected.position // 8 == ordinal else None
            write = None
            reset_owner = None
            nominated = None
            if correction is not None:
                matching = [way for way, source in enumerate(sources)
                            if source.hit and source.position == correction.position]
                first = matching[0] if matching else None
                needs_entry = first is None or (correction.kind == 3 and correction.action in (0, 2)) or (
                    sources[first].kind, sources[first].action) != (correction.kind, correction.action)
                if needs_entry:
                    nominated = accepted.victims[alignment] if first is None else first
                    entry = Entry(tag(pc), correction.position % 8, correction.kind, correction.action,
                                  Target.encode(pc, correction.target))
                    write = Write(row, nominated, entry)
                    reset_owner = self.entries[alignment, bank].owner(write)
                    writes[alignment, bank] = write
            values = [None] * WAYS
            for way, source in enumerate(sources):
                resolved = next((branch for branch in feedback.branches if branch.kind == 1
                                 and branch.position == source.position), None)
                if source.hit and source.kind == 1 and resolved is not None:
                    values[way] = max(0, min(3, source.counter + (1 if resolved.taken else -1)))
            if reset_owner is not None:
                values[reset_owner] = 2
            if any(value is not None for value in values):
                patches[alignment, bank] = CounterPatch(row, tuple(values))
            touch = nominated
            if touch is None:
                touch = next((way for way, source in enumerate(sources) if source.hit
                    and any(branch.position == source.position and branch.taken for branch in feedback.branches)), None)
            if touch is not None:
                touches[alignment, replacement_row(pc)] = 1 - touch
        return writes, patches, touches

    def advance(self, events=Events()):
        if events.reset:
            self.reset()
            return
        self.cycles += 1
        if not events.ready:
            return
        previous_read, previous_frame = self.read, self.frame
        read = self._read(events.pc) if events.select and events.enabled else previous_read
        busy = {(alignment, coordinate(address)[1]) for alignment, (address, _) in enumerate(window(events.pc))}
        if not events.select or not events.enabled:
            busy = set()
        if events.advance and events.enabled and previous_read is not None:
            self.frame = previous_read
        self.read = read

        for key, cache in self.entries.items():
            for retired in cache.advance(key in busy, self.entry_offers[key]):
                self.memory[*key, retired.row, retired.way] = retired.entry if retired.entry is not None else Entry()
                self.entry_commits += 1
        writes, patches = self._learn(self.offered) if self.offered is not None else ({}, {})
        for key, queue in self.directions.items():
            retired = queue.advance(key in busy, patches.get(key))
            if retired is not None:
                for way, value in enumerate(retired.values):
                    if value is not None:
                        self.counters[*key, retired.row, way] = value
                self.counter_commits += 1

        # Each accepted duplicate observation owns a cleanup obligation.
        # A same-port training conflict defers it, not silently discards it.
        if events.consume and previous_frame is not None:
            for alignment, bank_read in enumerate(previous_frame.banks):
                matching = [(way, entry) for way, entry in enumerate(bank_read.entries)
                    if entry.valid and entry.tag == tag(bank_read.pc) and entry.position >= bank_read.pc % 8
                    and not bank_read.cross_page]
                if len(matching) == 2 and matching[0][1].position == matching[1][1].position:
                    way = matching[1][0]
                    key = alignment, bank_read.bank, bank_read.row, way
                    self.cleanup[key] = Write(bank_read.row, way, None)
        offers = {key: [] for key in self.entries}
        for key, write in writes.items():
            offers[key].append(write)
        for key, clear in tuple(self.cleanup.items()):
            physical = key[:2]
            if not any(write.way == clear.way for write in offers[physical]):
                offers[physical].append(clear)
                del self.cleanup[key]
        self.entry_offers = {key: tuple(value) for key, value in offers.items()}
        self.offered = None
        if events.enabled and events.feedback is not None:
            victims = tuple(self.recency.get((align, replacement_row(pc)), 1)
                for align, (pc, _) in enumerate(window(events.feedback.pcs[0])))
            self.offered = Accepted(events.feedback, victims)
            self.accepted_feedback += 1

    def state(self):
        return dict(cycle=self.cycles, accepted_feedback=self.accepted_feedback,
            populated_cells=sum(entry.valid for entry in self.memory.values()),
            entry_commits=self.entry_commits, counter_commits=self.counter_commits,
            entry_pending={key: len(cache.outstanding) for key, cache in self.entries.items()},
            counter_pending={key: len(queue.pending) for key, queue in self.directions.items()},
            deferred_cleanup=tuple(self.cleanup), offered=self.offered, frame=self.frame)
