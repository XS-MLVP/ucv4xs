"""Whole-source lifetime and observable boundary-neutrality comparisons."""
from hashlib import sha256
import json

from bpuverify.sc.checker.boundary import ScBoundaryChecks
from bpuverify.sc.model.boundary import observed_feedback
from bpuverify.sc.model.neutral_boundary import META_FIELDS, RULES


def expected_feedback(transaction, *, branch_count, fold_count):
    """Comparison adapter from semantic source slots, independent of codec."""
    by_slot = {b.prediction_slot: b for b in transaction.branches if b is not None}
    assert len(by_slot) == len(transaction.branches)
    history = transaction.history
    assert (history.path, history.global_history, history.backward, history.loop, history.common_valid) == (0, 0, 0, 0, True)
    entries = []
    for slot in range(4):
        b = by_slot.get(slot)
        entries.append(dict(rawHit=0 if b is None else b.mbtb_hit,
            position=0 if b is None else b.position,
            attribute=dict(branchType=0 if b is None else b.branch_type, rasAction=0), counter_value=0))
    branches = tuple(dict(valid=int(i < len(transaction.branches)),
        taken=transaction.branches[i].actual_taken if i < len(transaction.branches) else 0,
        position=transaction.branches[i].position if i < len(transaction.branches) else 0,
        branch_type=transaction.branches[i].branch_type if i < len(transaction.branches) else 0)
        for i in range(branch_count))
    return dict(valid=1, ready=1, pc=transaction.pc, history=(1, 0, 0, 0, (0,) * fold_count),
        meta={k: tuple(transaction.meta[k]) for k in META_FIELDS},
        mbtb_meta=(tuple(entries[:2]), tuple(entries[2:])), branches=branches)


class NeutralBoundaryChecks(ScBoundaryChecks):
    def __init__(self, program):
        super().__init__(program)
        self.completed = set()
        self.feedback_records = []
        self.reverse_witnesses = {}
        self.closed = False

    def mark(self, coverage, rule, **witness):
        self.check(True, rule in RULES, request='declared semantic obligation')
        self.completed.add(rule)
        coverage.record('reached', self.program.label, rule, **witness)

    def neutral_feedback(self, source):
        actual, expected = super().feedback(source)
        return self.program.neutral(actual.meta), self.program.neutral(expected.meta)

    def accepted_feedback(self, source, kind, intended, frames, *, branch_count, fold_count, last_cold_response):
        expected = expected_feedback(intended, branch_count=branch_count, fold_count=fold_count)
        actual = tuple(observed_feedback(frame.value) for frame in frames)
        self.check((expected,), actual, request=dict(source=source, phase=kind, complete_feedback=True))
        tick = frames[0].event.tick
        self.accepted(source, tick)
        self.check(True, tick > last_cold_response, request='all cold original responses precede learning')
        self.check(False, any(row['source'] == source or row['tick'] == tick for row in self.feedback_records),
                   request='one actual acceptance per designated original')
        self.feedback_records.append(dict(source=source, phase=kind, tick=tick,
            payload_sha256=sha256(json.dumps(actual[0], sort_keys=True, separators=(',', ':')).encode()).hexdigest()))

    def reverse_consumer(self, step, transfer, actual):
        if step in self.program.crossing_steps:
            self.reverse_witnesses[step] = dict(accepted=transfer.accepted_event.tick,
                completed=transfer.completed_event.tick, takens=actual.takens, useds=actual.useds,
                meta={k: tuple(actual.meta[k]) for k in ('scPred', 'useScPred', 'sumAboveThres')},
                families={k: tuple(actual.meta['debug'][k]) for k in self.program.expected(0, (1130,) * 4)['families']})

    def finish(self):
        self.check(set(RULES), self.completed, request='every semantic obligation reached before checked credit')
        self.check(self.program.cold_source_count + self.program.reverse_steps, len(self.feedback_records),
                   request='all designated feedbacks actually accepted')
        self.check(1, sum(row['phase'] == 'neutral' for row in self.feedback_records), request='one complete dual-vote event')
        self.check(self.program.reverse_steps, sum(row['phase'] == 'reverse' for row in self.feedback_records),
                   request='exact fresh single-vote recovery length')
        self.check(set(self.program.crossing_steps), set(self.reverse_witnesses), request='both last-before and first-after crossing consumers')
        super().finish()
        self.closed = True

    def summary(self):
        status = self.board.status
        return dict(program=self.program.state(), closed=self.closed, completed=sorted(self.completed),
            originals=len(self.sources), consumed=len(self.spent), actual_feedbacks=self.feedback_records,
            recovery_consumers=self.reverse_witnesses,
            comparisons=dict(checked=status.checked, passed=status.passed, failed=status.failed))
