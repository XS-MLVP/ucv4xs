"""Compare public predictions against an independently owned semantic cache."""
from collections import deque
from dataclasses import asdict

from toffee import CheckContext, Scoreboard, ScoreboardMode

from suites.frontend.bpu.ubtb.model.semantic import UbtbReference


def prediction_value(prediction):
    # Invalid payload bits are not part of the prediction contract.
    return asdict(prediction) if prediction.valid else dict(valid=0)


class UbtbSemanticChecker:
    def __init__(self):
        self.model = UbtbReference()
        self.board = Scoreboard('ubtb.semantic-reference')
        self.initialized = False
        self.failure = None
        self.failure_observed = False
        self.input_tick = None
        self.events = None
        self.expected = deque(maxlen=64)
        self.cycles = 0

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
            self.input_tick, self.events = event.tick, events
        except Exception as error:
            self.failure = error

    def capture_output(self, event, actual, *, enabled, reset=False):
        if self.failure is not None or not self.initialized:
            return
        try:
            if self.input_tick != event.tick - 1:
                raise AssertionError('reference requires one public input boundary per clock')
            expected = self.model.prediction(enabled=enabled)
            pc = None if self.events.predict is None else self.events.predict.pc
            self.expected.append((event.tick, pc, expected))
            self.cycles += 1
            # Reset clears entries asynchronously while the generated
            # s1_hitOH register has no reset. Never compare a boundary whose
            # pins are being cleared, even before the delayed input launch
            # carries its reset event. The tick stays in the expected list so
            # downstream boundary bookkeeping remains one entry per clock.
            if reset:
                return
            # Reset cancels semantic requests. MicroBTB does not promise that
            # unreset lookup latches drive valid=0 while reset is asserted or
            # before the first new request. Those idle bits are not responses.
            # Never qualify them merely because the output valid pin is high.
            if self.events.reset or (enabled and self.model.lookup is None):
                return
            self.board.check(
                expected=prediction_value(expected), actual=prediction_value(actual),
                context=CheckContext(
                    self.board.name, ScoreboardMode.DIRECT, sequence_id=event.tick,
                    request=dict(events=self.events, state=self.model.state()),
                    observed_event=event))
        except Exception as error:
            self.failure = error

    def response_expected(self, request, context):
        """Scoreboard computes this on driver acceptance, checks on observation.

        Acceptance is a rise-write launch, not the hardware sampling boundary.
        The SDK's existing one-cycle association links the subsequent response.
        No prediction result is read to create the expectation.
        """
        tick = context.accepted_event.tick + 2

        def compare(actual):
            self.raise_failure()
            matches = [(pc, prediction) for at, pc, prediction in self.expected if at == tick]
            if len(matches) != 1:
                raise AssertionError(f'no independent prediction for accepted PC {request.pc:#x} at {tick}')
            pc, expected = matches[0]
            self.board.check(expected=request.pc, actual=pc, context=context)
            self.board.check(expected=prediction_value(expected), actual=prediction_value(actual),
                             context=context)

        return compare
