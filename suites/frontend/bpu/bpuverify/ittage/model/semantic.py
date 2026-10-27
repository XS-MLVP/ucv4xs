"""Independent banked indirect-target cache and its visibility contract.

The model owns all entries and target regions. Inputs are public prediction
advances, folded contexts and accepted branch feedback, not SRAM contents,
internal hits, counter registers or write-buffer packets sampled from the DUT.
Random allocation is specified as an independently computed legal set. A
checked choice may subsequently be an upstream training input.

Scope: DefaultConfig's five direct-mapped tables, two banks, 9-bit tags,
2-bit confidence, one useful bit, four-entry write caches and 16 PLRU regions.
The public API uses byte addresses; zero-confidence learning preserves the
actual target semantics even when the RTL's compressed encoding fails.
"""
from dataclasses import dataclass, fields, replace

from bpuverify.common.model.configuration import ITTAGE_ROWS, ITTAGE_HISTORIES, ITTAGE_TAG_BITS, PHR_BITS

from bpuverify.ittage.model.region import IttageRegionModel


SETS = ITTAGE_ROWS
HISTORY_LENGTHS = ITTAGE_HISTORIES
REGION_WIDTH = 20
ADDRESS_LIMIT = 1 << 50  # The unguarded PC addr port is49 pruned bits.


def unsigned(value, limit, name):
    if type(value) is not int or not 0 <= value < limit:
        raise ValueError(f'{name} must be an unsigned value below {limit}')


@dataclass(frozen=True, slots=True)
class Context:
    """Per-table index, tag and secondary-tag folds; ordinary upstream data."""
    folds: tuple[tuple[int, int, int], ...] = ((0, 0, 0),) * len(SETS)

    def __post_init__(self):
        if len(self.folds) != len(SETS) or any(len(row) != 3 for row in self.folds):
            raise ValueError('each configured table requires three folded operands')
        for table, row in enumerate(self.folds):
            widths = (min(HISTORY_LENGTHS[table], SETS[table].bit_length() - 1),
                      min(HISTORY_LENGTHS[table], ITTAGE_TAG_BITS), min(HISTORY_LENGTHS[table], ITTAGE_TAG_BITS-1))
            for value, width in zip(row, widths, strict=True):
                unsigned(value, 1 << width, 'folded context')

    @classmethod
    def from_recent(cls, recent):
        unsigned(recent, 1 << PHR_BITS, 'recent path history')
        def fold(length, width):
            value = 0
            for bit in range(length):
                value ^= ((recent >> bit) & 1) << (bit % width)
            return value
        return cls(tuple((fold(length, min(length, sets.bit_length() - 1)),
                          fold(length, min(length, ITTAGE_TAG_BITS)), fold(length, min(length, ITTAGE_TAG_BITS-1)))
                         for length, sets in zip(HISTORY_LENGTHS, SETS, strict=True)))


