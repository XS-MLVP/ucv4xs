"""Default independent predictor comparison, including filtered raw-hit sources."""
from collections import deque

from toffee import CheckContext, Scoreboard, ScoreboardMode

from bpuverify.mbtb.model.semantic import MbtbReference, tag


def prediction_values(expected, actual):
    observed = {}
    for slot, entry in enumerate(actual.entries):
        for name, attribute in dict(valid='valid', taken='taken', target='target', position='position',
                                    kind='branch_type', action='ras_action').items():
            if f'{slot}.{name}' in expected:
                observed[f'{slot}.{name}'] = getattr(entry, attribute)
        source = actual.meta_entries[slot // 2][slot % 2]
        names = dict(raw_hit=source['rawHit'], meta_position=source['position'],
            meta_kind=source['attribute']['branchType'], meta_action=source['attribute']['rasAction'],
            counter=source['counter_value'])
        observed.update({f'{slot}.{name}': value for name, value in names.items() if f'{slot}.{name}' in expected})
    return expected, observed


class MbtbSemanticChecker:
    def __init__(self):
        self.model = MbtbReference()
        self.board = Scoreboard('mbtb.semantic-reference')
        self.failure = None
        self.failure_observed = self.initialized = False
        self.events = self.input_tick = None
        self.expected = deque(maxlen=64)
        self.accepted_feedback = deque(maxlen=64)
        self.accepted_cleanup = deque(maxlen=64)

    def raise_failure(self):
        if self.failure is not None:
            self.failure_observed = True
            raise self.failure

    def raise_unobserved_failure(self):
        if not self.failure_observed:
            self.raise_failure()

    def capture_input(self, event, events):
        if self.failure is not None:
            return
        try:
            if events.reset:
                self.initialized = True
            if self.initialized:
                previous = self.model.frame
                if not events.reset and events.ready and events.consume and previous is not None:
                    for align, read in enumerate(previous.banks):
                        eligible = [(way, entry) for way, entry in enumerate(read.entries)
                            if entry.valid and entry.tag == tag(read.pc) and entry.position >= read.pc % 8
                            and not read.cross_page]
                        if len(eligible) == 2 and eligible[0][1].position == eligible[1][1].position:
                            self.accepted_cleanup.append(dict(tick=event.tick, align=align, bank=read.bank,
                                row=read.row, way=eligible[1][0], tag=eligible[1][1].tag,
                                position=eligible[1][1].position))
                self.model.advance(events)
                if not events.reset and events.ready and self.model.offered is not None:
                    self.accepted_feedback.append((event.tick, self.model.offered.feedback))
            self.events, self.input_tick = events, event.tick
        except Exception as error:
            self.failure = error

    def _check(self, wanted, actual, context):
        expected, observed = prediction_values(wanted, actual)
        self.board.check(expected=expected, actual=observed, context=context)

    def capture_output(self, event, actual, *, enabled):
        if self.failure is not None or not self.initialized:
            return
        try:
            if self.input_tick != event.tick - 1:
                raise AssertionError('MBTB reference requires one public input boundary per clock')
            frame = self.model.frame
            wanted = frame.values(enabled) if frame is not None else None
            self.expected.append((event.tick, frame, wanted, self.events.enabled))
            if self.events.reset or not self.events.ready or wanted is None:
                return
            self._check(wanted, actual, CheckContext(self.board.name, ScoreboardMode.DIRECT,
                sequence_id=event.tick, request=dict(events=self.events, state=self.model.state()), observed_event=event))
        except Exception as error:
            self.failure = error

    def response_expected(self, request, context):
        tick = context.accepted_event.tick + 4

        def compare(actual):
            self.raise_failure()
            matches = [(frame, wanted, enabled) for at, frame, wanted, enabled in self.expected if at == tick]
            if len(matches) != 1 or matches[0][0] is None:
                raise AssertionError(f'no independent MBTB response at {tick}')
            frame, wanted, enabled = matches[0]
            if enabled:
                self.board.check(expected=request.pc, actual=frame.pc, context=context)
            self._check(wanted, actual, context)

        return compare
