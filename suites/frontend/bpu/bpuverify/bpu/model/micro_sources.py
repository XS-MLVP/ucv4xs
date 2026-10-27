"""First real source-bank adapter: independently learned MicroBTB.

All other tables must remain cold or disabled. Unsupported enabled learning
raises, rather than silently treating trained predictors as misses. Further
source-bank adapters are required for a complete all-predictor BPU oracle.
"""
from copy import copy
from dataclasses import replace
from bpuverify.bpu.model.selection import Branch, Kind, StackAction, early, fallthrough
from bpuverify.ubtb.model.semantic import UbtbEvents, UbtbReference
from bpuverify.ubtb.transaction.types import BranchTraining, PredictRequest, UbtbBatchTraining, UbtbBranchFeedback


class MicroSources:
    """Shared independently owned MicroBTB component for source-bank profiles."""
    def __init__(self):
        self.micro = UbtbReference()
        self._previous_boundary = None

    def reset(self):
        self.micro.reset()
        self._previous_boundary = None

    def _receive_feedback(self, resolve):
        """Associate a consumed receipt with its own preceding fast teacher.

        The pipeline forecasts the current S3 teacher for the next edge.
        DriveStable acceptance arrives at the following RisingStable capture.
        Replay only our retained, independent pre-admission view. Incoming
        feedback can change pending learning, never that boundary's committed
        entries, captured lookup or recency. No DUT observation enters here.
        """
        if self._previous_boundary is None:
            raise ValueError('consumed MicroBTB feedback requires its preceding owned boundary')
        view, offered = self._previous_boundary
        view.advance(replace(offered,resolve_feedback=resolve))
        expected, replayed = self.micro.state(), view.state()
        expected.pop('learning');replayed.pop('learning')
        if expected != replayed:
            raise AssertionError('consumed feedback cannot rewrite committed MicroBTB history')
        self.micro.learning = view.learning

    def capture(self, pc, checkpoint):
        return None

    def choose(self, token, stage, enabled):
        if stage != 1:
            return fallthrough(token.pc)
        prediction = self.micro.prediction(enabled=enabled[0])
        candidate = None
        if prediction.valid:
            if self.micro.lookup.pc != token.pc * 2:
                raise AssertionError('owned MicroBTB lookup is not this pipeline token')
            candidate = Branch(prediction.position, prediction.target // 2, Kind(prediction.branch_type),
                               bool(prediction.taken), StackAction(prediction.ras_action))
        return early(token.pc, micro=candidate)

    def validate(self, events, cycle):
        if not getattr(self,'has_own_ras',False) and events.feedback is not None and any(branch is not None and branch.action != StackAction.NONE
                                               for branch in events.feedback.branches):
            raise NotImplementedError('call/return learning requires the composed return-stack adapter')

    def resident(self, pc):
        return self.micro._find(pc * 2) is not None

    def advance(self, events, cycle, issued):
        third, late = cycle.tokens[2], cycle.decisions[2]
        fast = None if third is None else BranchTraining(third.pc * 2, late.branch.target * 2,
            int(late.branch.taken), late.branch.position, int(late.branch.kind), int(late.branch.action),
            int(cycle.final_repair))
        resolve = None
        if events.feedback is not None:
            tx = events.feedback
            resolve = UbtbBatchTraining(tx.pc * 2, tuple(None if branch is None else UbtbBranchFeedback(
                branch.target * 2, int(branch.taken), branch.position, int(branch.kind), int(branch.action),
                int(branch.mispredict)) for branch in tx.branches))
        if events.feedback_at_edge and resolve is not None:
            self._receive_feedback(resolve)
        offered=UbtbEvents(predict=None if issued is None else PredictRequest(issued.pc * 2),
            fast_feedback=fast, resolve_feedback=None if events.feedback_at_edge else resolve,
            consume=cycle.fires[1], enabled=cycle.enabled[0])
        self._previous_boundary=None
        if events.feedback_at_edge:
            # Entries/Learning are immutable values. Only the two bounded
            # containers need copying; this is one boundary, not a cycle log.
            view=copy(self.micro)
            view.entries=list(self.micro.entries)
            view.recency=copy(self.micro.recency)
            view.recency.older=list(self.micro.recency.older)
            self._previous_boundary=view,offered
        self.micro.advance(offered)


class MicroOnlySources(MicroSources):
    """Qualified profile: MicroBTB learning, with other tables cold/disabled."""
    def validate(self,events,cycle):
        if events.feedback is not None and any(cycle.enabled[1:]):
            raise NotImplementedError('other enabled predictor learning needs the full source-bank adapter')
        super().validate(events,cycle)
