"""Closed-form shared-parameter neutrality, not a cycle/signal-level oracle."""
from dataclasses import dataclass

from bpuverify.sc.transaction.types import ScBaseBranch, ScBatchTraining, ScBranchFeedback

WEIGHT_BITS = 6
INITIAL_THRESHOLD = 1130
FAMILY_FIELDS = ('scPathTakenVec', 'scGlobalTakenVec', 'scBWTakenVec',
                 'scImliTakenVec', 'scBiasTakenVec')
PROFILES = tuple((boundary, placement) for boundary in ('lower', 'upper')
                 for placement in ('original-slots', 'exchanged-slots'))
RULES = ('distinct-originals', 'shared-parameter-identity', 'executed-prefix', 'original-eligibility',
         'qualified-boundary-history', 'neutral-feedback-retained', 'slot-placement-independent',
         'fresh-reverse-learning', 'exact-recovery-consumers', 'unrelated-experience-retained')
META_FIELDS = ('scBiasLowerBits', 'scPred', 'useScPred', 'sumAboveThres',
               'tageCtr', 'tagePred', 'tagePredValid')


@dataclass(frozen=True, slots=True)
class NeutralBoundaryProgram:
    boundary: str
    placement: str
    pc: int = 0x40000040

    def __post_init__(self):
        if (self.boundary, self.placement) not in PROFILES:
            raise ValueError('shared-parameter boundary and original slot association required')

    @property
    def label(self):
        return self.boundary + '.' + self.placement

    @property
    def direction(self):
        return int(self.boundary == 'upper')

    @property
    def endpoint(self):
        return (1 << (WEIGHT_BITS - 1)) - 1 if self.direction else -(1 << (WEIGHT_BITS - 1))

    @property
    def seed_count(self):
        return abs(self.endpoint) + 2

    @property
    def cold_source_count(self):
        return self.seed_count + 1

    @property
    def reverse_steps(self):
        return 1 << (WEIGHT_BITS - 1)

    @property
    def crossing_steps(self):
        return self.reverse_steps - 1, self.reverse_steps

    @property
    def prefix_slots(self):
        return (0, 1) if self.placement == 'original-slots' else (1, 0)

    @property
    def layout(self):
        early, late = self.prefix_slots
        positions = [None, None, 8, 12]
        positions[early], positions[late] = 1, 4
        return tuple(ScBaseBranch(p, 4 if self.direction else 3) for p in positions)

    def weight(self, seeds, reverse=0):
        if (type(seeds) is not int or not 0 <= seeds <= self.seed_count
                or type(reverse) is not int or not 0 <= reverse <= self.reverse_steps
                or reverse and seeds != self.seed_count):
            raise ValueError('owned seed/hold history must precede reverse feedback')
        magnitude = min(seeds, abs(self.endpoint)) - reverse
        return magnitude if self.direction else -magnitude

    def thresholds(self, seeds, reverse=0):
        self.weight(seeds, reverse)
        target = INITIAL_THRESHOLD + (-seeds if self.direction else seeds) + reverse
        return INITIAL_THRESHOLD, target, INITIAL_THRESHOLD, INITIAL_THRESHOLD

    def scores(self, weight):
        return 5 * (2 * weight + 1), 5 * (2 * weight + 1), 5, 5

    def expected(self, weight, thresholds):
        signs = tuple(int(s >= 0) for s in self.scores(weight))
        # Positions 1/4 share the same parameter, whereas the unexecuted
        # suffix positions 8/12 own independent parameters.
        logical_parameters = (1, 1, 2, 3)
        used = tuple(int(abs(score) > thresholds[owner] // 64)
                     for score, owner in zip(self.scores(weight), logical_parameters, strict=True))
        return dict(takens=signs, useds=used,
            meta=dict(scBiasLowerBits=(3 if self.direction else 2,) * 4,
                scPred=signs, useScPred=used, sumAboveThres=used,
                tageCtr=(4 if self.direction else 3,) * 4,
                tagePred=(self.direction,) * 4, tagePredValid=(1,) * 4),
            families={name: signs for name in FAMILY_FIELDS})

    def seed(self, meta):
        return ScBatchTraining(self.pc, meta, (ScBranchFeedback(1, self.direction, self.prefix_slots[0]),))

    def neutral(self, meta):
        # Keep execution order NT then T, even when original prediction
        # metadata slots were exchanged. The unexecuted suffix gets no vote.
        return ScBatchTraining(self.pc, meta, (
            ScBranchFeedback(1, 0, self.prefix_slots[0]),
            ScBranchFeedback(4, 1, self.prefix_slots[1]),
        ))

    def reverse(self, meta):
        return ScBatchTraining(self.pc, meta, (ScBranchFeedback(1, 1 - self.direction, self.prefix_slots[0]),))

    def feedback(self, meta, *, reverse=False):
        """Reuse the existing real-source ledger for single-vote phases."""
        return self.reverse(meta) if reverse else self.seed(meta)

    def state(self):
        return dict(boundary=self.boundary, placement=self.placement, seed_feedbacks=self.seed_count,
            cold_sources=self.cold_source_count, prefix=((1, False), (4, True)),
            reverse_feedbacks=self.reverse_steps, physical_enumeration=False,
            full_FTQ_reachability_proved=False)
