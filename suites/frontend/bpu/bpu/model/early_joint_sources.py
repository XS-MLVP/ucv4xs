"""Six independent semantic facets, one original-owner pipeline.

No DUT, sampled payload, duplicate base predictor or new prediction algorithm.
Each facet retains its own original checkpoint namespace.  Component snapshots remain in explicitly named ownership domains.
"""
from suites.frontend.bpu.models.configuration import *
from dataclasses import replace

from suites.frontend.bpu.bpu.model.early_late_sources import EarlyLateSources
from suites.frontend.bpu.bpu.model.indirect_sources import IndirectSnapshot, allocation, context_for
from suites.frontend.bpu.bpu.model.joint_sources import _TargetState
from suites.frontend.bpu.bpu.model.selection import final
from suites.frontend.bpu.ittage.model.semantic import Context, Events


class EarlyJointSources(EarlyLateSources):
    has_own_ittage = True
    unsupported_learning = (4, 6)

    def __init__(self):
        super().__init__()
        self.targets = _TargetState()

    @property
    def indirect(self):
        return self.targets.indirect

    @property
    def random(self):
        return self.targets.random

    def reset(self):
        super().reset()
        self.targets.reset()

    def capture(self, pc, checkpoint):
        frame = super().capture(pc, checkpoint)
        self.targets.reads[checkpoint.sequence] = IndirectSnapshot(checkpoint)
        return frame

    def target_snapshot(self, token, *, resolved=False):
        return self.targets.snapshot(token, resolved=resolved)

    def defined_ittage_metadata(self, token, *, service_enabled=None):
        return self.targets.metadata(token,service_enabled=service_enabled)

    def random_at_sample(self, events):
        return self.targets.random_at_sample(events)

    def choose(self, token, stage, enabled):
        if stage == 3:
            return self.target_snapshot(token, resolved=True).late
        return super().choose(token, stage, enabled)

    def validate(self, events, cycle):
        if events.feedback is not None:
            active = [b for b in events.feedback.branches if b is not None]
            first_taken = min((b.position for b in active if b.taken), default=None)
            if first_taken is not None and any(b.position > first_taken for b in active):
                raise ValueError('resolved execution prefix contains an unexecuted younger branch')
        super().validate(events, cycle)
        enabled = bool(cycle.enabled[2] and cycle.enabled[5])
        trained = any(memory for banks in self.indirect.memories for memory in banks)
        if enabled != self.targets.indirect_enabled and trained and (
                any(cycle.tokens[1:]) or (cycle.tokens[0] is not None
                    and cycle.fires[1] and not cycle.flushes[0])):
            raise NotImplementedError('trained ITTAGE transition needs drained older stages and a held/flushed S1')
        self.targets.indirect_enabled = enabled
        if events.feedback is not None and enabled:
            self.targets.feedback_for(events.feedback)

    def advance(self, events, cycle, issued):
        enabled = bool(cycle.enabled[2] and cycle.enabled[5])
        first, second, _ = cycle.tokens
        third = cycle.tokens[2]
        if third is not None and events.redirect is None:
            source = self.target_snapshot(third,resolved=True)
            self.targets.resolved[third.history.sequence] = replace(source,published_enabled=enabled)
        random = self.random_at_sample(events)
        if first is not None and cycle.fires[1] and enabled:
            source = self.target_snapshot(first)
            self.targets.reads[first.history.sequence] = replace(source,
                read=self.indirect.lookup_snapshot(first.pc * 2, context_for(first.history)))
        joint = None
        if second is not None and not cycle.flushes[1]:
            source = self.target_snapshot(second)
            prediction = None
            if enabled and source.read is not None:
                prediction = self.indirect.predict_snapshot(source.read)
            elif enabled and second.lookup is not None:
                raise ValueError('enabled joint target has no independently owned S1 read')
            branches, wanted, _ = self.tage_decision(second, bool(cycle.enabled[2] and cycle.enabled[3]))
            directions = tuple(bool(wanted[f'{slot}.taken']) if wanted.get(f'{slot}.valid') else None
                for slot in range(RESULT_SLOTS))
            target = None if prediction is None or prediction.provider is None else prediction.target // 2
            joint = final(second.pc, branches, directions, (None,) * RESULT_SLOTS, indirect_target=target)
            self.targets.resolved[second.history.sequence] = replace(source, enabled=enabled,
                prediction=prediction, allocation=None if prediction is None else allocation(prediction, random),
                late=joint)
        feedback = self.targets.feedback_for(events.feedback) if events.feedback is not None and enabled else None
        self.indirect.advance(Events(pc=None if issued is None else issued.pc * 2,
            context=Context() if first is None else context_for(first.history), access=cycle.fires[1],
            select=cycle.fires[2], feedback=feedback, enabled=enabled, reset=bool(events.consumed_reset)))
        self.targets.random = random
        # One base pipeline, one early pipeline, one direction facet.  Their S3
        # teachers consume cycle.decisions[2], already the owned joint outcome.
        super().advance(events, cycle, issued)
        if joint is not None:
            saved = self.tage_snapshot(second, resolved=True)
            self.directions.resolved[second.history.sequence] = replace(saved, late=joint)

    def retain(self, tokens):
        tokens = tuple(tokens)
        super().retain(tokens)
        keys = {token.history.sequence for token in tokens}
        self.targets.reads = {key: value for key, value in self.targets.reads.items() if key in keys}
        self.targets.resolved = {key: value for key, value in self.targets.resolved.items() if key in keys}

    def main_pending(self):
        return super().main_pending() or self.targets.pending()
