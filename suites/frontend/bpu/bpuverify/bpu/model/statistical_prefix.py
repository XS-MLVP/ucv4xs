"""Instruction-level SC prefix requirements, not bank/way coverage variants."""
from dataclasses import dataclass

from bpuverify.bpu.model.pipeline import Outcome
from bpuverify.bpu.model.selection import Kind

PROFILES = tuple(entry + '.' + direction for entry in ('compressed-entry', 'conditional-entry')
    for direction in ('condition-taken', 'condition-not-taken'))
RULES = ('original-history-and-SC-read', 'unused-SC-control', 'distinct-real-teaching-originals',
    'SC-opposes-retained-TAGE-choice', 'executed-prefix-selects-complete-target',
    'actual-correct-prefix-feedback', 'fresh-consumer-after-learning', 'all-original-evidence-preserved')
CONTEXT_PROFILES = tuple(direction+'.'+agreement for direction in ('forward','backward')
    for agreement in ('agree','disagree'))
CONTEXT_RULES = ('real-executed-nonzero-history','owned-five-family-read','cold-unused-control',
    'distinct-teaching-originals','all-five-learning-effects','fresh-used-consumer',
    'correct-feedback-qualification','wrong-feedback-learning','fresh-after-both-feedbacks',
    'immutable-original-evidence','stale-global-experience-masked','stale-backward-experience-masked')
CONCURRENT_CONTEXT_PROFILES = tuple(profile+'.'+resource for profile in CONTEXT_PROFILES
    for resource in ('same-resource','independent-resource'))
CONCURRENT_CONTEXT_RULES = CONTEXT_RULES + ('old-context-survives-new-predictions',
    'qualification-controls-waiting','complete-feedback-accepted-once')


@dataclass(frozen=True, slots=True)
class Layout:
    profile: str
    a: int = 0x40000103

    def __post_init__(self):
        if self.profile not in PROFILES:
            raise ValueError('declared instruction-entry/direction program required')

    @property
    def b(self):
        return 0x40000001 if self.profile.startswith('compressed-entry.') else 0x40000002

    @property
    def x(self):
        # A 64K-halfword offset preserves all SC rows and both path folds.
        # The target hash uses bits 1..15; TAGE still receives a different tag.
        # It does not share the target's TAGE identity and never trains it.
        return self.b + 0x10000

    @property
    def d(self):
        return self.a + 0x100

    @property
    def positive(self):
        return self.profile.endswith('.condition-taken')

    @property
    def recovery_offset(self):
        return self.a // 16 * 16 + 4 - self.a


@dataclass(frozen=True, slots=True)
class ContextLayout(Layout):
    """One branch, a real conditional prefix and two agreement classes.

    The existing forward/backward recipe is retained. These coordinates form
    instruction flow; they are not bank/set/way coverage parameters.
    """
    def __post_init__(self):
        if self.profile not in CONTEXT_PROFILES:
            raise ValueError('declared nonzero-history SC behavior required')

    @property
    def b(self): return 0x40010000

    @property
    def prefix(self): return 0x40010600 if self.backward else 0x4000fe00

    @property
    def prefix_target(self): return 0x40010040

    @property
    def jump(self): return 0x40010400

    @property
    def position(self): return 4

    @property
    def d(self): return 0x40020080

    @property
    def backward(self): return self.profile.startswith('backward.')

    @property
    def agrees(self): return self.profile.endswith('.agree')

    @property
    def provider_counter(self): return 5 if self.agrees else 2

    def outcome(self,source,prediction,taken):
        if type(taken) is not bool:
            raise TypeError('instruction outcome must be a semantic bool')
        branch=prediction.branch
        wrong=(branch.position,branch.target,branch.kind,branch.taken)!=(
            self.position,self.d,Kind.CONDITIONAL,True) if taken else branch.taken
        return Outcome(self.position,self.d,Kind.CONDITIONAL,taken,mispredict=bool(wrong))


@dataclass(frozen=True, slots=True)
class ConcurrentContextLayout(ContextLayout):
    """An old executed prefix learns while an unrelated instruction stream runs.

    Only the resource relation changes. The target and its genuine prefix
    are exactly the existing context program; no physical coverage sweep.
    """
    a: int = 0x40000000

    def __post_init__(self):
        if self.profile not in CONCURRENT_CONTEXT_PROFILES:
            raise ValueError('declared concurrent nonzero-history SC behavior required')

    @property
    def agrees(self): return self.profile.split('.')[1]=='agree'

    @property
    def same_resource(self): return self.profile.endswith('.same-resource')

    @property
    def recovery_offset(self): return 0

    @property
    def loop(self):
        # Outside prefix_target -> jump: a self-loop inside that straight
        # instruction range would intercept the genuine return-to-context.
        return self.b+(0x2080 if self.same_resource else 0x2181)

    def blocks(self, needs_read):
        if type(needs_read) is not bool:
            raise TypeError('original feedback read qualification must be a bool')
        return self.same_resource and needs_read


def conditional_outcomes(source, prediction, layout, taken):
    """Truth is declared by the program; only misprediction comes from golden."""
    if type(taken) is not bool:
        raise TypeError('execution direction must be declared semantically')
    late = prediction.branch
    wrong = ((late.position, late.target, late.kind, late.taken) !=
        (2, layout.d, Kind.CONDITIONAL, True)) if taken else late.taken and late.position == 2
    branches = (Outcome(2, layout.d, Kind.CONDITIONAL, taken, mispredict=bool(wrong)),)
    if not taken:
        kind = Kind.INDIRECT if source.pc == layout.b else Kind.DIRECT
        tail_wrong = not wrong and (late.position, late.target, late.kind, late.taken) != (4, layout.a, kind, True)
        branches += (Outcome(4, layout.a, kind, True, mispredict=tail_wrong),)
    return branches
