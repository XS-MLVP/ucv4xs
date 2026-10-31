"""Logical results have independent owner service orders, not paired lane ages."""
from suites.frontend.bpu.bpu.model.tage.dual_migration import provider
from suites.frontend.bpu.bpu.model.tage.neighbor_migration import HISTORY_PATHS
from suites.frontend.bpu.bpu.model.tage.partial_residency import A_ONLY, PAIR

SOURCE_COUNT = 3
INPUT_NAMES = ('old-first', 'neighbor', 'fresh-target', 'old-second', 'old-third')
OUTCOMES = (A_ONLY, PAIR, PAIR, PAIR, PAIR)
SERVICE_IDENTITIES = (('neighbor-a', 'target-b'), ('target-a', 'neighbor-b'))
PROPOSALS = ((('target-a', 1), None),
             (('neighbor-a', 1), ('neighbor-b', 6)),
             (('target-b', 6), None),
             (('target-a', 1), ('target-b', 6)),
             (('target-a', 1), ('target-b', 6)))
PRELUDE_PLAN = ((('neighbor-a', 1), ('target-b', 6)),
                (('target-a', 0), ('neighbor-b', 6)))
FINAL_PLAN = ((('neighbor-a', 1), ('target-b', 7)),
              (('target-a', 0), ('neighbor-b', 6)))
PRE_DIRTY_COUNTS = ((0, 0), (0, 1), (1, 2), (2, 2), (2, 2))


def expected_profile(name, *, serviced):
    if name not in HISTORY_PATHS:
        raise ValueError('undeclared asymmetric-retirement history')
    if name == 'original':
        pair = provider(1, 0), provider(0, 7 if serviced else 5)
    elif name == 'neighbor':
        pair = ((provider(0, 1), provider(1, 6)) if serviced else
                (provider(0, 2), provider(1, 5)))
    else:
        pair = None, None
    return (0, 3), pair
