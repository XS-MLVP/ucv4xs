"""Compare logical ownership; actual retention cells only qualify the window."""
from toffee import CheckContext, Scoreboard, ScoreboardMode, TransferState

from bpuverify.utage.checker.source_ownership import actual_fields
from bpuverify.utage.model.read_ownership import RETAINED_VERSIONS, RULES
from bpuverify.utage.model.semantic import indices, tag
from bpuverify.utage.model.source_ownership import POSITION


class ReadOwnershipChecks:
    def __init__(self, program, coverage):
        program.validate()
        self.program, self.coverage = program, coverage
        self.board = Scoreboard('utage.inflight-learning-ownership')
        self.completed = set()
        self.public_feedback = []
        self.window = None

    def check(self, expected, actual, point):
        self.board.check(expected=expected, actual=actual, context=CheckContext(
            self.board.name, ScoreboardMode.DIRECT,
            request=dict(point=point, program=self.program.state(), window=self.window)))

    def reached(self, rule, **witness):
        self.coverage.record('reached', rule, **witness)

    def end(self, rule):
        self.completed.add(rule)

    def profile(self, profile, prediction, base):
        expected = profile.expected(base)
        self.check(expected, actual_fields(prediction, expected), 'original logical record '+profile.name)

    def observe(self, row):
        public = row.shadow['public']
        if public['valid']:
            self.public_feedback.append(public['bits'])

    def feedback_once(self, ledger, expected):
        self.check(RETAINED_VERSIONS + 1, len(ledger.consumed), 'one real source per learning version')
        self.check(len(ledger.sources), len(ledger.consumed), 'no unused or repeated learning source')
        self.check(tuple(expected), tuple(self.public_feedback), 'complete actual feedback accepted once')
        self.reached('original-feedback-once', accepted=len(self.public_feedback))
        self.end('original-feedback-once')

    def actual_reuse(self, records, transfers):
        p = self.program
        original = dict(valid=1, data_valid=1, index=p.original.indices[0],
            tag=tag(p.original.pc, p.original.context, 0), position=POSITION, counter=3)
        learned = dict(valid=1, data_valid=1, index=p.learning.indices[0],
            tag=tag(p.learning.pc, p.learning.context, 0), position=POSITION, counter=7)
        windows = []
        for before, after in zip(records, records[1:]):
            if (before.inputs is None or not before.inputs.select or not before.inputs.advance
                    or before.inputs.override is not None
                    or before.inputs.read_pc != p.original.pc
                    or before.inputs.pc != p.learning.pc or before.inputs.context != p.learning.context):
                continue
            if indices(before.inputs.read_pc, before.inputs.read_context) != p.original.indices:
                continue
            for slot, cell in enumerate(before.shadow['cells']):
                if cell != original or after.shadow['cells'][slot] != learned:
                    continue
                accepted = [t for t in transfers if t.accepted_event is not None
                    and t.accepted_event.tick <= before.tick < after.tick
                    and (t.completed_event is None or t.completed_event.tick >= after.tick)
                    and t.request.read_pc == p.original.pc and t.request.pc == p.learning.pc
                    and t.request.read_history == p.original.history
                    and t.request.folded_history == p.learning.history
                    and t.request.position == POSITION and t.request.base_taken == 0
                    and t.request.override is None]
                meta = after.prediction.meta
                # The returned identity must itself still be the query's A0/A1
                # pair. A fresh B read after learning is not an overlap witness.
                if (accepted and tuple(meta['readIndex']) == p.original.indices
                        and tuple(row['foldedHist'] for row in meta['foldedPathHistForTrain_hist'])
                            == p.learning.context.folds):
                    windows.append(dict(before_tick=before.tick, reuse_tick=after.tick,
                        query_accepted_ticks=tuple(t.accepted_event.tick for t in accepted),
                        physical_slot=slot, original=cell, new=after.shadow['cells'][slot],
                        actual_return=actual_fields(after.prediction, p.query_expected()),
                        selected=tuple(after.shadow['hits']), response=after.shadow['response']))
        self.check(1, len(windows), 'one actual reuse while an original query is returning')
        self.window = windows[0]
        self.reached('actual-inflight-reuse', **self.window)
        self.end('actual-inflight-reuse')
        return self.window

    def responses(self, transfers, actuals):
        self.check(True, len(transfers) >= 2, 'actual pipeline queries are required')
        self.check(len(transfers), len(actuals), 'each submitted query has one actual response')
        self.check(True, all(t.state is TransferState.COMPLETED for t in transfers),
                   'all query responses completed through driver/monitor association')
        self.check(True, all(a.accepted_event.tick < b.accepted_event.tick < a.completed_event.tick
            for a, b in zip(transfers, transfers[1:])), 'query responses overlap, not serialized lookalikes')
        self.reached('complete-original-response', responses=len(actuals))
        for actual in actuals:
            expected = self.program.query_expected()
            self.check(expected, actual_fields(actual, expected), 'return remains original A, never replacement B')
        self.end('complete-original-response')

    def finish(self, originals):
        self.reached('immutable-original-sources')
        self.check(True, len(originals) >= RETAINED_VERSIONS + 1,
                   'all learned versions have original immutable query evidence')
        self.check(tuple(frozen for _, frozen in originals), tuple(source.meta for source, _ in originals),
                   'all original metadata unchanged by later learning and queries')
        self.end('immutable-original-sources')
        self.check(set(RULES), self.completed, 'all ownership requirements checked')
        # No checked credit from preparation or a partial failing window.
        for rule in RULES:
            self.coverage.record('checked', rule)
