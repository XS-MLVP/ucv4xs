"""Reset-derived MicroRAS comparison; bounded state witnesses, no cycle export."""
from collections import Counter, deque
from copy import deepcopy
from dataclasses import asdict
from toffee import CheckContext, Scoreboard, ScoreboardMode
from bpuverify.uras.model.pipeline import advance, empty_state


class MicroRasChecker:
    def __init__(self, *, coverage=None):
        self.expected = empty_state()
        self.board = Scoreboard('bpu.micro_ras_pipeline')
        self.last_tick, self.failure = None, None
        self.initialized, self.frames = False, 0
        self.records = deque(maxlen=64)
        self.routes = Counter()
        self.coverage = coverage

    def check(self, expected, actual, point, **context):
        self.board.check(expected=expected, actual=actual, context=CheckContext(
            self.board.name, ScoreboardMode.DIRECT, sequence_id=self.last_tick,
            request=dict(point=point, **context)))

    def capture(self, observation):
        if self.failure is None:
            try:
                self.observe(observation.value, observation.event.tick)
            except Exception as error:
                self.failure = error

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure

    def observe(self, row, tick):
        try:
            self._observe(row,tick)
        except Exception as error:
            if self.coverage is not None:
                self.coverage.fail(error)
            raise

    def _observe(self, row, tick):
        if self.last_tick is not None:
            self.check(self.last_tick + 2, tick, 'lossless cycle observation')
        self.last_tick = tick
        if not self.initialized:
            self.check(1, row['reset'], 'genuine reset before observation')
            self.initialized = True
        else:
            self.check(self.expected, row['state'], 'all MicroRAS registers', inputs=row['inputs'])
            self.check({key: self.expected[key] for key in ('usable', 'address')}, row['output'],
                'complete module output', inputs=row['inputs'])
            if self.coverage is not None:
                self.coverage.confirm(tick,check=self.check)
        previous = deepcopy(self.expected)
        self.expected, route = advance(self.expected, row['inputs'], row['reset'])
        if self.coverage is not None:
            self.coverage.reach(previous,row['inputs'],tick=tick,reset=row['reset'])
        self.frames += 1
        self.routes[route] += 1
        self.records.append(dict(tick=tick, inputs=deepcopy(row['inputs']), expected_before=previous,
            expected_after=deepcopy(self.expected), route=route))

    def summary(self):
        self.raise_failure()
        self.check(True, self.initialized, 'genuine reset observed')
        result = dict(frames=self.frames, checks=asdict(self.board.status), routes=dict(self.routes),
            expected_state_seeded_from_DUT=False, main_speculative_RAS_reference_claimed=False)
        if self.coverage is not None:
            result['events']=self.coverage.summary()
        return result

    def finish(self):
        self.raise_failure()
        self.check((0, 0, 0, 0), tuple(self.expected[key] for key in
            ('s2_push', 's2_pop', 's3_push', 's3_pop')), 'all MicroRAS pending operations drained')
        if self.coverage is not None:
            self.check(None,self.coverage.pending,'all MicroRAS event effects checked')
        return self.summary()
