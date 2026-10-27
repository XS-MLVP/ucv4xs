"""An owned branch may be serviced while its same-history peer remains pending."""
from dataclasses import dataclass

from bpuverify.bpu.model.tage.asymmetric_retirement import PRELUDE_PLAN, expected_profile as initial_profile
from bpuverify.bpu.model.tage.dual_migration import provider
from bpuverify.bpu.model.tage.neighbor_migration import HISTORY_PATHS
from bpuverify.bpu.model.tage.partial_residency import A_ONLY, PAIR

FIRST_SERVICE = tuple(owner[0] for owner in PRELUDE_PLAN)
PARTIAL_PLAN = tuple(owner[1:] for owner in PRELUDE_PLAN)
DESTINATIONS = {name: (owner, rank) for owner, plan in enumerate(PRELUDE_PLAN)
                for rank, (name, _) in enumerate(plan)}


@dataclass(frozen=True)
class MixedVisibilityProgram:
    name: str
    late_sources: tuple
    late_outcomes: tuple
    late_proposals: tuple
    pending_after: tuple
    target_counters: tuple
    neighbor_counters: tuple

    @property
    def final_plan(self):
        return self.pending_after[-1]

    def pending_before(self, index):
        if type(index) is not int or not 0 <= index < len(self.late_sources):
            raise ValueError('undeclared mixed-visibility feedback')
        return PARTIAL_PLAN if index == 0 else self.pending_after[index - 1]

    def profile(self, phase, name):
        if phase not in ('initial', 'mixed', 'blocked', 'serviced') or name not in HISTORY_PATHS:
            raise ValueError('undeclared mixed-visibility consumer')
        if phase == 'initial':
            return initial_profile(name, serviced=False)
        if name == 'displaced':
            pair = None, None
        elif name == 'original':
            a, b = self.target_counters if phase == 'serviced' else (0, 5)
            pair = provider(1, a), provider(0, b)
        else:
            a, b = self.neighbor_counters if phase == 'serviced' else (1, 5)
            pair = provider(0, a), provider(1, b)
        return (0, 3), pair


TARGET_REACTIVATED = ((('target-b', 7),), (('target-a', 0), ('neighbor-b', 6)))

PROGRAMS = (
    MixedVisibilityProgram('both-old-identities', ('old-target', 'old-neighbor'), (PAIR, PAIR),
        ((('target-a', 1), ('target-b', 6)), (('neighbor-a', 1), ('neighbor-b', 6))),
        (TARGET_REACTIVATED, ((('neighbor-a', 0), ('target-b', 7)), (('target-a', 0), ('neighbor-b', 7)))),
        (0, 7), (0, 7)),
    MixedVisibilityProgram('old-target-only', ('old-target',), (A_ONLY,),
        ((('target-a', 1), None),),
        (((('target-b', 6),), (('target-a', 0), ('neighbor-b', 6))),), (0, 6), (1, 6)),
    MixedVisibilityProgram('fresh-target-mixed', ('mixed-target',), (PAIR,),
        ((('target-b', 6), None),),
        (((('target-b', 7),), (('neighbor-b', 6),)),), (0, 7), (1, 6)),
    MixedVisibilityProgram('fresh-neighbor-mixed', ('mixed-neighbor',), (PAIR,),
        ((('neighbor-a', 0), ('neighbor-b', 6)),),
        (((('neighbor-a', 0), ('target-b', 6)), (('neighbor-b', 7),)),), (0, 6), (0, 7)),
)
