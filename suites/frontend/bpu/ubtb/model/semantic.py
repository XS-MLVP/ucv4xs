"""MicroBTB learning semantics and their clocked visibility contract.

Inputs are public prediction/feedback events, never entry observations, hit
flags, victim wires or counters read from the DUT. The reliability cache is
owned here. Timing distinguishes an accepted feedback from its effect, and a
captured lookup from the later use of its selected entry.

Scope: the checked-in 32-entry, one-taken, PLRU, no-target-fix MicroBTB config.
Addresses use the standalone API's aligned 50-bit unguarded byte units.
"""
from suites.frontend.bpu.models.configuration import *

from dataclasses import dataclass, replace

from suites.frontend.bpu.ubtb.transaction.types import (
    BranchTraining, PredictRequest, UbtbBatchTraining, UbtbPrediction,
)


@dataclass(frozen=True, slots=True)
class UbtbEvents:
    """Events at one sampling boundary; consume controls prediction touches.

    A disabled request is not accepted. An already accepted feedback still
    completes if enable is subsequently removed. Reset cancels both pipelines.
    """
    predict: PredictRequest | None = None
    fast_feedback: BranchTraining | None = None
    resolve_feedback: UbtbBatchTraining | None = None
    consume: bool = True
    enabled: bool = True
    reset: bool = False


@dataclass(frozen=True, slots=True)
class Entry:
    key: int = 0
    confidence: int = 0
    target: int = 0
    position: int = 0
    branch_type: int = 0
    ras_action: int = 0


@dataclass(frozen=True, slots=True)
class Learning:
    feedback: BranchTraining
    slot: int | None
    result: Entry


@dataclass(frozen=True, slots=True)
class Lookup:
    pc: int
    slot: int | None
    replaced: bool = False


class _RecencyTree:
    """Conceptual tree of older children, not a packed RTL state word."""
    def __init__(self, capacity):
        self.capacity = capacity
        self.older = [0] * (capacity - 1)

    def victim(self):
        node, start, size = 0, 0, self.capacity
        while size > 1:
            child = self.older[node]
            size //= 2
            start += child * size
            node = 2 * node + 1 + child
        return start

    def touch(self, slot):
        node, start, size = 0, 0, self.capacity
        while size > 1:
            size //= 2
            child = int(slot >= start + size)
            self.older[node] = 1 - child
            start += child * size
            node = 2 * node + 1 + child


