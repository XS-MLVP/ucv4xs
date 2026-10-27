"""Compare every defined public branch field; no actual-to-golden feedback."""
from collections import deque

from toffee import CheckContext, Scoreboard, ScoreboardMode

from bpuverify.abtb.model.semantic import AbtbReference, coordinate


def prediction_values(expected, actual):
    observed = dict(meta_valid=actual.meta['valid'])
    if 'row' in expected:
        observed.update(row=actual.meta['setIdx'], banks=actual.meta['bankMask'])
    for way, entry in enumerate(actual.entries):
        names = dict(valid='valid', taken='taken', target='target', position='position',
                     kind='branch_type', action='ras_action')
        for label, attribute in names.items():
            if f'{way}.{label}' in expected:
                observed[f'{way}.{label}'] = getattr(entry, attribute)
        meta, micro = actual.meta['entries'][way], actual.micro_tage['result'][way]
        observed[f'{way}.micro_valid'] = micro['valid']
        if f'{way}.meta_hit' in expected:
            observed[f'{way}.meta_hit'] = meta['hit']
        if f'{way}.target_low' in expected:
            observed[f'{way}.target_low'] = meta['targetLowerBits']
            observed[f'{way}.strong'] = micro['bits']['isStrongBias']
            for label, value in (('position', meta['position']), ('kind', meta['attribute']['branchType']),
                                 ('action', meta['attribute']['rasAction'])):
                observed[f'{way}.meta_{label}'] = value
            for label, value in (('taken', micro['bits']['taken']), ('position', micro['bits']['cfiPosition']),
                                ('kind', micro['bits']['attribute']['branchType']),
                                ('action', micro['bits']['attribute']['rasAction'])):
                observed[f'{way}.micro_{label}'] = value
    wanted = dict(expected)
    for way in range(4):
        if f'{way}.target_low' in wanted:
            for label in ('position', 'kind', 'action'):
                wanted[f'{way}.meta_{label}'] = wanted[f'{way}.{label}']
            for label in ('taken', 'position', 'kind', 'action'):
                wanted[f'{way}.micro_{label}'] = wanted[f'{way}.{label}']
    return wanted, observed


class AbtbSemanticChecker:
    def __init__(self):
        self.model = AbtbReference()
        self.board = Scoreboard('abtb.semantic-reference')
        self.failure = None
        self.failure_observed = self.initialized = False
        self.events = self.input_tick = None
        self.expected = deque(maxlen=64)
        self.accepted_feedback = deque(maxlen=64)

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
                self.model.advance(events)
                if not events.reset and events.ready and self.model.offered is not None:
                    self.accepted_feedback.append((event.tick, self.model.offered))
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
                raise AssertionError('ABTB reference requires one public input boundary per clock')
            wanted = self.model.values(enabled)
            self.expected.append((event.tick, self.model.frame, wanted, enabled))
            if self.events.reset or not self.events.ready:
                return
            self._check(wanted, actual, CheckContext(self.board.name, ScoreboardMode.DIRECT,
                sequence_id=event.tick, request=dict(events=self.events, state=self.model.state()), observed_event=event))
        except Exception as error:
            self.failure = error

    def response_expected(self, request, context):
        tick = context.accepted_event.tick + 4

        def compare(actual):
            self.raise_failure()
            matches = [(frame, values, enabled) for at, frame, values, enabled in self.expected if at == tick]
            if len(matches) != 1:
                raise AssertionError(f'no independent ABTB response at {tick}')
            frame, wanted, enabled = matches[0]
            if enabled and request.override is None:
                if frame is None or not frame.valid:
                    # A redirect can flush the window that this accepted
                    # lookup owned.  That is not a licence to skip checking:
                    # the public response must then be a complete flush, and
                    # every defined field below is still compared.
                    if actual.meta['valid'] != 0 or any(entry.valid for entry in actual.entries):
                        raise AssertionError(
                            'flushed ABTB window published a prediction instead of a flush')
                else:
                    self.board.check(expected=(request.pc, coordinate(request.pc, request.path_hash)),
                        actual=(frame.pc, (frame.read.bank, frame.read.row)), context=context)
            self._check(wanted, actual, context)

        return compare
