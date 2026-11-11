"""Sticky full-field comparisons for real, unmodified parent instances."""
from collections import Counter
from copy import deepcopy

from toffee import CheckContext, Scoreboard, ScoreboardMode

from suites.frontend.bpu.testbenches.bpu.model.parent_primitives import ParentPrimitiveReference


class ParentPrimitiveChecker:
    def __init__(self):
        self.model = ParentPrimitiveReference()
        self.board = Scoreboard('bpu.parent-primitives')
        self.failure = None
        self.counts = Counter()
        self.lookups, self.control_frames = [], []
        self.diagnostics = []
        self.last_tick = None

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure

    def capture(self, before, actual, *, pre_tick, tick):
        if 'diagnostic' in actual:
            self.diagnostics.append(deepcopy(dict(tick=tick, before=before, actual=actual)))
        if self.failure is not None:
            return
        try:
            if tick != pre_tick + 1 or self.last_tick is not None and tick != self.last_tick + 2:
                raise AssertionError('parent primitive observation lost an exact clock boundary')
            expected = self.model.accept(before['controls'], fire=before['fire'], pc=before['pc'])
            self.board.check(expected=expected, actual={key: actual[key] for key in expected},
                context=CheckContext(self.board.name, ScoreboardMode.DIRECT, sequence_id=tick,
                                     request=deepcopy(before)))
            self.counts['paired_edges'] += 1
            if 'delayed' in expected:
                self.counts['delay_checked'] += 1
                self.control_frames.append(dict(tick=tick, inputs=deepcopy(before['controls']),
                    expected=deepcopy(expected['delayed']), actual=deepcopy(actual['delayed'])))
            if 'fallthrough' in expected:
                self.counts['fetch_checked'] += 1
                self.counts['fetch_accepted' if before['fire'] else 'fetch_held'] += 1
                self.lookups.append(dict(tick=tick, pc=self.model.lookup_pc, fire=before['fire'],
                    offered_pc=before['pc'], expected=deepcopy(expected['fallthrough']),
                    actual=deepcopy(actual['fallthrough'])))
            self.last_tick = tick
        except Exception as error:
            self.failure = error

    def finish(self):
        self.raise_failure()
        if self.counts['delay_checked'] < 2 or self.counts['fetch_accepted'] < 1:
            raise AssertionError('parent primitive scope did not establish defined delayed/fetch state')
        return deepcopy(dict(counts=dict(self.counts), lookups=self.lookups,
                             controls=self.control_frames))

    def diagnostic_report(self):
        return deepcopy(dict(counts=dict(self.counts), lookups=self.lookups,
            controls=self.control_frames, diagnostics=self.diagnostics,
            failure=None if self.failure is None else str(self.failure)))
