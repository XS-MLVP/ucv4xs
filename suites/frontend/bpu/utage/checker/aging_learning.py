"""Observe genuine maintenance/learning overlap and complete protection state."""
from collections import deque
from copy import deepcopy
from hashlib import sha256

from toffee import CheckContext, Scoreboard, ScoreboardMode

from suites.frontend.bpu.utage.model.aging_learning import POSITION
from suites.frontend.bpu.utage.model.semantic import Context, training_folds
from suites.frontend.bpu.utage.transaction.types import UtageLookup, UtageTraining


def payload(transaction):
    return dict(start_pc=transaction.pc, meta=deepcopy(transaction.meta), branch=dict(
        taken=transaction.actual_taken, position=transaction.position,
        branch_type=transaction.branch_type))


def protection(values):
    # Exact all-cell comparison in sparse display: an unexpected nonzero cell
    # is an unexpected key, not an excluded zero or a changed denominator.
    return {(address // 512, address % 512): value for address, value in enumerate(values) if value}


class AgingLearningChecks:
    def __init__(self, program, coverage):
        self.program, self.coverage = program, coverage
        self.board = Scoreboard('utage.aging-learning')
        self.failure = None
        self.cycle = 0
        self.actual = [0] * 1024
        self.planned = deque()
        self.sources = {}
        self.spent = set()
        self.consumed = set()
        self.armed = False
        self.receipts = []
        self.overlap = None
        self.post_verified = False
        self.accepted_count = 0

    def check(self, expected, actual, detail):
        self.board.check(expected=expected, actual=actual,
            context=CheckContext(self.board.name, ScoreboardMode.DIRECT, sequence_id=self.cycle,
                request=dict(program=self.program.name, detail=detail, armed=self.armed,
                    final_admissions=tuple(self.receipts), overlap=self.overlap)))

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure

    def capture(self, observation):
        if self.failure is None:
            try:
                self.observe(observation)
            except Exception as error:
                self.failure = error

    def prediction(self, expected, actual):
        context, slot = expected.context, actual.meta['abtbResult'][0]
        hit = int(expected.provider is not None)
        wanted = dict(valids=(1, 0, 0, 0), indices=context.index,
            history=training_folds(Context.from_recent(context.history)),
            position=POSITION, base=expected.base, strong=0, hits=(hit, hit))
        observed = dict(valids=tuple(entry['valid'] for entry in actual.meta['abtbResult']),
            indices=tuple(actual.meta['readIndex']),
            history=training_folds(tuple(row['foldedHist'] for row in actual.meta['foldedPathHistForTrain_hist'])),
            position=slot['cfiPosition'], base=slot['baseTaken'], strong=slot.get('baseIsStrongBias', 0),
            hits=(actual.hit, slot['hit']))
        if hit:
            wanted.update(provider=expected.provider, counter=expected.counter,
                          taken=(expected.taken, expected.taken))
            observed.update(provider=slot['tableId'], counter=slot['takenCtr_value'],
                            taken=(actual.taken, slot['predTaken']))
        self.check(wanted, observed, dict(obligation='fresh logical consumer/source', expected=expected))

    def remember(self, transfer, prediction, expected):
        self.check(False, transfer.sequence_id in self.sources, 'distinct actual source lifetimes')
        self.check(UtageLookup(expected.context.pc, POSITION, expected.base,
                              folded_history=expected.context.history), transfer.request, 'source lookup identity')
        self.check(True, transfer.accepted_event is not None and transfer.completed_event is not None
            and transfer.accepted_event.tick < transfer.completed_event.tick, 'source must have a real response')
        self.prediction(expected, prediction)
        self.sources[transfer.sequence_id] = dict(read=expected, prediction=prediction,
            frozen=deepcopy(prediction.meta), completed=transfer.completed_event.tick)
        return transfer.sequence_id

    def transaction(self, source_id, learning):
        self.check(True, source_id in self.sources, 'feedback requires a published source')
        self.check(False, source_id in self.spent, 'one feedback per original source')
        source = self.sources[source_id]
        self.check(learning.source, source['read'], 'feedback belongs to its original logical branch')
        self.check(source['frozen'], source['prediction'].meta, 'original source remains immutable')
        self.spent.add(source_id)
        return UtageTraining(learning.source.context.pc, POSITION, learning.actual,
            deepcopy(source['frozen']), mispredict=int(learning.source.taken != learning.actual))

    def plan(self, transactions):
        entries = tuple((source, phase, payload(transaction)) for source, phase, transaction in transactions)
        self.planned.extend(entries)

    def _snapshot(self, row):
        if 'all_cells_sha256' not in row:
            return False
        changes = row['changes']
        self.check(len(changes), len({address for address, _, _ in changes}), 'one delta per observed cell')
        for address, old, new in changes:
            if type(address) is not int or not 0 <= address < 1024 or new not in range(4):
                raise ValueError('maintenance observation requires 1024 two-bit cells')
            self.check(self.actual[address], old, dict(obligation='actual delta continuity', address=address))
            self.actual[address] = new
        self.check(sha256(bytes(self.actual)).hexdigest(), row['all_cells_sha256'], 'complete actual cell snapshot')
        return True

    def arm(self):
        self.raise_failure()
        self.check(False, self.armed, 'one declared maintenance event')
        self.check(0, len(self.planned), 'all preparation feedback really accepted')
        self.check(True, self.cycle > 0, 'monitor active before preparation')
        self.check(protection(self.program.before), protection(self.actual), 'declared full pre-maintenance state')
        self.armed = True

    def _admissions(self):
        self.check(('threshold-failure', 'overlap-target'), tuple(row['phase'] for row in self.receipts),
                   'complete original final feedback pair')
        self.check(1, self.receipts[1]['cycle'] - self.receipts[0]['cycle'], 'adjacent accepted feedback, not two serial drains')

    def observe(self, observation):
        self.cycle += 1
        row, tick = observation.value, observation.event.tick
        self.check(dict(reset=0, enable=1), dict(reset=row['reset'], enable=row['enable']), 'normal enabled epoch')
        if row['public']['valid']:
            self.check(True, bool(self.planned), 'no unplanned feedback')
            source_id, phase, expected = self.planned.popleft()
            self.check(expected, row['public']['bits'], dict(obligation='complete actual public offer', source_id=source_id))
            self.check(True, self.sources[source_id]['completed'] < tick, 'feedback follows its original response')
            self.accepted_count += 1
            if self.armed:
                self.receipts.append(dict(phase=phase, cycle=self.cycle, tick=tick, source_id=source_id))
        sampled = self._snapshot(row)
        ages = tuple(table['age'] for table in row['tables'])
        if any(ages):
            self.check(True, self.armed, 'maintenance cannot occur during unqualified preparation')
            self.check(None, self.overlap, 'exactly one maintenance pulse')
            self._admissions()
            self.check((1, 1), ages, 'both tables share genuine global maintenance')
            self.check(True, sampled, 'actual pre-effect cells at maintenance')
            self.check(protection(self.program.before), protection(self.actual), 'common prestate before local/maintenance effects')
            for expected, actual in zip(self.program.controls, row['tables'], strict=True):
                self.check(expected, {key: actual[key] for key in expected}, 'same-boundary complete learning qualification')
            self.overlap = dict(cycle=self.cycle, tick=tick, controls=deepcopy(row['tables']))
            self.coverage.record('reached', self.program.name, actual_overlap=True,
                                 accepted_count=self.accepted_count)
        elif self.overlap is not None:
            if not self.post_verified:
                self.check(self.overlap['cycle'] + 1, self.cycle, 'effects visible at next actual observation')
                self.check(True, sampled, 'complete post-maintenance snapshot')
            self.check(protection(self.program.after), protection(self.actual), 'all protection cells age from the common old state')
            self.post_verified = True

    def consumer(self, expected, actual):
        self.prediction(expected, actual)
        self.check(True, expected in self.program.consumers, 'declared consumer identity')
        self.check(False, expected in self.consumed, 'each declared consumer checked once')
        self.consumed.add(expected)

    def finish(self):
        self.raise_failure()
        self.check(0, len(self.planned), 'no unaccepted expected feedback')
        self._admissions()
        self.check(True, self.overlap is not None and self.post_verified, 'actual overlap and full poststate required')
        self.check(set(self.program.consumers), self.consumed, 'all target, source and protected-neighbor consumers')
        self.check(set(self.sources), self.spent, 'each designated source consumed exactly once')
        for source in self.sources.values():
            self.check(source['frozen'], source['prediction'].meta, 'learning never rewrites an original source')
        self.coverage.record('checked', self.program.name, full_cells=1024, full_consumers=True,
                             original_sources_unchanged=True)
