"""Old/new semantic instructions and accepted feedback sources, in byte units."""
from dataclasses import asdict, dataclass, replace
from suites.frontend.bpu.ubtb.transaction.types import BranchTraining, UbtbBatchTraining, UbtbBranchFeedback

PROFILES = ('committed', 'fast-learning', 'resolve-learning', 'competing-learning')
RULES = ('distinct-old-residents', 'old-learning-stage-proved', 'post-reset-cold',
         'no-delayed-old-replay', 'fresh-reliability-lifetime', 'immutable-old-sources')


@dataclass(frozen=True)
class Program:
    profile: str

    def __post_init__(self):
        if self.profile not in PROFILES:
            raise ValueError('unknown MicroBTB reset lifetime profile')

    @property
    def old(self):
        return (BranchTraining(0x40001000, 0x40002000, 1, 3, 1),
                BranchTraining(0x40001080, 0x40003000, 1, 5, 3, 2),
                BranchTraining(0x40001100, 0x40004000, 1, 9, 2))

    @property
    def fast(self):
        return BranchTraining(0x40001200, 0x40005000, 1, 7, 2)

    @property
    def resolved(self):
        return BranchTraining(0x40001300, 0x40006000, 1, 11, 3)

    @property
    def resolve(self):
        source = self.resolved
        return UbtbBatchTraining(source.pc, (None, UbtbBranchFeedback(
            source.target, source.taken, source.position, source.branch_type,
            source.ras_action, source.mispredict)))

    @property
    def selected(self):
        return None if self.profile == 'committed' else self.fast if self.profile == 'fast-learning' else self.resolved

    @property
    def new(self):
        return (replace(self.old[0], target=0x40007000),
                replace(self.old[1], target=0x40008000, branch_type=2, position=9, ras_action=0))

    @property
    def old_pcs(self):
        return tuple(branch.pc for branch in (*self.old, self.fast, self.resolved))

    def state(self):
        return dict(profile=self.profile, old=[asdict(b) for b in self.old],
            pending_fast=asdict(self.fast), pending_resolve=asdict(self.resolve),
            selected=None if self.selected is None else asdict(self.selected), new=[asdict(b) for b in self.new])
