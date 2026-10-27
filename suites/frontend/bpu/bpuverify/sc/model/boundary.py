"""Closed-form signed-weight boundary program, not an RTL state machine.

The pinned SC has five six-bit weight families. One representative branch
learns unit votes; three other branch ways retain zero. Original cold sources
remain eligible even after newer predictions become confident. Every source is
used once. These are standalone SC cut-point obligations, not FTQ generation.
"""
from dataclasses import dataclass

from bpuverify.sc.transaction.types import ScBaseBranch, ScBatchTraining, ScBranchFeedback


META_FIELDS = ('scBiasLowerBits', 'scPred', 'useScPred', 'sumAboveThres',
               'tageCtr', 'tagePred', 'tagePredValid')
FAMILY_FIELDS = ('scPathTakenVec', 'scGlobalTakenVec', 'scBWTakenVec',
                 'scImliTakenVec', 'scBiasTakenVec')
POSITIONS = (4, 5, 6, 7)
WEIGHT_BITS = 6


@dataclass(frozen=True)
class ScBoundaryProgram:
    direction: int
    pc: int = 0x40000040  # Existing SC halfword API; zero semantic histories.

    def __post_init__(self):
        if type(self.direction) is not int or self.direction not in (0, 1):
            raise ValueError('boundary direction must be an outcome bit')

    @property
    def endpoint(self):
        return (1 << (WEIGHT_BITS - 1)) - 1 if self.direction else -(1 << (WEIGHT_BITS - 1))

    @property
    def approach_steps(self):
        return abs(self.endpoint)

    @property
    def source_count(self):
        return self.approach_steps + 2  # Two genuinely eligible boundary holds.

    @property
    def reverse_steps(self):
        return 1 << (WEIGHT_BITS - 1)

    @property
    def layout(self):
        return tuple(ScBaseBranch(position, 4 if self.direction else 3) for position in POSITIONS)

    def weight(self, accepted, *, reverse=0):
        if (type(accepted) is not int or not 0 <= accepted <= self.source_count
                or type(reverse) is not int or not 0 <= reverse <= self.reverse_steps
                or reverse and accepted != self.source_count):
            raise ValueError('boundary progress must follow approach, holds, then reverse')
        magnitude = min(accepted, self.approach_steps) - reverse
        return magnitude if self.direction else -magnitude

    def expected(self, weight, thresholds):
        # All families have the same selected weight, but their public signs
        # are checked separately so one wrong family cannot hide in the sum.
        scores = (5 * (2 * weight + 1), 5, 5, 5)
        signs = tuple(int(score >= 0) for score in scores)
        ways = tuple((p % 4) ^ (p // 4) for p in POSITIONS)
        used = tuple(int(abs(score) > thresholds[way] // 64) for score, way in zip(scores, ways, strict=True))
        meta = dict(scBiasLowerBits=(3 if self.direction else 2,) * 4,
            scPred=signs, useScPred=used, sumAboveThres=used,
            tageCtr=(4 if self.direction else 3,) * 4,
            tagePred=(self.direction,) * 4, tagePredValid=(1,) * 4)
        return dict(takens=signs, useds=used, meta=meta,
                    families={name: signs for name in FAMILY_FIELDS})

    def feedback(self, meta, *, reverse=False):
        return ScBatchTraining(self.pc, meta, (ScBranchFeedback(
            POSITIONS[0], 1 - self.direction if reverse else self.direction, prediction_slot=0),))


def expected_feedback(transaction, *, branch_count, fold_count):
    """Complete defined offer, hand-shaped independently of the drive codec."""
    branch, = transaction.branches
    assert branch is not None and branch.prediction_slot == 0 and branch.mbtb_hit == 1
    empty = dict(rawHit=0, position=0, attribute=dict(branchType=0, rasAction=0), counter_value=0)
    hit = dict(rawHit=1, position=branch.position,
               attribute=dict(branchType=branch.branch_type, rasAction=0), counter_value=0)
    return dict(valid=1, ready=1, pc=transaction.pc,
        history=(1, 0, 0, 0, (0,) * fold_count),
        meta={key: tuple(transaction.meta[key]) for key in META_FIELDS},
        mbtb_meta=((hit, empty), (empty, empty)),
        branches=tuple(dict(valid=int(index == 0), taken=branch.actual_taken if index == 0 else 0,
            position=branch.position if index == 0 else 0,
            branch_type=branch.branch_type if index == 0 else 0) for index in range(branch_count)))


def observed_feedback(value):
    bits = value['bits']
    return dict(valid=value['valid'], ready=value['ready'], pc=bits['start_pc'],
        history=(bits['common_hr_valid'], bits['global_history'], bits['backward'], bits['loop'],
                 tuple(fold['foldedHist'] for fold in bits['path_history'])),
        meta={key: tuple(bits['sc_meta'][key]) for key in META_FIELDS},
        mbtb_meta=bits['mbtb_meta'], branches=bits['branches'])
