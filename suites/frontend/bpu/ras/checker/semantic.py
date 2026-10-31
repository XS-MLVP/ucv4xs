"""Compare program meaning, not an implementation register mirror."""
from suites.frontend.bpu.models.configuration import *

from toffee import CheckContext, Scoreboard, ScoreboardMode

from suites.frontend.bpu.ras.model.semantic import RasReference


def projection(actual):
    metadata = actual['redirect_meta']
    return dict(top=actual['top'], group=metadata['ssp'], repeat=metadata['sctr'],
                calls=metadata['tosw']['flag'] * RAS_SPEC_ENTRIES + metadata['tosw']['value'])


def values(model, actual, retained=None):
    expected, observed = dict(model.projection), projection(actual)
    expected.update(commit_group=expected['group'], commit_calls=expected['calls'])
    commit = actual['commit_meta']
    observed.update(commit_group=commit['ssp'], commit_calls=commit['tosw']['flag'] * RAS_SPEC_ENTRIES + commit['tosw']['value'])
    if retained is not None:
        expected.update(retained_head=model.committed_head,
                        retained_groups=tuple((frame.address, frame.repeat) for frame in model.committed))
        observed.update(retained_head=retained['head'],
                        retained_groups=tuple((cell['address'] * 2, cell['counter']) for cell in retained['cells']))
    return expected, observed


class RasSemanticChecker:
    def __init__(self, *, coverage=None):
        self.model = RasReference()
        self.board = Scoreboard('ras.semantic-program')
        self.initialized = False
        self.failure = None
        self.failure_observed = False
        self.events = None
        self.input_tick = None
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
            self.events, self.input_tick = events, event.tick
        except Exception as error:
            self.failure = error

    def capture_output(self, event, actual, *, retained=None, reset=False):
        if self.failure is not None or not self.initialized:
            return
        try:
            if self.input_tick != event.tick - 1:
                raise AssertionError('RAS program reference requires one public input boundary per cycle')
            if reset:
                return
            expected, observed = values(self.model, actual, retained)
            self.board.check(expected=expected, actual=observed,
                context=CheckContext(self.board.name, ScoreboardMode.DIRECT, sequence_id=event.tick,
                    request=dict(events=self.events, state=self.model.state()), observed_event=event))
            if self.coverage is not None:
                self.coverage.consume(self.model, event.tick)
        except Exception as error:
            self.failure = error
