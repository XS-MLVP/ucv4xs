"""Independent statistical-correction semantics for the pinned MinimalConfig.

Five families own signed learning weights: path, global, backward, loop count
and bias. A lookup captures a committed-weight snapshot; later base-predictor
information selects its branch feature. Feedback votes update weights and
adaptive confidence thresholds atomically. No DUT objects or debug metadata
indices are used here. PC units are explicitly the existing SC API's halfwords.

Timing is a separate visibility contract: feedback reads committed weights,
learns next cycle, queues masked writes the following cycle, and reads have
priority over write retirement in each bank. There is no SRAM-to-golden sync.
"""
from dataclasses import dataclass, replace

from bpuverify.sc.model.threshold import ScThresholdModel
from bpuverify.sc.transaction.types import ScBaseBranch


FAMILIES = ('path', 'global', 'backward', 'loop', 'bias')


def fold(value, length, width=7):
    """Parity of semantic history positions, independent of port packing."""
    result = 0
    for bit in range(length):
        result ^= ((value >> bit) & 1) << (bit % width)
    return result


@dataclass(frozen=True, slots=True)
class Context:
    path: int = 0  # The public upstream path feature: eight bits folded to seven.
    global_history: int = 0
    backward: int = 0
    loop: int = 0
    common_valid: bool = True

    @classmethod
    def from_history(cls, history):
        return cls(fold(history.path, 8), history.global_history, history.backward,
                   history.loop, history.common_valid)

    def __post_init__(self):
        for name, width in (('path', 7), ('global_history', 8), ('backward', 4), ('loop', 8)):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value < 1 << width:
                raise ValueError(f'SC {name} is out of range')


