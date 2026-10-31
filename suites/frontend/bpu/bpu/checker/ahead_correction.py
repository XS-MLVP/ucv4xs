"""Complete actual states plus fresh direction-owned working-set consumers."""
from suites.frontend.bpu.bpu.checker.ahead_working_set import AheadWorkingSetChecks
from suites.frontend.bpu.bpu.model.ahead_correction import RULES


class AheadCorrectionChecks(AheadWorkingSetChecks):
    def __init__(self, program, coverage):
        super().__init__(program, coverage)
        self.rounds = []

    def consumer(self, events, cycle, sources):
        token = cycle.metadata
        if token is None or not events.metadata_ready or not self.phase.startswith(('warm', 'late')):
            return ()
        edges = {edge.pc:edge for edge in self.program.edges(0)}
        if token.pc not in edges: return ()
        edge = edges[token.pc]
        negative = self.phase.endswith('negative')
        desired = self.program.desired_branch(edge, negative=negative)
        final = cycle.decisions[2].branch
        self.check(desired, dict(taken=final.taken, position=final.position,
            target=final.target, kind=int(final.kind), action=int(final.action)),
            'complete final outcome belongs to this declared corrected or preserved branch')
        frame = sources.snapshot(token).frame
        if frame is None or not frame.valid: return ()
        ways = tuple(way for way, (hit, entry) in enumerate(zip(frame.hits, frame.read.entries, strict=True))
                     if hit and entry.position == edge.position and entry.kind == edge.kind)
        self.check(True, len(ways) <= 1, 'logical branch is not duplicated in one Ahead response')
        if not ways: return ()
        way, = ways
        counter = self.program.desired_counter(edge, negative=negative)
        early = token.early.branch
        actual_early = dict(taken=early.taken, position=early.position, target=early.target,
                            kind=int(early.kind), action=int(early.action))
        # Cold/transient early reads may still require the correctly checked
        # Main repair. They are not successful endpoint consumers, nor are
        # they errors merely because learning has not reached its endpoint.
        if frame.counters[way] != counter or actual_early != desired: return ()
        self._pending = (token.pc, dict(tick=self.pipeline.current_event.tick,
            counter=counter, kind=edge.kind, key=(frame.read.bank, frame.read.row, way),
            target=edge.target, source_sequence=token.sequence,
            source_history=token.history.history, taken=early.taken))
        return ()

    def finish(self):
        self.raise_failure()
        self.check(6, len(self.lifetimes), 'warm and late complete laps at all three direction endpoints')
        self.check([0, 0, 3, 3, 3], [row['goal'] for row in self.rounds],
                   'two genuine corrections and three genuine recoveries of each selected direction')
        self.check(len(self.program.edges(0))+5*len(self.program.selected), len(self.feedback_receipts),
                   'all initial discoveries and selected branch outcomes were actually accepted')
        self.check(tuple((resolve, redirect) for _, resolve, redirect in self.originals),
                   tuple((source.meta.resolve, source.meta.redirect) for source, _, _ in self.originals),
                   'direction reversal preserves every immutable original source')
        self.check(0, len(self.pending_services), 'every predicted Ahead service crossed full actual comparison')
        for rule in RULES:
            self.mark(rule, corrected=len(self.program.selected), feedback=len(self.feedback_receipts),
                      consumers=sum(row['consumers'] for row in self.lifetimes))
            self.coverage.record('checked', rule, **self.witnesses[rule])

    def close_lap(self):
        super().close_lap()
        if self.phase == 'late-positive':
            self.mark('warm-full-working-set', consumers=len(self.seen),
                      last_tick=max(row['tick'] for row in self.seen.values()))

    def summary(self):
        failure = None if self.pipeline is None else getattr(self.pipeline, 'failure', None)
        diagnostic = None
        context = getattr(failure, 'context', None)
        request = None if context is None else context.request
        if isinstance(request, dict) and 'short_history' in request:
            short = request['short_history']
            prediction = short['reference'].get('prediction')
            frame = None if prediction is None else prediction.frame
            if frame is not None:
                diagnostic = dict(tick=context.sequence_id,
                    expected_read_tags=tuple(entry.tag for entry in frame.read.entries),
                    observed_read_tags=tuple(short['observed_read_tags']),
                    expected=getattr(failure, 'expected', {}).get('early_direction'),
                    actual=getattr(failure, 'actual', {}).get('early_direction'),
                    classification='read-only cause evidence; never a golden seed or a waived failure')
        return dict(super().summary(), direction_rounds=list(self.rounds),
                    first_micro_direction_failure=diagnostic)
