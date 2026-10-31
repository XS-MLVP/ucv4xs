"""Foreground-latched cycle Scoreboard with independent recovery association."""
from collections import deque
from copy import deepcopy
from dataclasses import asdict

from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from suites.frontend.bpu.bpu.model.phr.model import BpuPhrReference
from suites.frontend.bpu.bpu.checker.phr.association import BpuPhrAssociation


class BpuPhrChecker:
    def __init__(self, *, scope, record_limit=None):
        if record_limit is not None and (type(record_limit) is not int or record_limit < 2):
            raise ValueError('PHR record_limit must retain at least two frames')
        self.scope = scope
        self.reference = BpuPhrReference()
        self.scoreboard = Scoreboard('bpu.phr_state')
        self.planned = deque()
        self.records = [] if record_limit is None else deque(maxlen=record_limit)
        self.observed_cycles = 0
        self.initialized = False
        self.failure = None
        self.last_tick = None
        self.accepted = 0
        self.cells = 0
        self.folds = 0
        self.association = BpuPhrAssociation()

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure

    def plan(self, payload):
        self.raise_failure()
        self.planned.append(deepcopy(payload))

    def check(self, expected, actual, **request):
        self.raise_failure()
        self.scoreboard.check(expected=expected, actual=actual,
            context=CheckContext(scoreboard=self.scoreboard.name,
                mode=ScoreboardMode.DIRECT, request=request))

    def capture(self, observation):
        if self.failure is None:
            try:
                self.observe(observation)
            except Exception as error:
                self.failure = error

    def observe(self, observation):
        row, event = observation.value, observation.event
        self.observed_cycles += 1
        self.records.append(dict(tick=event.tick, **row))
        context = CheckContext(scoreboard=self.scoreboard.name, mode=ScoreboardMode.DIRECT,
            sequence_id=self.accepted, request=dict(scope=self.scope,
                pending_recovery=None if not self.planned else self.planned[0]), observed_event=event)
        check = lambda expected, actual: self.scoreboard.check(expected=expected, actual=actual, context=context)
        if self.last_tick is not None:
            check(self.last_tick + 2, event.tick)
        self.last_tick = event.tick
        if not self.initialized:
            check(1, row['reset'])
            self.reference.reset()
            self.initialized = True
            return
        self.association.observe(row, event.tick, check)
        check(self.reference.state, row['state'])
        self.cells += 52
        self.folds += 19 * 4
        logical = self.reference.logical()
        check(dict(pointer=self.reference.state['s1_pointer'], low=logical & 8191), row['phr_meta'])
        if row['public_meta']['valid']:
            meta = self.reference.meta3
            check(dict(phrPtr=meta['pointer'], phrLowBits=meta['low']), row['public_meta']['phr'])
        for stage in ('s1', 's2', 's3'):
            child, parent = row['boundary'][stage], row['parent']
            check(parent[stage + '_valid'], child['valid'])
            check(parent[stage + '_pc'] & ((1 << 49) - 1), child['start_pc'])
            check(parent[stage + '_taken'], child['prediction']['taken'])
            check(parent[stage + '_target'], child['prediction']['target'])
        for stage, meta in (('s2', self.reference.meta2), ('s3', self.reference.meta3)):
            if row['boundary'][stage]['valid']:
                check(meta, row['boundary'][stage]['meta'])
        if row['boundary']['s2']['valid'] or row['boundary']['s3']['valid']:
            selected = 's3' if row['boundary']['s3']['valid'] else 's2'
            prediction = row['boundary'][selected]['prediction']
            check(1, row['public_prediction']['valid'])
            check(dict(start_pc=row['parent'][selected + '_pc'],
                    target=prediction['target'], taken=prediction['taken'],
                    position=prediction['position'],
                    s2_override=row['boundary']['s2']['valid'],
                    s3_override=row['boundary']['s3']['valid']),
                row['public_prediction']['bits'])
        public = row['public_redirect']
        check(public['valid'], row['boundary']['redirect']['valid'])
        if public['valid']:
            check(True, bool(self.planned))
            check(self.planned.popleft(), public['bits'])
            meta = public['bits']['meta']['phr']
            check(dict(valid=1, taken=public['bits']['taken'], target=public['bits']['target'],
                cfi_pc=public['bits']['cfi_pc'], meta=dict(pointer=meta['phrPtr'], low=meta['phrLowBits'])),
                row['boundary']['redirect'])
            self.accepted += 1
        self.reference.advance(row['boundary'], row['reset'])

    def summary(self):
        self.raise_failure()
        if self.planned:
            raise AssertionError(f'unaccepted recoveries: {list(self.planned)!r}')
        return dict(cycles=self.observed_cycles, accepted=self.accepted, cells_compared=self.cells,
            fold_registers_compared=self.folds, associated=self.association.emitted,
            flushed=self.association.flushed, checks=asdict(self.scoreboard.status))
