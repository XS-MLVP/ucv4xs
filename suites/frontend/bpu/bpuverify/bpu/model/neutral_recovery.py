"""Declared semantic edges: protection is contribution, not direction learning."""
from dataclasses import dataclass
from bpuverify.bpu.model.early_protection import COMMON


@dataclass(frozen=True, slots=True)
class Step:
    name: str
    kind: str
    counter_before: int
    counter_after: int
    before: int
    after: int
    base: bool | None

    @property
    def signature(self): return self.kind, self.counter_before, self.counter_after, self.before, self.after
    @property
    def edge(self): return self.name, self.kind, self.before, self.after


STEPS = {
    'neutral-lower': (
        Step('T-error-to-zero', 'penalty', 4, 3, 1, 0, None),
        Step('neutral-at-zero', 'neutral', 3, 2, 0, 0, False),
        Step('first-NT-error', 'penalty', 2, 3, 0, 0, None),
        Step('NT-error-restores-T', 'penalty', 3, 4, 0, 0, None),
        Step('contribution-restores-protection', 'reward', 4, 5, 0, 1, False)),
    'neutral-upper': (
        Step('approach-upper', 'reward', 7, 7, 1, 2, False),
        Step('reach-upper', 'reward', 7, 7, 2, 3, False),
        Step('neutral-at-upper', 'neutral', 7, 7, 3, 3, True),
        Step('error-releases-upper', 'penalty', 7, 6, 3, 2, None)),
}
PROFILES = tuple(STEPS)
EDGES = {name:tuple(step.edge for step in steps) for name, steps in STEPS.items()}
EXTRA = ('confirmed-T-seed', 'short-not-long-provider', 'actual-acceptance-window',
    'longer-allocation-eligibility', 'explicit-neutral-source', 'neutral-does-not-lock-learning',
    'owned-edge-receipts', 'full-preservation-and-seed-immutable')


def rules(profile):
    if profile not in STEPS: raise ValueError('declared integrated neutral-boundary profile required')
    strength = 'weak-T-seed-preserved' if profile == 'neutral-lower' else 'neutral-direction-strength'
    return (*COMMON, *EXTRA, strength, *(step.name for step in STEPS[profile]))
