"""Recovery classification is checked against the owned executed prefix."""
from copy import deepcopy

from bpuverify.bpu.checker.common_history import CommonHistoryChecks
from bpuverify.bpu.coverage.common_recovery import RULES
from bpuverify.bpu.model.common_recovery import POSITIONS, PROFILES


class CommonRecoveryChecks(CommonHistoryChecks):
    rules = RULES

    def __init__(self, pipeline, *, profile, observe_state=True, coverage=None):
        if profile not in PROFILES:
            raise ValueError('unknown semantic recovery profile')
        super().__init__(pipeline, observe_state=observe_state, coverage=coverage)
        self.profile = profile
        self.original_snapshot = None
        self.actual_recovery = None
        self.committed_sample = None

    def capture_state(self, event, row):
        super().capture_state(event, row)
        if self.failure is not None:
            return
        if row['reset']:
            self.original_snapshot = self.actual_recovery = self.committed_sample = None
            return
        if self.observe_state:
            # One bounded endpoint snapshot, never a per-cycle exported trace.
            self.committed_sample = dict(tick=event.tick, state=deepcopy(row['state']))
        if row['redirect']['valid'] and self.original is not None and self.last_recovery is not None\
                and self.last_recovery[1] is self.original[1]:
            self.actual_recovery = dict(tick=event.tick, bits=deepcopy(row['redirect']))

    def original_source(self, receipt):
        source = self.source(receipt)
        self.check(self.profile.original, source.value, 'normal loop independently certifies the original pattern')
        self.check(POSITIONS, source.block.conditionals, 'both original conditional identities are known')
        self.check(self.profile.restored, self.profile.recover(), 'closed expectation agrees with executed-prefix semantics')
        self.original = receipt, source
        self.original_snapshot = deepcopy(receipt)
        if self.coverage is not None:
            self.coverage.record('reached', self.rules[0], receipt.meta_tick, witness=dict(
                actual=receipt.meta.resolve['commonHR'], expected=source.value.mapping(),
                conditional_positions=source.block.conditionals))
            self.coverage.record('reached', self.rules[1], receipt.meta_tick, witness=dict(
                prediction_tick=receipt.prediction_tick, meta_tick=receipt.meta_tick,
                original_common_metadata=receipt.meta.redirect['commonHRMeta']))

    def recovered(self, tick):
        self.check(True, self.original is not None and self.last_recovery is not None,
                   'the original source and an actual accepted recovery are both required')
        self.check((tick, self.original[1], self.profile.correction, self.profile.restored),
                   self.last_recovery, 'complete recovery belongs to the declared original and actual CFI')
        self.check(True, self.last_tick > tick + 2 and self.model.pending is None,
                   'registered restoration is observed, not merely scheduled')
        self.check(self.profile.restored, self.model.value, 'only actual executed conditional results are replayed')
        self.check(True, self.actual_recovery is not None and self.actual_recovery['tick'] == tick,
                   'accepted recovery proof comes from compared monitor input, not the driver plan')
        if self.observe_state:
            self.check(True, self.committed_sample is not None and self.committed_sample['tick'] == self.last_tick,
                       'current actual committed sample is required')
            self.check(self.profile.restored.mapping(), self.committed_sample['state'],
                       'actual committed prefix snapshot matches the independent requirement')
        self.completed_recovery = tick
        if self.coverage is not None:
            self.coverage.record('reached', self.rules[3], self.last_tick, witness=dict(
                actual_accepted=self.actual_recovery, actual_committed=self.committed_sample,
                expected=self.profile.restored.mapping()))

    def consumed(self, receipt):
        self.check(True, self.completed_recovery is not None and receipt.prediction_tick > self.completed_recovery,
                   'public consumer is a fresh post-recovery lookup')
        self.check(self.profile.correction.target, receipt.prediction.start_pc,
                   'consumer belongs to the independent direct-only drain path')
        source = self.source(receipt)
        self.check((), source.block.conditionals, 'consumer path cannot add a hidden conditional outcome')
        self.check(self.profile.consumer, source.value, 'fresh valid public consumer retains the recovered history')
        self.consumer = receipt
        if self.coverage is not None:
            self.coverage.record('reached', self.rules[4], receipt.meta_tick, witness=dict(
                prediction_tick=receipt.prediction_tick, meta_tick=receipt.meta_tick,
                actual_pc=receipt.prediction.start_pc, actual=receipt.meta.resolve['commonHR'],
                expected=self.profile.consumer.mapping()))

    def finish(self):
        self.check(True, self.original is not None and self.original_snapshot is not None,
                   'a saved original snapshot in the current reset epoch is mandatory')
        self.check(self.original_snapshot, self.original[0], 'the entire original prediction and metadata are immutable')
        super().finish(public_only=True)
