"""Seven existing predictor algorithms, with one owned query/feedback history.

SC reads belong to S0 originals, selections to their S2 passage, and feedback
to the separately published history view. No observed state seeds a model.
RAS is explicitly outside this profile; the six-component profile is intact.
"""
from dataclasses import replace

from bpuverify.bpu.model.common_query import CommonQueryReference
from bpuverify.bpu.model.early_joint_sources import EarlyJointSources
from bpuverify.bpu.model.sc.ownership import OwnedStatisticalReference
from bpuverify.bpu.model.selection import Branch
from bpuverify.sc.model.semantic import Context, Events, feedback_needs_read


class StatisticalJointSources(EarlyJointSources):
    has_own_sc = True
    unsupported_learning = (6,)

    def __init__(self):
        super().__init__()
        self.queries = CommonQueryReference()
        self.statistical = OwnedStatisticalReference()
        self.statistical_enabled = False
        self.read_enabled = {}

    @property
    def sc(self):
        return self.statistical.model

    def reset(self):
        super().reset()
        self.queries.reset()
        self.statistical.reset()
        self.statistical_enabled = False
        self.read_enabled.clear()

    def statistical_snapshot(self, token, *, resolved=False):
        return self.statistical.snapshot(token, resolved=resolved)

    def choose(self, token, stage, enabled):
        if stage == 3:
            return self.statistical_snapshot(token, resolved=True).late
        return super().choose(token, stage, enabled)

    def preview_history(self, events, cycle):
        recovery = None
        if events.redirect is not None:
            request = events.redirect
            if request.kind is None:
                raise ValueError('SC/CommonHR recovery requires the actual semantic branch kind')
            source = self.queries.source_for(request.source)
            recovery = source, Branch(request.cfi_pc - source.pc // 16 * 16,
                request.target, request.kind, request.taken)
        return self.queries.preview(cycle, recovery=recovery)

    def sc_feedback(self, resolution, enabled):
        return self.statistical.feedback_for(resolution) if resolution is not None and enabled else None

    def validate(self, events, cycle):
        # All obligations that could reject a submitted feedback are checked
        # before *any* predictor consumes this boundary.
        super().validate(events, cycle)
        enabled = bool(cycle.enabled[2] and cycle.enabled[4])
        if enabled != self.statistical_enabled and (any(cycle.tokens[1:]) or (
                cycle.tokens[0] is not None and cycle.fires[1] and not cycle.flushes[0])):
            raise NotImplementedError('SC enable transition needs drained older stages and a held/flushed S1')
        second = cycle.tokens[1]
        if second is not None and not cycle.flushes[1] and enabled and not self.read_enabled[second.history.sequence]:
            raise NotImplementedError('SC selection needs a genuinely enabled original query; flush the old held source')
        self.preview_history(events, cycle)
        transaction = self.sc_feedback(events.feedback, enabled)
        if transaction is not None and feedback_needs_read(transaction) and cycle.fires[0] and cycle.next_pc % 2 == transaction.pc % 2:
            raise AssertionError('SC accepts conflicting prediction and feedback reads in one bank')
        self.statistical_enabled = enabled

    def advance(self, events, cycle, issued):
        enabled = bool(cycle.enabled[2] and cycle.enabled[4])
        step = self.preview_history(events, cycle)
        self.queries.apply(step, issued=issued)
        if issued is not None:
            self.statistical.capture(issued, history=self.queries.sc_history(issued))
            self.read_enabled[issued.history.sequence] = enabled
        feedback = self.sc_feedback(events.feedback, enabled)
        second, third = cycle.tokens[1:]
        if third is not None:
            self.statistical.publish(third, history=self.queries.sc_history(third, feedback=True))
        # The S0 weight read was frozen above. T1 learning changes thresholds
        # at this edge, so S2 selection sees that independently predicted value.
        self.statistical.advance(Events(pc=None if issued is None else issued.pc,
            context=Context() if issued is None else Context.from_history(self.queries.sc_history(issued)),
            feedback=feedback, feedback_context=Context() if feedback is None else Context.from_history(feedback.history),
            enabled=enabled, reset=bool(events.consumed_reset)))
        super().advance(events, cycle, issued)
        if second is not None and not cycle.flushes[1]:
            result = self.statistical.resolve(second,
                direction=self.tage_snapshot(second, resolved=True),
                target=self.target_snapshot(second, resolved=True), enabled=enabled)
            key = second.history.sequence
            self.directions.resolved[key] = replace(self.directions.resolved[key], late=result.late)
            self.targets.resolved[key] = replace(self.targets.resolved[key], late=result.late)

    def retain(self, tokens):
        tokens = tuple(tokens)
        keys = {token.history.sequence for token in tokens}
        if self.queries.pending is not None and self.queries.pending[0].owner.sequence not in keys:
            raise ValueError('a pending recovery still owns this query history')
        super().retain(tokens)
        self.queries.sources = {k: v for k, v in self.queries.sources.items() if k in keys}
        self.queries.iterations.owned = {k: v for k, v in self.queries.iterations.owned.items() if k in keys}
        for name in ('reads', 'resolved', 'feedback_histories'):
            values = getattr(self.statistical, name)
            setattr(self.statistical, name, {k: v for k, v in values.items() if k in keys})
        self.read_enabled = {k: v for k, v in self.read_enabled.items() if k in keys}

    def main_pending(self):
        return (super().main_pending() or self.queries.pending is not None or self.sc.learning is not None
            or bool(self.sc.pending) or any(row is not None and row.dirty
                for banks in self.sc.writes for cache in banks for row in cache.rows))