class UbtbReference:
    capacity = 32
    confidence_max = 3
    tag_mask = (1 << 22) - 1
    # The record owns 22 halfword bits. In byte units this is an 8-MiB
    # local region, not a 4-MiB region with architectural bit22 discarded.
    target_mask = (1 << 23) - 1

    def __init__(self):
        self.reset()

    def reset(self):
        self.entries = [Entry() for _ in range(self.capacity)]
        self.recency = _RecencyTree(self.capacity)
        self.learning = None
        self.lookup = None

    @classmethod
    def key(cls, pc):
        return (pc >> 1) & cls.tag_mask

    @staticmethod
    def _address(value, name):
        if type(value) is not int or not 0 <= value < (1 << 50) or value & 1:
            raise ValueError(f'{name} must be an unsigned 50-bit, halfword-aligned byte address')

    @classmethod
    def _validate_feedback(cls, feedback):
        cls._address(feedback.pc, 'feedback PC')
        cls._address(feedback.target, 'feedback target')
        for name, limit in (('taken', 2), ('mispredict', 2), ('position', POSITIONS),
                            ('branch_type', 4), ('ras_action', 4)):
            value = getattr(feedback, name)
            if type(value) is not int or not 0 <= value < limit:
                raise ValueError(f'{name} must be in [0, {limit})')

    @classmethod
    def _feedback(cls, events):
        selected = events.fast_feedback
        if selected is not None:
            cls._validate_feedback(selected)
        batch = events.resolve_feedback
        if batch is None:
            return selected
        cls._address(batch.pc, 'resolve PC')
        if len(batch.branches) > 8 or batch.fire not in (0, 1):
            raise ValueError('resolve requires at most eight branches and a Boolean fire')
        wrong = []
        for branch in batch.branches:
            if branch is None:
                continue
            value = BranchTraining(batch.pc, branch.target, branch.taken,
                                   branch.position, branch.branch_type,
                                   branch.ras_action, branch.mispredict)
            cls._validate_feedback(value)
            if branch.valid not in (0, 1):
                raise ValueError('branch validity must be Boolean')
            if branch.valid and branch.mispredict:
                wrong.append(value)
        if len(wrong) > 1:
            raise ValueError('FTQ feedback permits at most one valid misprediction')
        return wrong[0] if batch.fire and wrong else selected

    def _find(self, pc):
        matches = [slot for slot, entry in enumerate(self.entries)
                   if entry.confidence and entry.key == self.key(pc)]
        if len(matches) > 1:
            raise AssertionError(f'reference cache has duplicate live key {self.key(pc)}')
        return matches[0] if matches else None

    def victim(self):
        return next((slot for slot, entry in enumerate(self.entries)
                     if not entry.confidence), self.recency.victim())

    def _learn(self, old, feedback):
        target = feedback.target & self.target_mask & ~1
        if old is None or not old.confidence:
            # Dead entries are not taken predictions. A fall-through feedback
            # cannot revive one, even when it follows the depleting feedback
            # without a bubble. Do not copy a forwarding hit qualifier into
            # this learning rule: that would enshrine an RTL bug as expected.
            if not feedback.taken:
                return Entry() if old is None else old
            return Entry(self.key(feedback.pc), self.confidence_max, target,
                         feedback.position, feedback.branch_type, feedback.ras_action)
        correct = feedback.taken and (
            old.target, old.position, old.branch_type, old.ras_action
        ) == (target, feedback.position, feedback.branch_type, feedback.ras_action)
        return replace(old, confidence=(min(self.confidence_max, old.confidence + 1)
                                        if correct else old.confidence - 1))

    def prediction(self, *, enabled=True):
        lookup = self.lookup
        if not enabled or lookup is None or lookup.slot is None or lookup.replaced:
            # Payload is deliberately undefined on a miss; check only valid.
            return UbtbPrediction(0, 0, 0, 0, 0)
        entry = self.entries[lookup.slot]
        # A selected entry may age to zero in this same clock. The captured
        # hit remains a prediction; its confidence is not re-read for validity.
        target = (lookup.pc & ~self.target_mask) | entry.target
        return UbtbPrediction(1, 1, target, entry.position,
                              entry.branch_type, entry.ras_action)

    def advance(self, events: UbtbEvents):
        """Advance exactly one clock; return the resulting public prediction.

        Lookup reads committed keys before this boundary's delayed feedback
        takes effect. Training sees a forwarded preceding effect for the same
        key. A different key cannot falsely match a simultaneously evicted
        entry. Prediction then consumes the current payload of its chosen slot.
        """
        if not isinstance(events, UbtbEvents):
            raise TypeError('reference input must be UbtbEvents')
        if events.reset:
            self.reset()
            return self.prediction(enabled=events.enabled)
        if events.predict is not None:
            self._address(events.predict.pc, 'prediction PC')
        feedback = self._feedback(events)
        pending = self.learning
        slot = None if pending is None else (
            self.victim() if pending.slot is None else pending.slot)
        allocating = pending is not None and pending.slot is None and pending.feedback.taken
        writing = pending is not None and (pending.slot is not None or allocating)

        lookup = self.lookup
        if events.enabled and events.predict is not None:
            hit = self._find(events.predict.pc)
            lookup = Lookup(events.predict.pc, hit, allocating and hit == slot)

        following = None
        if events.enabled and feedback is not None:
            hit = self._find(feedback.pc)
            if allocating and hit == slot:
                hit = None
            old = None if hit is None else self.entries[hit]
            if writing and self.key(feedback.pc) == self.key(pending.feedback.pc):
                hit, old = slot, pending.result
            following = Learning(feedback, hit, self._learn(old, feedback))

        # Lookup and training touches on this boundary are ordered: training
        # is newer. Selection above uses the pre-touch recency state.
        if events.enabled and events.consume and self.prediction().valid:
            self.recency.touch(self.lookup.slot)
        if pending is not None:
            self.recency.touch(slot)
            if writing:
                self.entries[slot] = pending.result
        self.lookup, self.learning = lookup, following
        return self.prediction(enabled=events.enabled)

    def state(self):
        """Bounded failure context, not a state export used as stimulus."""
        return dict(lookup=self.lookup, learning=self.learning,
                    entries=tuple(self.entries), older_children=tuple(self.recency.older))
