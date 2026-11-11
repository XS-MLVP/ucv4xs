"""Passive composition witnesses; no model/checker is lent to a testcase.

Moved from the original composition tests without changing their comparisons.
These classes extend the same autonomous pipeline checker. Only successful
compared cycles can contribute to a witness; a prior failure stays sticky.
"""
from collections import defaultdict

from suites.frontend.bpu.testbenches.abtb.model.semantic import coordinate
from suites.frontend.bpu.testbenches.bpu.checker.pipeline import PipelineChecker
from suites.frontend.bpu.testbenches.bpu.model.ahead_sources import history_feature


class BothLiveChecker(PipelineChecker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.both_compared = []

    def capture(self, row, event):
        super().capture(row, event)
        if self.failure is not None or not self.records or self.last_tick != event.tick:
            return
        expected = self.records[-1]['expected']
        if 'ahead' not in expected or 'main_metadata' not in expected:
            return
        ahead, main = expected['ahead'], expected['main_metadata']
        self.both_compared.append(dict(
            tick=event.tick,
            ahead_hits=tuple(ahead.get(f'{way}.meta_hit') for way in range(4)),
            main_hits=tuple(main[f'{alignment}.{way}.hit']
                            for alignment in range(2) for way in range(2)),
            early_source=expected.get('early_source'), choice2=expected.get('choice2')))


class SharedRedirectChecker(PipelineChecker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shared_redirect_cycles = []
        self.post_redirect_cycles = []
        self._pending = None

    @staticmethod
    def _window(expected):
        ahead, early = expected['ahead'], expected['early_direction']
        return dict(
            ahead_meta_valid=ahead.get('meta_valid'),
            ahead_hits=tuple(ahead.get(f'{way}.meta_hit') for way in range(4)),
            ahead_valids=tuple(ahead.get(f'{way}.valid') for way in range(4)),
            early_hits=early.get('raw_hits'),
            early_valids=tuple(early.get(f'{way}.valid') for way in range(4)))

    def capture(self, row, event):
        redirect_valid = bool(row.get('inputs', {}).get('redirect', {}).get('valid'))
        super().capture(row, event)
        if (self.failure is not None or self.last_tick != event.tick
                or not self.records or self.records[-1]['tick'] != event.tick):
            return
        expected = self.records[-1]['expected']
        both = 'ahead' in expected and 'early_direction' in expected
        if redirect_valid and both:
            record = dict(tick=event.tick, prediction_valid=expected.get('prediction_valid'),
                          **self._window(expected))
            self.shared_redirect_cycles.append(record)
            self._pending = record
        elif self._pending is not None and event.tick == self._pending['tick'] + 2:
            if both:
                self.post_redirect_cycles.append(dict(
                    tick=event.tick, after=self._pending['tick'], **self._window(expected)))
            self._pending = None


def _flatten(mapping, prefix=''):
    for key, value in mapping.items():
        name = f'{prefix}{key}'
        if isinstance(value, dict):
            yield from _flatten(value, name + '.')
        elif isinstance(value, (list, tuple)) and value and isinstance(value[0], dict):
            for index, item in enumerate(value):
                yield from _flatten(item, f'{name}.{index}.')
        elif isinstance(value, set):
            yield name, tuple(sorted(map(str, value)))
        else:
            yield name, value


class FieldTally(PipelineChecker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.values, self.actuals = defaultdict(set), defaultdict(set)
        self.samples = 0

    def capture(self, row, event):
        super().capture(row, event)
        if self.failure is not None or not self.records or self.last_tick != event.tick:
            return
        record = self.records[-1]
        self.samples += 1
        for key, value in _flatten(record['expected']):
            self.values[key].add(value)
        for key, value in _flatten(record['actual']):
            self.actuals[key].add(value)


class CollisionChecker(PipelineChecker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.collisions = []

    def capture(self, row, event):
        super().capture(row, event)
        if self.failure is not None or not self.records or self.last_tick != event.tick:
            return
        expected = self.records[-1]['expected']
        redirect = bool(expected.get('flushes', (0, 0, 0))[2])
        training = row['inputs']['training']
        if not redirect or not (training['valid'] and training['ready']):
            return
        events = self.last_events
        self.collisions.append(dict(
            tick=event.tick, model_has_redirect=events.redirect is not None,
            model_has_feedback=events.feedback is not None,
            middle_repair=expected.get('repair2'), final_repair=expected.get('repair3')))


class HistoryIndexChecker(CollisionChecker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.awaiting = None
        self.later_reads = []

    def capture(self, row, event):
        super().capture(row, event)
        if self.failure is not None or not self.records or self.last_tick != event.tick:
            return
        expected, actual = self.records[-1]['expected'], self.records[-1]['actual']
        if self.awaiting is not None:
            events = self.last_events
            if events is not None:
                ahead_events = self.model.sources.last_ahead_events
                if ahead_events is not None and ahead_events.select:
                    self.later_reads.append(dict(tick=event.tick, read_pc=ahead_events.read_pc,
                                                history=ahead_events.history))
            ahead = expected.get('ahead')
            if isinstance(ahead, dict) and ahead.get('row') is not None:
                self.awaiting.update(
                    next_tick=event.tick, next_row=ahead.get('row'), next_banks=ahead.get('banks'),
                    next_actual_row=actual['ahead'].get('row'),
                    next_actual_banks=actual['ahead'].get('banks'), later_reads=list(self.later_reads))
                self.awaiting = None
            elif event.tick > self.awaiting['tick'] + 32:
                self.awaiting = None
        if not self.collisions:
            return
        record = self.collisions[-1]
        if record['tick'] != event.tick or 'index_used' in record:
            return
        events, cycle = self.last_events, self.last_cycle
        if events is None or events.feedback is None or cycle is None:
            return
        origin = events.feedback.source
        live = self.model.history.history
        origin_feature, live_feature = history_feature(origin), live % 16
        read_pc = cycle.next_pc
        origin_coordinate = coordinate(read_pc, origin_feature)
        live_coordinate = coordinate(read_pc, live_feature)
        record.update(
            origin_history=origin.history, live_history=live, history_advanced=origin.history != live,
            origin_feature=origin_feature, live_feature=live_feature,
            index_used=self.model.sources.last_ahead_events.history,
            origin_coordinate=origin_coordinate, live_coordinate=live_coordinate,
            coordinates_differ=origin_coordinate != live_coordinate, read_pc=read_pc)
        self.awaiting = record


def discriminating_target(token, pc=0x40000000):
    """Choose an input, not an actual-derived oracle: change the low hash bits."""
    origin_feature = token.history.history % 16
    for target in (pc + 2 * step for step in range(16)):
        if (target // 2) % 16 != origin_feature:
            return target
    raise AssertionError('no redirect target discriminates the two history features')
