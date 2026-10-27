"""bpuverify.bpu.checker.sc.common_routes components."""
from collections import deque

from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode


class RouteChecker:
    def __init__(self, phr, *, record_limit=None):
        if record_limit is not None and (type(record_limit) is not int or record_limit < 2):
            raise ValueError('SC route record_limit must retain at least two frames')
        self.phr = phr
        self.records = [] if record_limit is None else deque(maxlen=record_limit)
        self.observed_cycles = 0
        self.failure = None
        self.scoreboard = Scoreboard('bpu.sc.common_history_prediction_routes')

    def raise_failure(self):
        self.phr.raise_failure()
        if self.failure is not None:
            raise self.failure

    def capture(self, observation):
        if self.failure is None:
            try:
                self.observe(observation)
            except Exception as error:
                self.failure = error

    def observe(self, observation):
        row = observation.value
        self.observed_cycles += 1
        self.records.append(dict(tick=observation.event.tick, **row))
        check = lambda expected, actual, field: self.scoreboard.check(expected=expected, actual=actual,
            context=CheckContext(scoreboard=self.scoreboard.name, mode=ScoreboardMode.DIRECT,
                request=dict(field=field), observed_event=observation.event))
        check(row['enable'] & row['stage_fire'], row['fire'], 'actual_SC_prediction_enable_gate')
        base, common = (row['pc'] >> 3) & 127, row['common']
        indices = dict(globalTable_0=base ^ (common['ghr'] & 127) ^ (common['ghr'] >> 7),
                       bwTable_0=base ^ common['bw'])
        for table, read in row['reads'].items():
            check(row['fire'] & common['valid'], read['valid'], table + '.actual_commonHR_read_gate')
            check(indices[table], read['set_index'], table + '.PC_history_index')
            check(1 << (row['pc'] & 1), read['bank_mask'], table + '.physical_bank_mask')
