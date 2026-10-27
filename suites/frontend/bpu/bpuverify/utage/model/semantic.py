"""Independent history-conditioned direction tables and visibility contracts.

DefaultConfig promises two 512-row tables with histories 5/9 and 8-bit tags.
The model owns every entry/useful value. Metadata is a public feedback input,
not a prediction oracle. It derives complete configured tags without copying the implementation's dirty-mask/priority-mask logic.

Recent updates are chronological immutable versions: newest matching versions
forward, superseded writes coalesce, committed versions remain cacheable, and
queue pressure retires a write before a dirty version can be overwritten.
Read snapshots survive later updates. PC units are this UT API's halfwords.
"""
from dataclasses import dataclass, replace

from bpuverify.common.model.configuration import MICRO_HISTORIES, MICRO_HISTORY_TAG_BITS, MICRO_TAG_BITS, PHR_BITS

from bpuverify.common.model.folded_history import PHR_FOLD_LAYOUT


HISTORIES = MICRO_HISTORIES
SETS = 512
TAG_BITS = MICRO_TAG_BITS
INDEX_FOLDS = tuple(PHR_FOLD_LAYOUT.index((n,min(n,9))) for n in HISTORIES)
TAG_FOLDS = tuple(PHR_FOLD_LAYOUT.index((n,min(n,b))) for n,b in zip(HISTORIES,MICRO_HISTORY_TAG_BITS))
ALT_FOLDS = tuple(PHR_FOLD_LAYOUT.index((n,min(n,b-1))) for n,b in zip(HISTORIES,MICRO_HISTORY_TAG_BITS))
PC_FEATURES = ((3, 2, 1), ())
PC_PARITY = ((10, 8, 6, 4, 2), (14, 12, 10, 8, 6, 4, 2, 0))


def unsigned(value, limit, name):
    if type(value) is not int or not 0 <= value < limit:
        raise ValueError(f'UTAGE {name} must be an unsigned integer below {limit}')


@dataclass(frozen=True, slots=True)
class Context:
    folds: tuple[int, ...] = (0,) * len(PHR_FOLD_LAYOUT)

    def __post_init__(self):
        if len(self.folds) != len(PHR_FOLD_LAYOUT):
            raise ValueError('UTAGE context requires all configured public folded histories')
        for value, (_, width) in zip(self.folds, PHR_FOLD_LAYOUT, strict=True):
            unsigned(value, 1 << width, 'folded history')

    @classmethod
    def from_recent(cls, recent):
        unsigned(recent, 1 << PHR_BITS, 'recent path history')
        return cls(tuple(sum((sum((recent >> position) & 1
            for position in range(bit, length, width)) % 2) << bit
            for bit in range(width)) for length, width in PHR_FOLD_LAYOUT))


def indices(pc, context):
    unsigned(pc, 1 << 49, 'halfword PC')
    return tuple((pc ^ context.folds[feature]) % SETS for feature in INDEX_FOLDS)


def tag(pc, context, table):
    unsigned(pc, 1 << 49, 'halfword PC')
    unsigned(table, 2, 'table')
    features = sum(((pc >> position) & 1) << bit
                   for bit, position in enumerate(reversed(PC_FEATURES[table])))
    parity = sum(((pc >> position) & 1) << bit
                 for bit, position in enumerate(reversed(PC_PARITY[table])))
    width = MICRO_HISTORY_TAG_BITS[table]
    low = (parity ^ context.folds[TAG_FOLDS[table]] ^ (2 * context.folds[ALT_FOLDS[table]])) % (1 << width)
    return (features << width) | low


@dataclass(frozen=True, slots=True)
class Entry:
    valid: bool = False
    tag: int = 0
    position: int = 0
    counter: int = 0


@dataclass(frozen=True, slots=True)
class Version:
    sequence: int
    index: int
    entry: Entry