def coordinates(pc, context, table):
    unsigned(pc, ADDRESS_LIMIT, 'PC')
    unsigned(table, len(SETS), 'table')
    if pc & 1:
        raise ValueError('ITTAGE PC must be halfword aligned')
    index_fold, tag_fold, secondary = context.folds[table]
    halfword = pc // 2
    index = ((halfword // 2) ^ index_fold) % SETS[table]
    tag = ((halfword // (2 * SETS[table])) ^ tag_fold ^ (secondary * 2)) % (1 << ITTAGE_TAG_BITS)
    return halfword % 2, index, tag


@dataclass(frozen=True, slots=True)
class Target:
    offset: int = 0
    pointer: int | None = None  # None uses the lookup PC's region.


@dataclass(frozen=True, slots=True)
class Entry:
    valid: bool = False
    tag: int = 0
    confidence: int = 0
    useful: int = 0
    target: Target = Target()


@dataclass(frozen=True, slots=True)
class Patch:
    """Semantic field update, not a packed bitmask or a get/set pin operation."""
    valid: bool | None = None
    tag: int | None = None
    confidence: int | None = None
    useful: int | None = None
    target: Target | None = None

    def apply(self, entry):
        return replace(entry, **{field.name: getattr(self, field.name) for field in fields(self)
                                 if getattr(self, field.name) is not None})

    def merge(self, newer):
        # An in-flight useful-only clear must not erase an older target write.
        return Patch(**{field.name: (getattr(newer, field.name) if getattr(newer, field.name) is not None
                                    else getattr(self, field.name)) for field in fields(self)})


@dataclass(frozen=True, slots=True)
class Write:
    table: int
    bank: int
    index: int
    patch: Patch


@dataclass(frozen=True, slots=True)
class CachedWrite:
    index: int
    patch: Patch
    dirty: bool = True


class WriteCache:
    """Four logical slots: oldest numbered dirty slot drains first.

    Completed shadows remain reusable. New keys prefer a clean slot; an
    explicitly non-backpressured full miss may replace a pending PLRU victim.
    Same-address pending semantic updates compose instead of dropping fields.
    Heap-order recency deliberately differs from the implementation encoding.
    """
    def __init__(self):
        self.slots = [None] * 4
        self.older = [0] * 3
        self.overwrites = 0

    def _victim(self):
        side = self.older[0]
        return 2 * side + self.older[1 + side]

    def _touch(self, slot):
        side = slot // 2
        self.older[0] = 1 - side
        self.older[1 + side] = 1 - slot % 2

    def advance(self, *, read_busy, incoming=None):
        before = tuple(self.slots)
        dirty = [index for index, slot in enumerate(before) if slot is not None and slot.dirty]
        drain = before[dirty[0]] if dirty and not read_busy else None
        if drain is not None:
            self.slots[dirty[0]] = replace(drain, dirty=False)
        if incoming is not None:
            address, patch = incoming
            hit = next((index for index, slot in enumerate(before)
                        if slot is not None and slot.index == address), None)
            if hit is not None:
                old = before[hit]
                updated = old.patch.merge(patch) if old.dirty else patch
                if old.dirty or updated != old.patch:
                    self.slots[hit] = CachedWrite(address, updated)
            else:
                slot = next((index for index, entry in enumerate(before)
                             if entry is None or not entry.dirty), self._victim())
                if len(dirty) == 4:
                    self.overwrites += 1
                self.slots[slot] = CachedWrite(address, patch)
                self._touch(slot)
        return drain


@dataclass(frozen=True, slots=True)
class Metadata:
    provider: int | None = None
    confidence: int = 0
    useful: int = 0
    provider_target: int = 0
    alternate: int | None = None
    alternate_confidence: int = 0
    alternate_target: int = 0
    differs: bool = False
    allocation: int | None = None
    published: bool = True  # The original query published this snapshot.

    def __post_init__(self):
        for name in ('provider', 'alternate', 'allocation'):
            value = getattr(self, name)
            if value is not None:
                unsigned(value, len(SETS), name)
        unsigned(self.confidence, 4, 'confidence')
        unsigned(self.alternate_confidence, 4, 'alternate confidence')
        unsigned(self.useful, 2, 'useful')
        unsigned(self.provider_target, ADDRESS_LIMIT, 'provider target')
        unsigned(self.alternate_target, ADDRESS_LIMIT, 'alternate target')
        if type(self.published) is not bool:
            raise TypeError('published must be Boolean')


@dataclass(frozen=True, slots=True)
class Outcome:
    pc: int
    context: Context
    metadata: Metadata
    target: int
    taken: bool = True
    indirect: bool = True
    returns: bool = False
    valid: bool = True
    mispredict: bool = False

    def __post_init__(self):
        unsigned(self.pc, ADDRESS_LIMIT, 'feedback PC')
        unsigned(self.target, ADDRESS_LIMIT, 'feedback target')
        if self.pc & 1 or self.target & 1:
            raise ValueError('ITTAGE addresses must be halfword aligned')
        if not isinstance(self.context, Context) or not isinstance(self.metadata, Metadata):
            raise TypeError('feedback requires semantic Context and Metadata')
        for name in ('taken', 'indirect', 'returns', 'valid', 'mispredict'):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f'{name} must be Boolean')

    @property
    def qualified(self):
        # A feedback beat can only teach from the snapshot its own prediction
        # published. An unpublished snapshot has no semantic provider or
        # allocation candidate, even if unrelated register residue is visible.
        return (self.valid and self.taken and self.indirect and not self.returns
                and self.metadata.published)


@dataclass(frozen=True, slots=True)
class Events:
    pc: int | None = None          # Accepted fetch start (S0).
    context: Context = Context()   # Context used by the next table access (S1).
    access: bool = False
    select: bool = False
    feedback: Outcome | None = None
    enabled: bool = True
    ready: bool = True            # Public initialization-complete handshake.
    reset: bool = False

    def __post_init__(self):
        if not isinstance(self.context, Context):
            raise TypeError('prediction context must be semantic Context')
        if self.feedback is not None and not isinstance(self.feedback, Outcome):
            raise TypeError('feedback must be semantic Outcome or None')
        for name in ('access', 'select', 'enabled', 'ready', 'reset'):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f'{name} must be Boolean')


@dataclass(frozen=True, slots=True)
class Read:
    pc: int
    context: Context
    entries: tuple[Entry, ...]
    tags: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Prediction:
    pc: int
    context: Context
    provider: int | None
    confidence: int
    useful: int
    provider_target: int
    alternate: int | None
    alternate_confidence: int
    alternate_target: int
    candidates: tuple[int, ...]

    @property
    def target(self):
        return self.alternate_target if self.provider is not None and self.confidence == 0 and self.alternate is not None else self.provider_target


class IttageReference:
    def __init__(self):
        self.reset()

    def reset(self):
        self.memories = [[{} for _ in range(2)] for _ in SETS]
        self.caches = [[WriteCache() for _ in range(2)] for _ in SETS]
        self.regions = IttageRegionModel()
        self.fetch_pc = None
        self.read = None
        self.prediction = None
        self.learning = None
        self.normal = ()
        self.tick = 0
        self.clear_start = False
        self.maintenance = [(False, 0) for _ in SETS]
        self.commits = 0

    def _decode(self, pc, target):
        if target.pointer is None:
            return (pc // (1 << REGION_WIDTH)) * (1 << REGION_WIDTH) + target.offset
        return self.regions.decode(target.pointer, target.offset)

    def _existing_target(self, pc, target):
        region = target // (1 << REGION_WIDTH)
        pointer = next((index for index, value in enumerate(self.regions.regions) if value == region), None)
        if pointer is None and region != pc // (1 << REGION_WIDTH):
            # Metadata is an upstream source snapshot. Preserve its target,
            # rather than silently substitute the training PC's high bits.
            pointer = self.regions.allocate(target).pointer
        return Target(target % (1 << REGION_WIDTH), pointer)

    def _selection(self, read):
        matched = [table for table, entry in enumerate(read.entries)
                   if entry.valid and entry.tag == read.tags[table]]
        provider = matched[-1] if matched else None
        alternate = matched[-2] if len(matched) > 1 else None
        entry = Entry() if provider is None else read.entries[provider]
        alt = Entry() if alternate is None else read.entries[alternate]
        candidates = tuple(table for table, candidate in enumerate(read.entries)
                           if table not in matched and not candidate.useful and
                           (provider is None or table > provider))
        return Prediction(read.pc, read.context, provider, entry.confidence, entry.useful,
                          0 if provider is None else self._decode(read.pc, entry.target),
                          alternate, alt.confidence,
                          0 if alternate is None else self._decode(read.pc, alt.target), candidates)

    def lookup_snapshot(self, pc, context=Context()):
        """Pure request-owned table read, before any later region selection."""
        entries, tags = [], []
        for table in range(len(SETS)):
            bank, index, tag = coordinates(pc, context, table)
            entries.append(self.memories[table][bank].get(index, Entry()))
            tags.append(tag)
        return Read(pc, context, tuple(entries), tuple(tags))

    def predict_snapshot(self, read):
        """Select from an immutable table read using the current owned regions."""
        if type(read) is not Read:raise TypeError('ITTAGE selection requires an independent Read')
        return self._selection(read)

    def inspect(self, pc, context=Context()):
        """Quiescent table prediction; no state or recency change from reads."""
        return self.predict_snapshot(self.lookup_snapshot(pc,context))

    def _learn(self, feedback):
        if feedback is None or not feedback.qualified:
            return ()
        meta, target = feedback.metadata, feedback.target
        allocate = feedback.mispredict and not (
            meta.provider is not None and meta.confidence == 0 and meta.provider_target == target)
        destination = meta.allocation if allocate else None
        if destination is not None and meta.provider is not None and destination <= meta.provider:
            raise ValueError('allocation must be longer than the provider')
        planned = {}
        # Preserve metadata targets before a new allocation changes the region
        # directory. Directory capacity aliasing is explicit model state.
        old_targets = {}
        if meta.provider is not None:
            old_targets[meta.provider] = self._existing_target(feedback.pc, meta.provider_target)
        used_alt = meta.provider is not None and meta.alternate is not None and meta.confidence == 0
        if used_alt and feedback.mispredict:
            old_targets[meta.alternate] = self._existing_target(feedback.pc, meta.alternate_target)
        new_target = None
        if destination is not None or (meta.provider is not None and meta.confidence == 0) or (
                used_alt and feedback.mispredict and meta.alternate_confidence == 0):
            if target // (1 << REGION_WIDTH) == feedback.pc // (1 << REGION_WIDTH):
                new_target = Target(target % (1 << REGION_WIDTH))
            else:
                # Target learning, not just table allocation, must retain the
                # actual region. A forced-PC fallback is not correct learning.
                new_target = Target(target % (1 << REGION_WIDTH), self.regions.allocate(target).pointer)
        if meta.provider is not None:
            correct = meta.provider_target == target
            count = min(3, meta.confidence + 1) if correct else max(0, meta.confidence - 1)
            useful = int(correct) if meta.differs else meta.useful
            planned[meta.provider] = (count, useful,
                new_target if meta.confidence == 0 else old_targets[meta.provider])
            if used_alt and feedback.mispredict:
                planned[meta.alternate] = (max(0, meta.alternate_confidence - 1), None,
                    new_target if meta.alternate_confidence == 0 else old_targets[meta.alternate])
        if destination is not None:
            planned[destination] = (2, 0, new_target)
        result = []
        for table, (count, useful, target_ref) in planned.items():
            bank, index, tag = coordinates(feedback.pc, feedback.context, table)
            result.append(Write(table, bank, index, Patch(True, tag, count, useful, target_ref)))
        return tuple(result)

    def advance(self, events):
        if not isinstance(events, Events):
            raise TypeError('reference input must be Events')
        if events.reset:
            self.reset()
            return self.prediction
        if events.pc is not None:
            coordinates(events.pc, events.context, 0)

        # Selection precedes this boundary's directory/commit changes. Reads
        # carry immutable table snapshots, not pointers into current memory.
        if events.enabled and events.select:
            self.prediction = None if self.read is None else self._selection(self.read)
        new_read, reading_bank = self.read, None
        if events.enabled and events.ready and events.access and self.fetch_pc is not None:
            entries, tags = [], []
            for table in range(len(SETS)):
                bank, index, tag = coordinates(self.fetch_pc, events.context, table)
                reading_bank = bank
                entries.append(self.memories[table][bank].get(index, Entry()))
                tags.append(tag)
            new_read = Read(self.fetch_pc, events.context, tuple(entries), tuple(tags))
        elif not (events.enabled and events.access):
            new_read = None

        feedback = self.learning
        qualified = feedback is not None and feedback.qualified
        saturating = self.tick == 255
        if saturating:
            self.tick = 0
        elif qualified and feedback.mispredict and not (
                feedback.metadata.provider is not None and feedback.metadata.confidence == 0
                and feedback.metadata.provider_target == feedback.target):
            self.tick = (max(0, self.tick - 1) if feedback.metadata.allocation is not None
                         else min(255, self.tick + 1))
        next_normal = self._learn(feedback)
        writes = {(write.table, write.bank): write for write in self.normal}
        next_maintenance = []
        for table, (busy, cursor) in enumerate(self.maintenance):
            normal_here = any(write.table == table for write in self.normal)
            clear = busy and reading_bank is None and not normal_here
            if clear:
                for bank in range(2):
                    writes[table, bank] = Write(table, bank, cursor, Patch(useful=0))
            for bank in range(2):
                write = writes.get((table, bank))
                drained = self.caches[table][bank].advance(
                    read_busy=not events.ready or reading_bank == bank,
                    incoming=None if write is None else (write.index, write.patch))
                if drained is not None:
                    old = self.memories[table][bank].get(drained.index, Entry())
                    self.memories[table][bank][drained.index] = drained.patch.apply(old)
                    self.commits += 1
            following = (cursor + int(clear)) % SETS[table]
            finished = clear and cursor == SETS[table] - 1
            next_maintenance.append((True if self.clear_start else busy and not finished, following))
        self.maintenance, self.clear_start = next_maintenance, saturating
        self.normal = next_normal
        self.learning = events.feedback if events.enabled else None
        self.read = new_read
        if events.enabled and events.pc is not None:
            self.fetch_pc = events.pc
        return self.prediction

    def state(self):
        return dict(fetch_pc=self.fetch_pc, read=self.read, prediction=self.prediction,
                    accepted_feedback=self.learning, pending_updates=self.normal,
                    tick=self.tick, maintenance=tuple(self.maintenance), commits=self.commits,
                    regions=self.regions.regions,
                    pending_cache_keys=tuple(tuple(tuple(slot.index for slot in cache.slots
                        if slot is not None and slot.dirty) for cache in banks) for banks in self.caches))
