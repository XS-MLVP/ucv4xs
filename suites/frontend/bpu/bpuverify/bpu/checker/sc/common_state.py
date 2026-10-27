"""bpuverify.bpu.checker.sc.common_state components."""

from copy import deepcopy
from collections import deque
from dataclasses import asdict
from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from bpuverify.bpu.model.sc.common_state import dedup
from bpuverify.bpu.model.sc.common_state import recovery
from bpuverify.bpu.model.sc.common_state import update


class CommonStateChecker:
    def __init__(self, *, record_limit=None):
        if record_limit is not None and (type(record_limit) is not int or record_limit < 2):
            raise ValueError('CommonHR record_limit must retain at least two frames')
        self.scoreboard = Scoreboard('bpu.common_history_state')
        self.state = dict(valid=0, ghr=0, bw=0)
        self.candidates = dict(positions=[0] * 4, hits=[0] * 4)
        self.pending = None
        self.initialized, self.failure = False, None
        self.records = [] if record_limit is None else deque(maxlen=record_limit)
        self.outcomes = [] if record_limit is None else deque(maxlen=record_limit)
        self.observed_cycles = self.observed_outcomes = 0

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure

    def capture(self, observation):
        if self.failure is None:
            try:
                self.observe(observation)
            except Exception as error:
                self.failure = error

    def observe(self, observation):
        row, event = observation.value, observation.event
        self.observed_cycles += 1
        check = lambda expected, actual, field: self.scoreboard.check(expected=expected, actual=actual,
            context=CheckContext(scoreboard=self.scoreboard.name, mode=ScoreboardMode.DIRECT,
                request=dict(field=field), observed_event=event))
        if self.records:
            check(self.records[-1]['tick'] + 2, event.tick, 'continuous_reset_to_state_observation')
        self.records.append(dict(tick=event.tick, **deepcopy(row)))
        if not self.initialized:
            check(1, row['reset'], 'actual_reset_before_reference_initialization')
            self.initialized = True
        else:
            check(self.state, row['state'], 'independent_GHR_BW_and_valid_state')
        if row['reset']:
            self.state = dict(valid=0, ghr=0, bw=0)
            self.pending = None
            self.candidates = dict(positions=[0] * 4, hits=[0] * 4)
            return
        if self.pending is not None:
            self.state = recovery(self.pending)
        elif row['fire3']:
            prediction = row['s3']
            if prediction['taken']:
                check(1, sum(prediction['first']), 'exactly_one_actual_first_taken_owner')
                selected = prediction['first'].index(1)
                check(self.candidates['positions'][selected], prediction['position'], 'latched_S2_position_matches_final_S3_CFI')
            else:
                selected = 0
            before = deepcopy(self.state)
            self.state = update(self.state, self.candidates['positions'], self.candidates['hits'], prediction, selected)
            self.outcomes.append(dict(tick=event.tick, prediction=deepcopy(prediction),
                candidates=deepcopy(self.candidates), before=before, after=deepcopy(self.state)))
            self.observed_outcomes += 1
        self.pending = deepcopy(row['redirect']) if row['redirect']['valid'] else None
        if row['fire2']:
            self.candidates = dict(positions=list(row['s2']['positions']),
                hits=dedup(row['s2']['hits'], row['s2']['positions']))

    def summary(self):
        self.raise_failure()
        return dict(cycles=self.observed_cycles, outcomes=self.observed_outcomes,
            checks=asdict(self.scoreboard.status), initialized_from_actual_reset=True,
            observed_prestate_seeded_reference=False)
