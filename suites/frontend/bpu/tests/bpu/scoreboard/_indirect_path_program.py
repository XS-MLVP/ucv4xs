"""Pure semantic program helper; not imported by production verification code."""
from bpuverify.common.model.configuration import TAGE_ALLOCATION_WAIT, TAGE_HISTORIES, TAGE_TABLES, PHR_STORAGE_BITS
from copy import deepcopy
from dataclasses import replace
from bpuverify.bpu.model.early_joint_sources import EarlyJointSources
from bpuverify.bpu.model.pipeline import Outcome, Resolution
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.path_history import path_contribution
from tests.bpu.scoreboard.test_early_late_sources import Program as Foundation


class Program(Foundation):
    def __init__(self, pc, *, flowing, sources_factory=None):
        super().__init__(pc, sources_factory=EarlyJointSources if sources_factory is None else sources_factory)
        self.flowing = flowing
        enabled = list(self.event.enabled)
        enabled[5] = True
        self.event = replace(self.event, enabled=tuple(enabled))
        while self.model.control_pipe[-1] != self.event.enabled:
            self.model.advance(replace(self.event, reset=True))
        self.feedbacks = []

    def controls(self, *, early=None, target=None):
        self.quiet()
        enabled = list(self.event.enabled)
        if early is not None:
            enabled[1] = early
        if target is not None:
            enabled[5] = target
        self.event = replace(self.event, enabled=tuple(enabled))
        for _ in range(8):
            self.step(replace(self.event, prediction_ready=False))
            if self.model.control_pipe[-1] == self.event.enabled:
                break
        else:
            raise AssertionError('controls never became active')
        self.quiet()

    def early_enabled(self, value):
        self.controls(early=value)

    def resolve(self, source, position, taken, *, wrong, room=False, kind=None, target=None):
        idle = self.quiet()
        if target is None:
            target = self.pc if source.pc == self.a else self.a
        if kind is None:
            kind = Kind.CONDITIONAL if position == 2 else Kind.DIRECT
        request = Resolution(source.history, source.pc,
            (Outcome(position, target, kind, taken, mispredict=wrong),), origin=source)
        if room:
            feedback = self.model.sources.feedback_for(request)
            for _ in range(TAGE_ALLOCATION_WAIT):
                owner = self.model.sources.tage.allocation_at_next_accept(feedback)
                if owner is not None and owner[0] < TAGE_TABLES-1:
                    break
                self.step(idle)
            else:
                raise AssertionError('no longer-history allocation opportunity')
        self.step(replace(idle, feedback=request))
        self.feedbacks.append(request)
        self.quiet()

    def prepare(self):
        self.anchor = self.source(pc=self.a)
        self.resolve(self.anchor, 4, True, wrong=True)
        source = self.query()
        self.resolve(source, 2, True, wrong=True)
        self.seed = self.warm()
        self.controls(early=False)
        source = self.query()
        self.resolve(source, 2, False, wrong=True, room=True)
        source = self.query()
        self.resolve(source, 2, False, wrong=False)
        source = self.query()
        self.resolve(source, 4, True, wrong=True, kind=Kind.INDIRECT)
        # The natural A4 -> B4 -> A path establishes the independent history.
        edge = (path_contribution((self.a // 16) * 16 + 4, self.pc) << 2) ^ path_contribution((self.pc // 16) * 16 + 4, self.a)
        recent = 0
        for bit in range(0, max(TAGE_HISTORIES), 4):
            recent ^= edge << bit
        recent %= 1 << max(TAGE_HISTORIES)
        self.restart()
        self.anchor = self.source(lambda t: t.history.history % (1 << max(TAGE_HISTORIES)) == recent, pc=self.a)
        # Every target observation comes from a real, separately published B.
        target_originals = []
        for number in range(3):
            source = self.query()
            target_originals.append(source)
            self.resolve(source, 4, True, wrong=number == 0, kind=Kind.INDIRECT)
        target = self.query()
        prediction = self.model.sources.target_snapshot(target, resolved=True).prediction
        assert prediction.provider is not None and prediction.target // 2 == self.a
        assert prediction.confidence == 3
        frozen_target = deepcopy(self.model.sources.defined_ittage_metadata(target))
        # Only Main learns the new wrong target; ITTAGE's old target is retained.
        self.controls(target=False)
        wrong = self.query()
        self.resolve(wrong, 4, True, wrong=True, kind=Kind.INDIRECT, target=self.a + 0x200)
        self.controls(target=True)
        self.controls(early=True)
        self.restart()
        accepted = None
        middle = None
        cancelled = None
        for _ in range(256):
            cycle = self.model.evaluate(self.event)
            first = cycle.tokens[0]
            if first is not None and first.pc == self.pc and cycle.fires[1] and not cycle.flushes[0]:
                if cycle.decisions[0].source in ('ahead', 'ahead-direction') and cycle.decisions[0].branch.position == 2:
                    accepted = first.sequence
            if cycle.middle_repair and cycle.tokens[1].sequence == accepted:
                middle = (cycle.tokens[1], cycle.decisions[1])
            if cycle.final_repair and cycle.tokens[2].sequence == accepted:
                cancelled = cycle.tokens[0]
                window = self.event if self.flowing else replace(self.event, prediction_ready=False)
                cycle = self.step(window)
                token = cycle.tokens[2]
                assert middle is not None
                assert middle[1].branch.kind == Kind.INDIRECT
                assert middle[1].branch.target == self.a + 0x200
                assert cycle.decisions[2].source == 'indirect-history'
                assert cycle.decisions[2].branch.target == self.a
                assert cycle.decisions[2].branch.kind == Kind.INDIRECT
                assert token.history is self.model.sources.target_snapshot(token, resolved=True).owner
                assert token.history is self.model.sources.short_snapshot(token).owner
                assert token.history is self.model.sources.tage_snapshot(token).owner
                assert cancelled is not None and cancelled.pc == self.a + 0x200
                expected = ((token.history.history << 2) ^ path_contribution((token.pc // 16) * 16 + 4, self.a)) % (1 << PHR_STORAGE_BITS)
                assert self.model.history.history == expected
                assert cancelled.sequence not in {t.sequence for t in self.model.stages if t is not None}
                assert self.model.sources.defined_ittage_metadata(target) == frozen_target
                feedback = self.model.sources.last_short_events.feedback
                assert feedback is not None and feedback.position == 4 and feedback.kind == int(Kind.INDIRECT)
                assert any(s.valid and s.position == 2 for s in feedback.sources)
                assert feedback.context.folds == self.model.sources.short_snapshot(token).prediction.frame.context.folds
                self.quiet()
                return dict(owner=token.sequence, original_history=token.history.history,
                    restored_history=expected, early_target=token.early.branch.target,
                    middle_target=middle[1].branch.target, final_target=cycle.decisions[2].branch.target,
                    cancelled=dict(owner=cancelled.sequence, pc=cancelled.pc, history=cancelled.history.history),
                    held=not self.flowing, feedbacks=len(self.feedbacks),
                    six_components=['micro', 'main', 'ahead', 'short', 'tage', 'indirect'])
            self.step()
        raise AssertionError('no exact original with early direction, middle target, final target and younger cancellation')
