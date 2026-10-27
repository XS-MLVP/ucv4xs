"""Independent SC threshold reference over accepted feedback, not RTL bits."""
from dataclasses import dataclass
from operator import index
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpuverify.sc.transaction.types import ScBatchTraining


@dataclass(frozen=True, slots=True)
class ScThresholdUpdate:
    before: tuple[int, ...]
    after: tuple[int, ...]
    increments: tuple[int, ...]
    decrements: tuple[int, ...]
    qualifying_slots: tuple[int, ...]
    rejected_ways: tuple[int, ...]


class ScThresholdModel:
    """Four-way MinimalConfig by default; consume unmodified feedback metadata.

    Range rejection preserves the old entry, not the nearest range endpoint.
    Multiple branches contribute a net direction before one atomic update.
    No actual threshold observation is used to initialize or update this model.
    """

    def __init__(self, *, ways=4, position_width=4, width=13,
                 minimum=640, maximum=5040, initial=1130):
        ways, position_width, width = index(ways), index(position_width), index(width)
        minimum, maximum = index(minimum), index(maximum)
        if ways < 2 or ways & (ways - 1) or position_width < 1 or width < 1:
            raise ValueError('invalid SC threshold geometry')
        if not 0 <= minimum <= maximum < (1 << width):
            raise ValueError('threshold bounds must fit the counter')
        self.ways, self.position_width, self.width = ways, position_width, width
        self.minimum, self.maximum = minimum, maximum
        self.initial = tuple(index(value) for value in initial) if isinstance(initial, tuple) else (index(initial),) * ways
        if len(self.initial) != ways or any(not minimum <= value <= maximum for value in self.initial):
            raise ValueError('initial thresholds must be in range for every way')
        self._values = self.initial

    @property
    def values(self):
        return self._values

    def reset(self):
        self._values = self.initial

    def way(self, position):
        position = index(position)
        if not 0 <= position < (1 << self.position_width):
            raise ValueError('SC position is out of range')
        chunk_width = self.ways.bit_length() - 1
        mask, result = self.ways - 1, 0
        for shift in range(0, self.position_width, chunk_width):
            result ^= (position >> shift) & mask
        return result

    @staticmethod
    def _bit(value):
        value = index(value)
        if value not in (0, 1):
            raise ValueError('SC metadata and outcomes must contain two-state bits')
        return value

    def apply(self, transaction: 'ScBatchTraining', *, enabled=True):
        """Validate the whole beat before changing reference state."""
        enabled = self._bit(enabled)
        branches = tuple(transaction.branches)
        active = [branch for branch in branches if branch is not None]
        if not 1 <= len(branches) <= 8 or not active:
            raise ValueError('SC feedback needs one to eight slots and an active branch')
        if len({branch.position for branch in active}) != len(active):
            raise ValueError('SC branch positions must be distinct')
        slots = [index(branch.prediction_slot) for branch in active]
        if len(set(slots)) != len(slots) or any(not 0 <= slot < self.ways for slot in slots):
            raise ValueError('SC prediction slots must be distinct and in range')
        keys = ('scPred', 'tagePred', 'tagePredValid', 'useScPred', 'sumAboveThres')
        meta = {}
        for key in keys:
            values = tuple(self._bit(value) for value in transaction.meta[key])
            if len(values) != self.ways:
                raise ValueError(f'{key} must have one value per prediction slot')
            meta[key] = values
        decoded = []
        for branch in active:
            kind = index(branch.branch_type)
            if not 0 <= kind <= 3:
                raise ValueError('SC branch type is out of range')
            decoded.append((branch.prediction_slot, self.way(branch.position),
                            self._bit(branch.actual_taken), self._bit(branch.mbtb_hit), kind))

        increments, decrements, qualifying = [0] * self.ways, [0] * self.ways, []
        for slot, way, taken, hit, kind in decoded:
            valid = meta['tagePredValid'][slot]
            predicted, used = meta['scPred'][slot], meta['useScPred'][slot]
            sc_wrong = taken != predicted
            correct_and_agrees = taken == predicted == meta['tagePred'][slot]
            eligible = enabled and hit and kind == 1 and valid and not (used and correct_and_agrees)
            if eligible and (sc_wrong or not meta['sumAboveThres'][slot]):
                qualifying.append(slot)
                (increments if sc_wrong else decrements)[way] += 1
        candidates = tuple(max(0, min((1 << self.width) - 1, old + inc - dec))
                           for old, inc, dec in zip(self.values, increments, decrements, strict=True))
        rejected = tuple(way for way, value in enumerate(candidates)
                         if not self.minimum <= value <= self.maximum)
        after = tuple(old if way in rejected else new
                      for way, (old, new) in enumerate(zip(self.values, candidates, strict=True)))
        update = ScThresholdUpdate(self.values, after, tuple(increments), tuple(decrements),
                                   tuple(qualifying), rejected)
        self._values = after
        return update

    def apply_many(self, transactions, *, enabled=True):
        """An invalid later beat must not leave a partially updated reference."""
        before = self.values
        try:
            updates = tuple(self.apply(transaction, enabled=enabled) for transaction in transactions)
            if not updates:
                raise ValueError('SC feedback burst must not be empty')
            return updates
        except Exception:
            self._values = before
            raise