class RecentUpdates:
    """Eight retained versions and a bank-arbitrated write obligation stream."""
    def __init__(self):
        self.recent = []
        self.outstanding = []
        self.dirty = set()
        self.sequence = 0
        self.pressured = False

    def newest(self, index):
        return next((version for version in reversed(self.recent) if version.index == index), None)

    def retiring(self, read_index):
        if not self.outstanding:
            return None
        oldest = self.outstanding[0]
        if oldest.sequence not in self.dirty:
            return None
        return oldest if self.pressured or oldest.index % 4 != read_index % 4 else None

    def advance(self, read_index, incoming=None):
        retiring = self.retiring(read_index)
        pressure = len(self.outstanding) > 6
        if self.outstanding:
            oldest = self.outstanding[0]
            if oldest.sequence not in self.dirty or retiring is not None:
                self.outstanding.pop(0)
                self.dirty.discard(oldest.sequence)
        if incoming is not None:
            index, entry = incoming
            previous = self.newest(index)
            if previous is not None:
                self.dirty.discard(previous.sequence)
            version = Version(self.sequence, index, entry)
            self.sequence += 1
            self.recent.append(version)
            self.outstanding.append(version)
            self.dirty.add(version.sequence)
            if len(self.recent) > 8:
                evicted = self.recent.pop(0)
                if evicted.sequence in self.dirty:
                    raise AssertionError('UTAGE visibility contract cannot discard a pending dirty version')
        self.pressured = pressure
        return retiring


@dataclass(frozen=True, slots=True)
class Base:
    valid: bool = False
    position: int = 0
    taken: bool = False
    kind: int = 0
    strong: bool = False


@dataclass(frozen=True, slots=True)
class Source:
    valid: bool
    position: int
    hit: bool
    provider: int
    counter: int
    predicted: bool
    base: bool


@dataclass(frozen=True, slots=True)
class Feedback:
    pc: int
    context: Context
    indices: tuple[int, int]
    sources: tuple[Source, ...]
    position: int
    taken: bool
    kind: int = 1


@dataclass(frozen=True, slots=True)
class Learning:
    feedback: Feedback
    useful: tuple[int, int]
    residents: tuple[Entry | None, Entry | None]
    counters: tuple[Entry | None, Entry | None]


@dataclass(frozen=True, slots=True)
class Read:
    indices: tuple[int, int]
    entries: tuple[Entry, Entry]


@dataclass(frozen=True, slots=True)
class Frame:
    read: Read
    pc: int
    context: Context
    positions: tuple[int, ...]
    match_positions: tuple[int, ...]

    def providers(self):
        return tuple(next((table for table in (1, 0) if self.read.entries[table].valid
            and self.read.entries[table].tag == tag(self.pc, self.context, table)
            and self.read.entries[table].position == position), None) for position in self.match_positions)


@dataclass(frozen=True, slots=True)
class Prediction:
    frame: Frame | None
    bases: tuple[Base, ...]
    redirect_bubble: bool
    qualified: bool

    def values(self):
        providers = self.frame.providers() if self.frame is not None else (None,) * len(self.bases)
        eligible = tuple(base.valid and base.kind == 1 for base in self.bases)
        hits = tuple(int(table is not None) if valid else None for table, valid in zip(providers, eligible, strict=True))
        takens = tuple(int(table is not None and self.frame.read.entries[table].counter >= 4) for table in providers)
        result = dict(hits=hits)
        if any(value == 1 for value in hits):
            result['meta_valid'] = 1
        elif all(eligible):
            result['meta_valid'] = 0
        if self.frame is not None and any(eligible):
            result.update(indices=self.frame.read.indices, history=self.frame.context.folds)
        for slot, (base, provider) in enumerate(zip(self.bases, providers, strict=True)):
            result[f'{slot}.valid'] = int(base.valid and base.kind == 1 and not self.redirect_bubble)
            if not eligible[slot]:
                # Raw MicroTAGE corrections explicitly require the upstream
                # valid conditional branch. Empty pipeline beats cannot be
                # converted into meaningful prediction responses.
                continue
            result[f'{slot}.base'] = int(base.taken)
            result[f'{slot}.strong'] = int(base.strong)
            result[f'{slot}.hit'] = int(base.valid and provider is not None)
            if provider is not None:
                # A miss carries no correction payload. Priority-mux fallback
                # bits are not a defined direction prediction.
                result[f'{slot}.taken'] = takens[slot]
                result[f'{slot}.predicted'] = takens[slot]
            if self.frame is not None:
                result[f'{slot}.position'] = self.frame.positions[slot]
            if base.valid and provider is not None:
                result[f'{slot}.provider'] = provider
                result[f'{slot}.counter'] = self.frame.read.entries[provider].counter
        return result


