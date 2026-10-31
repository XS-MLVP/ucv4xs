"""Owned statistical evidence, not an all-predictor pipeline adapter.

The caller supplies independently derived semantic CommonHR/IMLI features;
their actual S0 window scheduling remains an explicit integration obligation.
Only the path feature is certified here against the exact path checkpoint.
Weights, decisions and learning belong to the existing independent SC model.
This layer neither samples hardware nor advances any other predictor.
"""
from suites.frontend.bpu.models.configuration import *

from dataclasses import dataclass

from suites.frontend.bpu.bpu.model.direction_sources import DirectionSnapshot, candidates
from suites.frontend.bpu.bpu.model.indirect_sources import IndirectSnapshot
from suites.frontend.bpu.bpu.model.pipeline import Resolution, Token
from suites.frontend.bpu.bpu.model.selection import Kind, final
from suites.frontend.bpu.sc.model.semantic import Context, ScReference, decide
from suites.frontend.bpu.sc.transaction.types import ScBaseBranch, ScBatchTraining, ScBranchFeedback, ScHistory


@dataclass(frozen=True, slots=True)
class StatisticalRead:
    owner: object
    pc: int
    history: ScHistory
    read: object


@dataclass(frozen=True, slots=True)
class StatisticalResult:
    original: StatisticalRead
    branches: tuple
    prediction: object
    late: object
    enabled: bool


class OwnedStatisticalReference:
    """An explicit seventh evidence domain; no duplicate Main/TAGE/ITTAGE."""

    def __init__(self):
        self.model = ScReference()
        self.reads, self.resolved, self.feedback_histories = {}, {}, {}

    def reset(self):
        self.model.reset()
        self.reads.clear()
        self.resolved.clear()
        self.feedback_histories.clear()

    def capture(self, token, *, history):
        if type(token) is not Token or type(history) is not ScHistory:
            raise TypeError('SC capture needs an owned token and independent semantic history')
        if history.path != token.history.history % (1 << PHR_BITS):
            raise ValueError('SC path history does not belong to the original checkpoint')
        key = token.history.sequence
        if key in self.reads:
            raise ValueError('SC original read cannot be rebound or captured twice')
        value = StatisticalRead(token.history, token.pc, history,
            self.model.snapshot(token.pc, Context.from_history(history)))
        self.reads[key] = value
        return value

    def snapshot(self, token, *, resolved=False):
        if type(token) is not Token:
            raise TypeError('SC lookup requires an owned pipeline token')
        value = (self.resolved if resolved else self.reads).get(token.history.sequence)
        original = value.original if resolved and value is not None else value
        if original is None or original.owner is not token.history or original.pc != token.pc:
            raise ValueError('SC source is absent, retired or belongs to another checkpoint owner')
        return value

    def resolve(self, token, *, direction, target, enabled=True):
        source = self.snapshot(token)
        if token.history.sequence in self.resolved:
            raise ValueError('SC original selection is already frozen')
        if type(enabled) is not bool:
            raise TypeError('SC selection enable must be a semantic bool')
        if type(direction) is not DirectionSnapshot or type(target) is not IndirectSnapshot:
            raise TypeError('SC joint selection needs independent TAGE and ITTAGE evidence')
        if direction.owner is not token.history or target.owner is not token.history:
            raise ValueError('SC, direction and target must share the exact original checkpoint owner')
        if direction.read is not None and direction.read.pc != token.pc:
            raise ValueError('TAGE read PC does not belong to this original')
        if target.read is not None and target.read.pc != token.pc * 2:
            raise ValueError('ITTAGE read PC does not belong to this original')
        branches, _, _ = candidates(token)
        tagged = dict(direction.wanted)
        bases = tuple(ScBaseBranch(
            0 if branch is None else branch.position, tagged.get(f'{slot}.counter', 0),
            int(bool(tagged.get(f'{slot}.has_provider'))), int(branch is not None),
            0 if branch is None else int(branch.kind)) for slot, branch in enumerate(branches))
        prediction = decide(source.read, bases, self.model.thresholds.values, enabled=enabled)
        directions = tuple(bool(tagged[f'{slot}.taken']) if tagged.get(f'{slot}.valid') else None
                           for slot in range(RESULT_SLOTS))
        statistical = tuple(bool(taken) if used else None
                            for taken, used in zip(prediction.directions, prediction.used, strict=True))
        indirect = target.prediction
        target_address = (indirect.target // 2 if target.enabled and indirect is not None
                          and indirect.provider is not None else None)
        choice = final(token.pc, branches, directions, statistical, indirect_target=target_address)
        result = StatisticalResult(source, branches, prediction, choice, enabled)
        self.resolved[token.history.sequence] = result
        return result

    def publish(self, token, *, history):
        """Freeze the independently owned public feedback-history view.

        R1 recovery may repair invalid young CommonHR payload after the SC
        read. That does not change the weights read or the source iteration.
        """
        source = self.snapshot(token, resolved=True)
        if type(history) is not ScHistory:
            raise TypeError('SC publication needs independently owned semantic history')
        original = source.original.history
        if history.path != original.path or history.loop != original.loop:
            raise ValueError('SC publication cannot rebind original path or iteration')
        if history.common_valid != original.common_valid or (history.common_valid and
                (history.global_history, history.backward) != (original.global_history, original.backward)):
            raise ValueError('only an invalid recovery history payload can be repaired')
        if token.history.sequence in self.feedback_histories:
            raise ValueError('published SC feedback history is already frozen')
        self.feedback_histories[token.history.sequence] = history

    def feedback_for(self, resolution):
        if type(resolution) is not Resolution or resolution.origin is None:
            raise ValueError('SC feedback requires the exact original resolution')
        token = resolution.origin
        source = self.snapshot(token, resolved=True)
        if token.history.sequence not in self.feedback_histories:
            raise ValueError('SC feedback requires its published history view')
        if not source.enabled:
            raise NotImplementedError('SC learning needs an originally enabled source')
        active = tuple(branch for branch in resolution.branches if branch is not None)
        first_taken = min((branch.position for branch in active if branch.taken), default=None)
        if first_taken is not None and any(branch.position > first_taken for branch in active):
            raise ValueError('SC resolved execution prefix contains an unexecuted younger branch')
        feedback = []
        for branch in active:
            if branch.kind != Kind.CONDITIONAL:
                continue
            matches = [slot for slot, original in enumerate(source.branches)
                       if original is not None and original.kind == Kind.CONDITIONAL
                       and original.position == branch.position]
            if len(matches) > 1:
                raise ValueError('SC feedback needs one logical Main source per conditional position')
            if matches:
                feedback.append(ScBranchFeedback(branch.position, int(branch.taken), matches[0]))
        if not feedback:
            return None
        return ScBatchTraining(token.pc, source.prediction.metadata(), tuple(feedback),
                               self.feedback_histories[token.history.sequence])

    def advance(self, events):
        """One independently scheduled SC boundary; never implicit settling."""
        self.model.advance(events)
        if events.reset:
            self.reads.clear()
            self.resolved.clear()
            self.feedback_histories.clear()

    def retire(self, token):
        self.snapshot(token)
        self.reads.pop(token.history.sequence)
        self.resolved.pop(token.history.sequence, None)
        self.feedback_histories.pop(token.history.sequence, None)
