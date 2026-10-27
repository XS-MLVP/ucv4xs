"""Actual transfer ownership, admission and complete semantic consumers."""
from copy import deepcopy

from toffee import CheckContext, Scoreboard, ScoreboardMode, TransferState
from bpuverify.mbtb.model.full_capacity_learning import FullCapacityProgram, MODES, RULES
from bpuverify.mbtb.checker.replacement_overlap import HALF_TICKS_PER_CYCLE


def actual_profile(prediction):
    return tuple((slot, e.position, e.target, e.taken, e.branch_type, e.ras_action,
                  prediction.meta_entries[slot // 5][slot % 5]['counter_value'])
                 for slot, e in enumerate(prediction.entries) if e.valid)


class FullCapacityChecks:
    def __init__(self, mode, order, coverage, *, position_relation='same-position'):
        if mode not in MODES:
            raise ValueError('unknown communication mode')
        self.program = FullCapacityProgram(order, position_relation=position_relation)
        if (coverage.mode, coverage.order, coverage.position_relation) != (mode, order, position_relation):
            raise ValueError('coverage must describe the actual semantic program')
        self.mode, self.coverage = mode, coverage
        self.board = Scoreboard('mbtb.full-capacity-learning')
        self.completed, self.witnesses, self.originals = set(), {}, []
        self.accepted, self.consumers = (), {}

    def check(self, expected, actual, point):
        self.board.check(expected=expected, actual=actual, context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT, request=dict(point=point, mode=self.mode,
                program=self.program.state(), accepted=self.accepted)))

    def reach(self, rule, **witness):
        self.completed.add(rule)
        self.witnesses[rule] = witness
        self.coverage.record('reached', rule, **witness)

    def response(self, stage, owner, transfer, prediction, *, after=None):
        self.check(True, transfer.state is TransferState.COMPLETED, 'native prediction transfer completed')
        self.check(self.program.branches[owner].pc, transfer.request.pc, 'actual request has the declared owner')
        if after is not None:
            self.check(True, transfer.accepted_event.tick > after, 'consumer is newer than learning acceptance')
        self.check(self.program.profile(stage, owner), actual_profile(prediction),
                   'complete branch identity, target, attributes, direction and counter: ' + owner)
        self.check(self.program.raw_hits(stage,owner),
                   tuple(s['rawHit'] for row in prediction.meta_entries for s in row),
                   'complete raw-hit metadata includes a page-suppressed adjacent Main window')
        self.originals.append((prediction, deepcopy(prediction.meta_entries)))
        self.consumers[stage, owner] = dict(accepted_tick=transfer.accepted_event.tick,
            completed_tick=transfer.completed_event.tick, actual=actual_profile(prediction))

    def sources(self, transfers, predictions):
        self.check((2, 2), (len(transfers), len(predictions)), 'two distinct actual sources')
        for owner, transfer, prediction in zip(self.program.sequence, transfers, predictions, strict=True):
            self.response('prepared', owner, transfer, prediction)
        a, b = transfers
        self.check(True, a.accepted_event.tick < b.accepted_event.tick < a.completed_event.tick,
                   'independent original lookups actually overlap in the pipeline')
        self.reach('original-overlapping-cold-sources', sources=[dict(owner=owner,
            accepted_tick=t.accepted_event.tick, completed_tick=t.completed_event.tick)
            for owner, t in zip(self.program.sequence, transfers, strict=True)])

    def admissions(self, receipts, payloads):
        self.accepted = tuple(receipts)
        self.check(2, len(receipts), 'both original feedbacks accepted exactly once')
        self.check(tuple(payloads), tuple(p for _, p in receipts), 'actual feedback payload and order')
        delta = receipts[1][0] - receipts[0][0]
        self.check(True, delta == HALF_TICKS_PER_CYCLE if self.mode == 'adjacent'
                   else delta > HALF_TICKS_PER_CYCLE, 'actual communication cadence')
        self.reach('actual-feedback-cadence', accepted=self.accepted, delta_half_ticks=delta)

    def finish(self):
        self.check(tuple(meta for _, meta in self.originals),
                   tuple(p.meta_entries for p, _ in self.originals), 'original metadata remain immutable')
        required = {('prepared', owner) for owner in ('old-a', 'old-b', 'old-c', 'old-d', 'neighbor-a', 'neighbor-b', 'neighbor-c', 'neighbor-d', *self.program.sequence)}
        for stage, owners in (('pair', (*self.program.sequence, 'old-a', 'old-b', 'neighbor-a', 'neighbor-b')),
                ('neighbor-probe', (*self.program.sequence, 'neighbor-a', 'neighbor-b', 'neighbor-probe')),
                ('neighbor-touch', (*self.program.sequence, 'neighbor-a', 'neighbor-b', 'neighbor-probe')),
                ('target-probe', (*self.program.sequence, 'target-probe', 'neighbor-a', 'neighbor-b', 'neighbor-probe'))):
            required.update((stage, owner) for owner in owners)
        required.update((stage,owner) for stage in ('pair','neighbor-probe','neighbor-touch','target-probe')
                        for owner in ('old-c','old-d','neighbor-c','neighbor-d'))
        self.check(set(), required - self.consumers.keys(), 'no declared actual consumer can be skipped')
        self.reach('immutable-original-sources', snapshots=len(self.originals))
        self.check(set(RULES), self.completed, 'all declared obligations actually completed')
        for rule in RULES:
            self.coverage.record('checked', rule, **self.witnesses[rule])

    def consumer_witness(self, stage, owners):
        self.check(set(), {(stage, owner) for owner in owners} - self.consumers.keys(),
                   'all phase witnesses must be actual completed comparisons')
        return {owner: self.consumers[stage, owner] for owner in owners}
