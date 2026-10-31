"""Every lookup and public history is compared; no fixed-point certification."""
from toffee import CheckContext, ScoreboardMode
from suites.frontend.bpu.bpu.checker.loop_iteration import LoopIterationChecks
from suites.frontend.bpu.bpu.model.common_query import CommonQueryReference
from suites.frontend.bpu.bpu.model.common_query import RULES


class CommonQueryChecks(LoopIterationChecks):
    def __init__(self, pipeline, *, query_coverage=None, **kwargs):
        super().__init__(pipeline, **kwargs)
        self.query_coverage = query_coverage
        self.query = CommonQueryReference()
        self.query_checked = self.query_issues = self.query_metadata = 0
        self.split_views = []

    def record_query(self, rule):
        coverage = self.query_coverage
        if coverage is not None and rule in RULES[coverage.profile]:
            coverage.record(rule, self.last_tick)

    def finish_query(self):
        self.raise_failure()
        self.check_query(True, self.completed, 'real original recovery and consumer checked before query credit')
        self.record_query('published-original-immutable')
        if self.query_coverage is not None:
            self.query_coverage.finish()
        return dict(checked=self.query_checked, issues=self.query_issues, metadata=self.query_metadata,
            split_views=self.split_views, reasons=dict(self.query.reasons))

    def check_query(self, expected, actual, point):
        try:
            self.pipeline.board.check(expected=expected, actual=actual,
                context=CheckContext(self.pipeline.board.name, ScoreboardMode.DIRECT,
                    sequence_id=self.last_tick, request=dict(point=point, history=self.query.state())))
        except Exception as error:
            self.failure = error
            raise

    def capture_state(self, event, row):
        if self.failure is not None:
            return
        try:
            recovery = None
            if row['iteration']['redirect']['valid'] and self.plans:
                source, branch, _ = self.plans[0]
                recovery = self.query.source_for(source.owner), branch
            super().capture_state(event, row['iteration'])
            if self.failure is not None or not self.initialized:
                return
            if row['iteration']['reset']:
                self.query.reset()
                self.query_checked = self.query_issues = self.query_metadata = 0
                self.split_views.clear()
                return
            self.check_query(self.query.value.mapping(), row['state'], 'registered completed conditional outcomes')
            cycle = self.pipeline.last_cycle
            step = self.query.preview(cycle, recovery=recovery)
            self.check_query(step.lookup.mapping(), row['lookup'], 'same-original S0 history, including invalid payload')
            self.check_query(step.iteration.after, row['iteration']['lookup'], 'same-original S0 iteration')
            if cycle.metadata is not None:
                source = self.query.snapshot(cycle.metadata)
                self.check_query(source.metadata.mapping(), row['published']['common'], 'same-original public history view')
                self.check_query(source.loop, row['published']['loop'], 'same-original public iteration')
                if source.read != source.metadata:
                    self.split_views.append(dict(sequence=source.sequence, read=source.read.mapping(),
                        feedback=source.metadata.mapping(), tick=event.tick))
                    self.record_query('restore-read-vs-feedback-view')
                self.query_metadata += 1
                self.record_query('original-public-history')
            self.query.apply(step, issued=self.pipeline.model.stages[0] if cycle.fires[0] else None)
            self.query_checked += 1
            self.query_issues += int(cycle.fires[0])
            if cycle.fires[0]:
                self.record_query('own-history-at-query')
            if cycle.tokens[0] is not None and not cycle.fires[1] and not cycle.flushes[0]:
                self.record_query('held-source-preserved')
            if step.reason == 'middle-reuse':
                self.record_query('young-replacement-history')
            if step.reason == 'backend-prefix':
                self.record_query('restore-executed-prefix')
            if step.reason == 'final-replay':
                self.record_query('late-replay-origin')
        except Exception as error:
            self.failure = error
