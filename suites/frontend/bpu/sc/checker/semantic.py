"""Default SC comparison with independently owned weights and snapshots."""
from collections import deque

from toffee import CheckContext, Scoreboard, ScoreboardMode

from suites.frontend.bpu.sc.model.semantic import Context, ScReference


def prediction_values(prediction, actual):
    expected = prediction.metadata()
    observed = {key: tuple(actual[key]) for key in expected}
    debug = actual['debug']
    for indices, name in zip(((0, 1), (2, 3), (4, 5), (6,), (7,)),
                             ('predPathIdx', 'predGlobalIdx', 'predBWIdx', 'predImliIdx', 'predBiasIdx'), strict=True):
        expected[name] = tuple(prediction.read.indices[table] for table in indices)
        value = debug[name]
        observed[name] = tuple(value) if isinstance(value, (tuple, list)) else (value,)
    for table, name in enumerate(('scPathTakenVec', 'scGlobalTakenVec', 'scBWTakenVec',
                                  'scImliTakenVec', 'scBiasTakenVec')):
        expected[name] = tuple(row[table] for row in prediction.components)
        observed[name] = tuple(debug[name])
    return expected, observed


class ScSemanticChecker:
    def __init__(self, *, coverage=None):
        self.model = ScReference()
        self.board = Scoreboard('sc.semantic-reference')
        self.initialized = False
        self.failure = None
        self.failure_observed = False
        self.events = None
        self.input_tick = None
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
                    self.coverage.accept(events, event.tick)
            self.events, self.input_tick = events, event.tick
        except Exception as error:
            self.failure = error

    def capture_output(self, event, actual):
        if self.failure is not None or not self.initialized:
            return
        try:
            if self.input_tick != event.tick - 1:
                raise AssertionError('SC reference requires one input boundary per cycle')
            self.expected.append((event.tick, self.model.prediction, self.events.enabled))
            if self.model.prediction is not None and not self.events.reset:
                expected, observed = prediction_values(self.model.prediction, actual)
                self.board.check(expected=expected, actual=observed,
                    context=CheckContext(self.board.name, ScoreboardMode.DIRECT, sequence_id=event.tick,
                        request=dict(events=self.events, state=self.model.state()), observed_event=event))
                if self.events.select and self.events.enabled and self.coverage is not None:
                    self.coverage.consume(self.model.prediction, event.tick)
        except Exception as error:
            self.failure = error

    def response_expected(self, request, context):
        tick = context.accepted_event.tick + 2

        def compare(actual):
            self.raise_failure()
            matches = [(prediction, enabled) for at, prediction, enabled in self.expected if at == tick]
            if len(matches) != 1:
                raise AssertionError(f'no independent SC response at tick {tick}')
            prediction, enabled = matches[0]
            if prediction is None:
                if enabled:
                    raise AssertionError('accepted SC lookup has no reference snapshot')
                self.board.check(expected=(0,) * len(actual.useds), actual=actual.useds, context=context)
                return
            if enabled:
                self.board.check(expected=(request.pc, Context.from_history(request.history)),
                                 actual=(prediction.read.pc, prediction.read.context), context=context)
                expected, observed = prediction_values(prediction, actual.meta)
                expected.update(takens=prediction.directions, useds=prediction.used)
                observed.update(takens=actual.takens, useds=actual.useds)
            else:
                expected, observed = dict(useds=(0,) * len(actual.useds)), dict(useds=actual.useds)
            self.board.check(expected=expected, actual=observed, context=context)

        return compare
