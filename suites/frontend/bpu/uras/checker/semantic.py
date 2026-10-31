"""Public response comparisons with independently reduced stack state."""
from toffee import CheckContext, Scoreboard, ScoreboardMode

from suites.frontend.bpu.uras.model.semantic import UrasReference
from suites.frontend.bpu.uras.coverage.semantic import obligations


def result_value(result):
    # Unknown target bits are not a usable return prediction.
    return dict(usable=1, target=result.target) if result.usable else dict(usable=0)


class UrasSemanticChecker:
    def __init__(self, *, coverage=None):
        self.model = UrasReference()
        self.board = Scoreboard('uras.semantic-reference')
        self.events = None
        self.input_tick = None
        self.initialized = False
        self.failure = None
        self.failure_observed = False
        self.cycles = 0
        self.coverage = coverage
        self.rules = ()

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
                before = self.model.state()
                self.model.advance(events)
                self.rules = obligations(events, before, self.model.result)
                if self.coverage is not None:
                    self.coverage.sample('reached', self.rules, tick=event.tick, output_tick=event.tick + 1)
            self.events, self.input_tick = events, event.tick
        except Exception as error:
            self.failure = error

    def capture_output(self, event, actual, *, reset=False):
        if self.failure is not None or not self.initialized:
            return
        try:
            if self.input_tick != event.tick - 1:
                raise AssertionError('MicroRAS reference requires one input boundary per clock')
            self.cycles += 1
            # Reset clears isCanUse asynchronously; the delayed input event
            # that resets the reference arrives one boundary later. A beat
            # with reset asserted carries no prediction obligation.
            if reset:
                return
            self.board.check(
                expected=result_value(self.model.result), actual=result_value(actual),
                context=CheckContext(
                    self.board.name, ScoreboardMode.DIRECT, sequence_id=event.tick,
                    request=dict(events=self.events, state=self.model.state()),
                    observed_event=event))
            if self.coverage is not None:
                self.coverage.sample('checked', self.rules, tick=self.input_tick, output_tick=event.tick)
        except Exception as error:
            self.failure = error


class HeldCallRepairChecks:
    """A full lifetime cannot earn checked credit from an immediate target."""
    def __init__(self, profile, steps, coverage):
        self.profile, self.steps, self.coverage = profile, tuple(steps), coverage
        phases = ('old-source', 'held-correction', 'withdrawn-hold')
        if profile.endswith('.resume-before'):
            phases += ('resume-before-consumer',)
        phases += ('fresh-consumer', 'return-once')
        if tuple(step[0] for step in self.steps) != phases or coverage.profile != profile:
            raise ValueError('complete declared held-call phases and matching profile required')
        self.board = Scoreboard('uras.held-call-repair')
        self.results = []
        self.closed = False

    def observe(self, phase, events, actual):
        if self.closed or len(self.results) >= len(self.steps):
            raise AssertionError('held-call lifetime is single-use')
        expected_phase, expected_events, expected = self.steps[len(self.results)]
        self.board.check(expected=(expected_phase, expected_events, result_value(expected)),
            actual=(phase, events, result_value(actual)), context=CheckContext(self.board.name,
                ScoreboardMode.DIRECT, sequence_id=len(self.results),
                request=dict(profile=self.profile, phase=phase, events=events, prior=self.results)))
        self.results.append(dict(phase=phase, usable=actual.usable,
                                 **(dict(target=actual.target) if actual.usable else {})))
        from suites.frontend.bpu.uras.coverage.semantic import HELD_RULES
        phase_rules = {'old-source': HELD_RULES[:1], 'held-correction': HELD_RULES[1:2],
            'withdrawn-hold': HELD_RULES[2:3], 'fresh-consumer': HELD_RULES[3:4],
            'return-once': HELD_RULES[4:]}
        self.coverage.sample('reached', phase_rules.get(phase, ()))

    def finish(self):
        if self.closed:
            raise AssertionError('held-call lifetime is single-use')
        if len(self.results) != len(self.steps) or self.board.status.failed:
            raise AssertionError('complete held correction, fresh consumption and one return required')
        from suites.frontend.bpu.uras.coverage.semantic import HELD_RULES
        self.coverage.sample('checked', HELD_RULES)
        self.closed = True
        return dict(profile=self.profile, status='PASS', observations=self.results,
                    actual_consumed_events_checked=True,
                    standalone_UT=True, BPU_parent_reachability_proved=False)