@dataclass(frozen=True, slots=True)
class Events:
    read_pc: int = 0
    read_context: Context = Context()
    select: bool = False
    pc: int = 0
    context: Context = Context()
    positions: tuple[int, ...] = (0, 0, 0, 0)
    bases: tuple[Base, ...] = (Base(),) * 4
    advance: bool = False
    override: str | None = None
    override_pc: int = 0
    override_context: Context = Context()
    feedback: Feedback | None = None
    redirect: bool = False
    enabled: bool = True
    ready: bool = True
    reset: bool = False


class UtageReference:
    def __init__(self):
        self.reset()

    def reset(self):
        self.memory = [{}, {}]
        self.useful = [{}, {}]
        self.updates = [RecentUpdates(), RecentUpdates()]
        self.read = self.frame = self.older = None
        self.token = None
        self.last_access = False
        self.offered = self.learning = None
        self.low_tick = self.high_tick = 0
        self.redirect_bubble = False
        self.prediction = None
        self.cycles = self.commits = self.accepted_feedback = 0
        self.effects = ()
        self.aged = False
        self.checked_indices = ()

    def _learning_read(self, feedback, incoming):
        resident = tuple(None if cache.newest(index) is None else cache.newest(index).entry
                         for cache, index in zip(self.updates, feedback.indices, strict=True))
        counters = tuple(write[1] if write is not None and write[0] == index else old
                         for old, write, index in zip(resident, incoming, feedback.indices, strict=True))
        useful = tuple(table.get(index, 0) for table, index in zip(self.useful, feedback.indices, strict=True))
        return Learning(feedback, useful, resident, counters)

    @staticmethod
    def _outcomes(feedback):
        return [(source, source.position == feedback.position and feedback.taken)
                for source in feedback.sources if source.valid and source.position <= feedback.position
                and (source.position < feedback.position or feedback.kind == 1)]

    def _learn(self, learning):
        feedback = learning.feedback
        outcomes = self._outcomes(feedback)
        wrong = [(source, actual) for source, actual in outcomes
                 if (source.predicted if source.hit else source.base) != actual]
        first = min(wrong, key=lambda row: row[0].position) if wrong else None
        minimum = first[0].provider + 1 if first is not None and first[0].hit else 0
        allocation = next((table for table in range(minimum, 2) if not learning.useful[table]), None) if first is not None else None
        failed = first is not None and allocation is None
        writes, effects = [], []
        for table in range(2):
            index = feedback.indices[table]
            intended_tag = tag(feedback.pc, feedback.context, table)
            selected = next(((source, actual) for source, actual in outcomes if source.hit and source.provider == table
                and (learning.residents[table] is None or learning.residents[table].position == source.position)), None)
            if table == allocation:
                source, actual = first
                entry = Entry(True, intended_tag, source.position, 4 if actual else 3)
                new_useful, role = table + 1, 'allocate'
            elif selected is not None:
                source, actual = selected
                # A same-row/tag forwarding write can belong to ANOTHER
                # conditional instruction. Never combine its confidence with
                # this source's saved position/eligibility. Keep an older
                # compatible resident before falling back to the own hint.
                compatible = next((entry for entry in (learning.counters[table], learning.residents[table])
                    if entry is not None and entry.valid and entry.tag == intended_tag
                    and entry.position == source.position), None)
                before_counter = source.counter if compatible is None else compatible.counter
                entry = Entry(True, intended_tag, source.position, max(0, min(7, before_counter + (1 if actual else -1))))
                new_useful, role = None, 'update'
                if source.predicted != actual or source.base != source.predicted:
                    old_useful = self.useful[table].get(index, 0)
                    increase = source.predicted == actual and source.base != source.predicted
                    new_useful = max(0, min(3, old_useful + (1 if increase else -1)))
                    role = 'useful-increase' if increase else 'useful-decrease'
            else:
                writes.append(None)
                continue
            writes.append((index, entry))
            if new_useful is not None:
                before = self.useful[table].get(index, 0)
                self.useful[table][index] = new_useful
                effects.append((table, index, before, new_useful, role))
        return tuple(writes), tuple(effects), failed

    def advance(self, events=Events()):
        if events.reset:
            self.reset()
            return
        self.cycles += 1
        previous_read, previous_frame, previous_token = self.read, self.frame, self.token
        previous_older, previous_access = self.older, self.last_access
        applied = self.learning
        low_reset, high_reset = self.low_tick == 128, self.high_tick == 256
        old_useful = tuple(dict(values) for values in self.useful) if low_reset else None
        read_indices = indices(events.read_pc, events.read_context)
        physical_entries = []
        for table, index in enumerate(read_indices):
            shadow = self.updates[table].newest(index)
            entry = shadow.entry if shadow is not None else self.memory[table].get(index, Entry())
            retiring = self.updates[table].retiring(index)
            if shadow is None and retiring is not None and self.updates[table].pressured and retiring.index % 4 == index % 4:
                entry = replace(entry, valid=False)
            physical_entries.append(entry)

        # Training residency/usefulness is sampled before this boundary's
        # learning writes; only the counter chain forwards a predecessor write.
        pending_read = None
        if self.offered is not None and events.enabled and events.ready:
            pending_read = self._learning_read(self.offered, (None, None))
        writes, effects, failed = self._learn(applied) if applied is not None else ((None, None), (), False)
        if pending_read is not None:
            counters = tuple(write[1] if write is not None and write[0] == index else old
                for old, write, index in zip(pending_read.counters, writes, pending_read.feedback.indices, strict=True))
            pending_read = replace(pending_read, counters=counters)
            self.accepted_feedback += 1
        self.learning = pending_read
        self.offered = events.feedback
        self.effects = effects
        self.checked_indices = tuple((table, index) for table, index in enumerate(applied.feedback.indices)) if applied is not None else ()
        self.aged = low_reset
        self.low_tick = 0 if low_reset else self.low_tick + int(failed)
        self.high_tick = 0 if high_reset else self.high_tick + int(failed)
        if low_reset:
            self.useful = [{index: max(0, value - 1) for index, value in old_useful[0].items()},
                           {index: value // 2 for index, value in old_useful[1].items()}]
            self.effects = tuple((table, index, value, self.useful[table][index], 'age')
                for table, values in enumerate(old_useful) for index, value in values.items())
        if events.ready:
            for table, index in enumerate(read_indices):
                retiring = self.updates[table].advance(index, writes[table])
                if retiring is not None:
                    self.memory[table][retiring.index] = retiring.entry
                    self.commits += 1
            self.read = Read(read_indices, tuple(physical_entries))
        qualified = self.frame is not None
        if events.enabled and events.ready:
            if events.advance:
                self.older = previous_frame
            if events.select:
                source = previous_older if events.override == 's3' else previous_frame if events.override == 's2' else None
                if events.override is not None:
                    if source is not None:
                        self.frame = replace(source, pc=events.override_pc, context=events.override_context,
                                             positions=events.positions)
                    qualified = source is not None
                elif previous_read is not None:
                    read = replace(previous_read, indices=previous_token or previous_read.indices)
                    self.frame = Frame(read, events.pc, events.context, events.positions, events.positions)
                    qualified = previous_access
                self.token = read_indices
        self.last_access = bool(events.select and events.enabled and events.ready)
        frame = self.frame
        if events.redirect and frame is not None:
            # Flushing prediction ownership is not a memory/table reset.
            frame = replace(frame, read=replace(frame.read, entries=(Entry(), Entry())))
            self.frame = frame
        self.prediction = Prediction(frame, events.bases, events.redirect, qualified)
        self.redirect_bubble = events.redirect

    def state(self):
        return dict(cycle=self.cycles, low_tick=self.low_tick, high_tick=self.high_tick,
            committed_rows=tuple(len(table) for table in self.memory),
            pending_writes=tuple(len(cache.dirty) for cache in self.updates),
            accepted_feedback=self.accepted_feedback, commits=self.commits,
            learning=self.learning, offered=self.offered, prediction=self.prediction)
