"""Exact qualified prediction fields and independent legal allocation sets."""
from collections import deque

from toffee import CheckContext, Scoreboard, ScoreboardMode

from bpuverify.ittage.model.semantic import Context, IttageReference


def prediction_values(prediction, actual, visible):
    expected = dict(valid=int(visible), hit=int(visible and prediction.provider is not None))
    observed = dict(valid=actual.meta['valid'], hit=actual.hit)
    if not visible:
        return expected, observed
    expected.update(provider_valid=int(prediction.provider is not None),
                    alternate_valid=int(prediction.alternate is not None),
                    allocate_valid=int(bool(prediction.candidates)),
                    differs=int(prediction.alternate is not None and prediction.provider_target != prediction.alternate_target))
    observed.update(provider_valid=actual.meta['provider']['valid'],
                    alternate_valid=actual.meta['altProvider']['valid'],
                    allocate_valid=actual.meta['allocate']['valid'], differs=actual.meta['altDiffers'])
    if prediction.provider is not None:
        expected.update(provider=prediction.provider, confidence=prediction.confidence,
                        useful=prediction.useful, provider_target=prediction.provider_target,
                        target=prediction.target)
        observed.update(provider=actual.meta['provider']['bits'], confidence=actual.meta['providerCnt_value'],
                        useful=actual.meta['providerUsefulCnt_value'], provider_target=actual.meta['providerTarget_addr'],
                        target=actual.target)
    if prediction.alternate is not None:
        expected.update(alternate=prediction.alternate, alternate_confidence=prediction.alternate_confidence,
                        alternate_target=prediction.alternate_target,
                        differs=int(prediction.provider_target != prediction.alternate_target))
        observed.update(alternate=actual.meta['altProvider']['bits'],
                        alternate_confidence=actual.meta['altProviderCnt_value'],
                        alternate_target=actual.meta['altProviderTarget_addr'], differs=actual.meta['altDiffers'])
    if prediction.candidates:
        expected['legal_allocation'] = True
        observed['legal_allocation'] = bool(actual.meta['allocate']['valid']
                                           and actual.meta['allocate']['bits'] in prediction.candidates)
    return expected, observed


class IttageSemanticChecker:
    def __init__(self, *, coverage=None):
        self.model = IttageReference()
        self.board = Scoreboard('ittage.semantic-reference')
        self.initialized = False
        self.events = None
        self.input_tick = None
        self.failure = None
        self.failure_observed = False
        self.expected = deque(maxlen=64)
        self.coverage = coverage

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
                if self.coverage is not None:
                    self.coverage.accept(events, self.model, event.tick)
            self.input_tick, self.events = event.tick, events
        except Exception as error:
            self.failure = error

    def _check(self, actual, prediction, visible, context):
        if prediction is None:
            if not visible:
                self.board.check(expected=dict(valid=0, hit=0),
                    actual=dict(valid=actual.meta['valid'], hit=actual.hit), context=context)
            return
        expected, observed = prediction_values(prediction, actual, visible)
        self.board.check(expected=expected, actual=observed, context=context)

    def capture_output(self, event, actual, *, visible):
        if self.failure is not None or not self.initialized:
            return
        try:
            if self.input_tick != event.tick - 1:
                raise AssertionError('ITTAGE reference requires one public input boundary per clock')
            self.expected.append((event.tick, self.model.prediction, visible))
            if not self.events.reset:
                self._check(actual, self.model.prediction, visible,
                    CheckContext(self.board.name, ScoreboardMode.DIRECT, sequence_id=event.tick,
                        request=dict(events=self.events, state=self.model.state()), observed_event=event))
                if visible and self.coverage is not None:
                    self.coverage.consume(self.model.prediction, event.tick)
        except Exception as error:
            self.failure = error

    def response_expected(self, request, context):
        tick = context.accepted_event.tick + 6

        def compare(actual):
            self.raise_failure()
            matches = [(prediction, visible) for at, prediction, visible in self.expected if at == tick]
            if len(matches) != 1:
                raise AssertionError(f'no independent ITTAGE response at {tick}')
            prediction, visible = matches[0]
            if visible:
                if prediction is None:
                    raise AssertionError('accepted ITTAGE request has no reference table snapshot')
                self.board.check(expected=(request.pc, Context.from_recent(request.folded_history)),
                                 actual=(prediction.pc, prediction.context), context=context)
            self._check(actual, prediction, visible, context)

        return compare