def coordinates(pc, context):
    if type(pc) is not int or not 0 <= pc < 1 << 49:
        raise ValueError('SC halfword PC is out of range')
    row = (pc // 8) % 128
    return pc % 2, (row ^ context.path, row ^ fold(context.global_history, 8),
                    row ^ context.backward, row ^ fold(context.loop, 8), row)


def way(position):
    if type(position) is not int or not 0 <= position < 16:
        raise ValueError('SC branch position must fit four bits')
    return (position % 4) ^ (position // 4)


def bias_feature(branch):
    if not 0 <= branch.tage_counter < 8:
        raise ValueError('SC TAGE confidence must fit three bits')
    return (2 * int(branch.provider_valid and branch.tage_counter in (3, 4))
            + int(branch.provider_valid and branch.tage_counter >= 4))


@dataclass(frozen=True, slots=True)
class Read:
    pc: int
    context: Context
    indices: tuple[int, ...]
    weights: tuple[tuple[int, ...], ...]


@dataclass(frozen=True, slots=True)
class Prediction:
    read: Read
    branches: tuple[ScBaseBranch, ...]
    sums: tuple[int, ...]
    directions: tuple[int, ...]
    used: tuple[int, ...]
    above: tuple[int, ...]
    components: tuple[tuple[int, ...], ...]

    def metadata(self):
        return dict(scBiasLowerBits=tuple(map(bias_feature, self.branches)),
                    scPred=self.directions, useScPred=self.used, sumAboveThres=self.above,
                    tageCtr=tuple(b.tage_counter for b in self.branches),
                    tagePred=tuple(int(b.tage_counter >= 4) for b in self.branches),
                    tagePredValid=tuple(int(b.provider_valid) for b in self.branches))


def decide(read, branches, thresholds, *, enabled=True):
    """Evaluate weighted evidence and TAGE-confidence-dependent correction."""
    if len(branches) != 4 or len(thresholds) != 4:
        raise ValueError('SC decisions require four base slots and thresholds')
    sums, directions, used, above, components = [], [], [], [], []
    for branch in branches:
        slot = way(branch.position)
        weights = tuple(row[slot if family != 'bias' else 4 * slot + bias_feature(branch)]
                        for family, row in zip(FAMILIES, read.weights, strict=True))
        evidence = tuple(2 * weight + 1 for weight in weights)
        total = sum(evidence)
        eligible = bool(branch.mbtb_valid and branch.branch_type == 1 and branch.provider_valid)
        confidence = branch.tage_counter
        shift = 4 if confidence in (0, 7) else 6 if confidence in (3, 4) else 5
        confident = eligible and abs(total) > thresholds[slot] // (1 << shift)
        sums.append(total)
        directions.append(int(total >= 0))
        used.append(int(enabled and confident))
        above.append(int(confident or not eligible))
        components.append(tuple(int(value >= 0) for value in evidence))
    return Prediction(read, tuple(branches), tuple(sums), tuple(directions), tuple(used),
                      tuple(above), tuple(components))


@dataclass(frozen=True, slots=True)
class PendingRow:
    index: int
    patch: tuple[int | None, ...]
    dirty: bool = True


class DeferredWeights:
    """Bounded masked-write visibility, expressed as logical weight patches.

    Completed shadows retain their masks; same-address patches compose. The
    configured non-backpressured capacity contract permits full-miss eviction.
    No tags, packed masks, RTL next-state wires or observed buffer slots enter
    this model. Retirement uses the oldest slot number, not FIFO submission.
    """
    def __init__(self):
        self.rows = [None] * 4
        self.older = [0] * 3

    def advance(self, busy, incoming=None):
        before = tuple(self.rows)
        dirty = [i for i, row in enumerate(before) if row is not None and row.dirty]
        retired = before[dirty[0]] if dirty and not busy else None
        if retired is not None:
            self.rows[dirty[0]] = replace(retired, dirty=False)
        if incoming is not None:
            index, patch = incoming
            slot = next((i for i, row in enumerate(before) if row is not None and row.index == index), None)
            if slot is None:
                side = self.older[0]
                slot = next((i for i, row in enumerate(before) if row is None or not row.dirty),
                            2 * side + self.older[1 + side])
                self.rows[slot] = PendingRow(index, patch)
                side = slot // 2
                self.older[0], self.older[1 + side] = 1 - side, 1 - slot % 2
            else:
                old = before[slot]
                merged = tuple(new if new is not None else value
                               for value, new in zip(old.patch, patch, strict=True))
                if old.dirty or merged != old.patch:
                    self.rows[slot] = PendingRow(index, merged)
        return retired


@dataclass(frozen=True, slots=True)
class Events:
    pc: int | None = None
    context: Context = Context()
    advance: bool = False
    select: bool = False
    branches: tuple[ScBaseBranch, ...] = ()
    feedback: object = None
    feedback_context: Context = Context()
    enabled: bool = True
    ready: bool = True
    reset: bool = False


def feedback_needs_read(transaction):
    """Logical read obligation, independent of acceptance or physical ports."""
    return any(branch is not None and branch.mbtb_hit and branch.branch_type == 1
        and transaction.meta['tagePredValid'][branch.prediction_slot]
        and not (transaction.meta['useScPred'][branch.prediction_slot]
                 and branch.actual_taken == transaction.meta['scPred'][branch.prediction_slot]
                 == transaction.meta['tagePred'][branch.prediction_slot])
        for branch in transaction.branches)


class ScReference:
    def __init__(self):
        self.reset()

    def reset(self):
        self.thresholds = ScThresholdModel()
        self.memory = [{} for _ in FAMILIES]
        self.writes = [[DeferredWeights() for _ in range(2)] for _ in FAMILIES]
        self.read = self.selection = self.prediction = None
        self.learning = None
        self.pending = ()
        self.cycles = self.commits = self.checkable_predictions = 0

    def snapshot(self, pc, context):
        bank, indices = coordinates(pc, context)
        weights = []
        for table, family in enumerate(FAMILIES):
            size = 16 if family == 'bias' else 4
            row = self.memory[table].get((bank, indices[table]), (0,) * size)
            if not context.common_valid and family in ('global', 'backward'):
                row = (0,) * size
            weights.append(row)
        return Read(pc, context, indices, tuple(weights))

    def _learn(self, transaction, read, *, thresholds=None):
        features = transaction.meta['scBiasLowerBits']
        if len(features) != 4 or any(type(feature) is not int or not 0 <= feature < 4 for feature in features):
            raise ValueError('SC feedback needs four valid bias features')
        update = (self.thresholds if thresholds is None else thresholds).apply(transaction)
        branches = {branch.prediction_slot: branch for branch in transaction.branches if branch is not None}
        patches = []
        for table, family in enumerate(FAMILIES):
            if not read.context.common_valid and family in ('global', 'backward'):
                continue
            votes = [0] * len(read.weights[table])
            for slot in update.qualifying_slots:
                branch = branches[slot]
                column = way(branch.position)
                if family == 'bias':
                    feature = features[slot]
                    column = 4 * column + feature
                votes[column] += 1 if branch.actual_taken else -1
            patch = tuple(max(-32, min(31, weight + vote)) if vote else None
                          for weight, vote in zip(read.weights[table], votes, strict=True))
            # Unchanged saturated weights have no physical write obligation.
            patch = tuple(new if new != old else None for old, new in zip(read.weights[table], patch, strict=True))
            if any(value is not None for value in patch):
                patches.append((table, read.pc % 2, read.indices[table], patch))
        return tuple(patches)

    def preview_learning(self):
        """Pure T1 effect for a post-edge observer of threshold/T2 outputs.

        The accepted read is already owned. Preview neither advances clocks
        nor changes memories, queues or thresholds; advance consumes it once.
        """
        original = self.thresholds
        thresholds = ScThresholdModel(ways=original.ways, position_width=original.position_width,
            width=original.width, minimum=original.minimum, maximum=original.maximum, initial=original.values)
        patches = self._learn(*self.learning, thresholds=thresholds) if self.learning is not None else ()
        return patches, thresholds.values

    def advance(self, events=Events()):
        if events.reset:
            self.reset()
            return
        self.cycles += 1
        old_read, old_selection = self.read, self.selection
        new_learning = None
        busy = set()
        if events.ready and events.enabled:
            if events.pc is not None:
                self.read = self.snapshot(events.pc, events.context)
                busy.update((table, events.pc % 2) for table, family in enumerate(FAMILIES)
                            if events.context.common_valid or family not in ('global', 'backward'))
            if events.advance:
                self.selection = old_read
            if events.select and old_selection is not None:
                self.prediction = decide(old_selection, events.branches, self.thresholds.values)
                self.checkable_predictions += 1
            if events.feedback is not None:
                transaction = events.feedback
                # Validation and eligibility cannot mutate state until learning.
                probe = ScThresholdModel(initial=self.thresholds.values)
                probe.apply(transaction)
                if feedback_needs_read(transaction):
                    read = self.snapshot(transaction.pc, events.feedback_context)
                    if events.pc is not None and transaction.pc % 2 == events.pc % 2:
                        raise AssertionError('SC accepts conflicting prediction and feedback reads in one bank')
                    busy.update((table, transaction.pc % 2) for table, family in enumerate(FAMILIES)
                                if events.feedback_context.common_valid or family not in ('global', 'backward'))
                    new_learning = (transaction, read)
        incoming = {(table, bank): (index, patch) for table, bank, index, patch in self.pending}
        self.pending = self._learn(*self.learning) if self.learning is not None else ()
        self.learning = new_learning
        for table, banks in enumerate(self.writes):
            for bank, cache in enumerate(banks):
                retired = cache.advance((table, bank) in busy, incoming.get((table, bank)))
                if retired is not None:
                    key = bank, retired.index
                    before = self.memory[table].get(key, (0,) * len(retired.patch))
                    self.memory[table][key] = tuple(old if new is None else new
                                                  for old, new in zip(before, retired.patch, strict=True))
                    self.commits += 1

    def state(self):
        return dict(cycle=self.cycles, thresholds=self.thresholds.values,
                    committed_rows=tuple(len(table) for table in self.memory), commits=self.commits,
                    pending_learning=self.learning, pending_writes=self.pending,
                    prediction=self.prediction)
