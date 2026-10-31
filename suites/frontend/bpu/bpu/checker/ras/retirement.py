"""suites.frontend.bpu.bpu.checker.ras.retirement components."""

from collections import deque
from copy import deepcopy
from dataclasses import asdict
from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from suites.frontend.bpu.ras.model.model import CommittedStack
from suites.frontend.bpu.ras.model.model import advance
from suites.frontend.bpu.bpu.case.ras.retirement import return_address


class CommitChecker:
    def __init__(self):
        self.scoreboard = Scoreboard('bpu.committed_stack')
        self.reference = CommittedStack()
        self.records, self.accepted, self.applied = [], [], []
        self.planned = deque()
        self.pending_expected = None
        self.initialized = False
        self.failure = None
        self.last_source_tick = -1
        self.last_tick = None
        self.checked_applied = 0

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure

    def check(self, expected, actual, *, tick=None, phase, request=None):
        self.raise_failure()
        self.scoreboard.check(expected=expected, actual=actual, context=CheckContext(
            scoreboard=self.scoreboard.name, mode=ScoreboardMode.DIRECT,
            request=dict(phase=phase, tick=tick, operation=request)))

    def capture(self, observation):
        if self.failure is None:
            try:
                self.observe(deepcopy(observation.value), observation.event.tick)
            except Exception as error:
                self.failure = error

    def observe(self, row, tick):
        self.records.append(dict(tick=tick, **row))
        if self.last_tick is not None:
            self.check(self.last_tick + 2, tick, tick=tick, phase='contiguous-cycle')
        self.last_tick = tick
        if not self.initialized:
            self.check(1, row['reset'], tick=tick, phase='reset-origin')
            self.initialized = True
            return
        self.check(self.reference.native(), dict(head=row['state']['head'],
            cells=list(row['state']['cells'])), tick=tick, phase='all-retained-committed-cells')
        self.checked_applied = len(self.applied)
        self.check(int(self.pending_expected is not None), row['pending']['valid'],
                   tick=tick, phase='registered-commit-valid')
        if self.pending_expected is not None:
            request = self.pending_expected
            self.check(dict(push=int(request['action'] == 2), pop=int(request['action'] == 1),
                ssp=request['meta']['ssp'], tosw=request['meta']['tosw']),
                {key: row['pending'][key] for key in ('push', 'pop', 'ssp', 'tosw')},
                tick=tick, phase='registered-commit-payload', request=request)
        if row['reset']:
            self.reference = CommittedStack()
            self.pending_expected = None
            return
        if self.pending_expected is not None:
            request = self.pending_expected
            # A genuine neutral instruction retires no stack operation. Its
            # speculative SSP need not equal the committed stack cursor after
            # omitted notifications. Lifetime/BOS effects belong to the
            # independent program reference, not this committed-data model.
            if request['action']:
                self.check(self.reference.head, request['meta']['ssp'], tick=tick,
                           phase='ordered-source-ssp', request=request)
                self.reference = advance(self.reference, request['action'],
                    address=request['return_address'] if request['action'] == 2 else None)
            self.applied.append(dict(tick=tick + 2, request=deepcopy(request),
                                     expected=self.reference.native()))
        self.pending_expected = None
        if row['commit']['valid']:
            self.check(True, bool(self.planned), tick=tick, phase='planned-public-commit')
            request = self.planned.popleft()
            self.check(dict(action=request['action'], branch_type=request['branch_type'],
                meta=request['meta']), row['commit']['bits'], tick=tick,
                phase='accepted-public-commit', request=request)
            self.check(1, row['spec']['enable'], tick=tick, phase='commit-enabled', request=request)
            self.accepted.append(dict(tick=tick, request=deepcopy(request)))
            self.pending_expected = request

    def request_for(self, transaction, action, phr):
        self.raise_failure()
        if type(action) is not int or action not in (0, 1, 2):
            raise ValueError('retirement needs a genuine neutral, return or call source')
        tick = transaction.meta_tick
        rows = [row for row in self.records if row['tick'] == tick]
        parents = [row for row in phr.records if row['tick'] == tick]
        self.check((1, 1), (len(rows), len(parents)), tick=tick, phase='unique-S3-source')
        row, parent = rows[0], parents[0]
        self.check(True, tick > self.last_source_tick, tick=tick, phase='ordered-nonduplicate-source')
        self.check(dict(valid=1, pc=transaction.meta.perf.start_pc),
            {key: row['public_meta'][key] for key in ('valid', 'pc')}, tick=tick, phase='public-commitMeta-source')
        self.check(transaction.meta.perf.start_pc, parent['public_meta']['bits']['perf']['start_pc'],
                   tick=tick, phase='coherent-associated-PC')
        self.check(transaction.meta.resolve, parent['public_meta']['bits']['resolve'],
                   tick=tick, phase='coherent-associated-resolve-meta')
        self.check(transaction.meta.redirect, parent['public_meta']['bits']['redirect'],
                   tick=tick, phase='coherent-associated-redirect-meta')
        self.check(dict(valid=1, enable=1, action=action, pc_bytes=transaction.meta.perf.start_pc * 2),
            {key: row['spec'][key] for key in ('valid', 'enable', 'action', 'pc_bytes')},
            tick=tick, phase='genuine-S3-speculation')
        self.last_source_tick = tick
        return dict(action=action, branch_type=3 if action == 1 else 2,
            meta=deepcopy(row['public_meta']['bits']), source_tick=tick,
            prediction_tick=transaction.prediction_tick, pc=transaction.meta.perf.start_pc,
            position=row['spec']['position'],
            return_address=return_address(transaction.meta.perf.start_pc, row['spec']['position']) if action == 2 else None)

    def summary(self):
        self.raise_failure()
        self.check(0, len(self.planned), phase='all-planned-accepted')
        self.check(None, self.pending_expected, phase='all-accepted-drained')
        self.check(len(self.accepted), len(self.applied), phase='one-update-per-commit')
        self.check(len(self.applied), self.checked_applied, phase='all-effects-compared')
        return dict(cycles=len(self.records), accepted=len(self.accepted), applied=len(self.applied),
                    final_native=self.reference.native(), checks=asdict(self.scoreboard.status))
