"""Independent logical histories with distinct pending learning effects."""
from suites.frontend.bpu.bpu.model.tage.dual_migration import PC, PATHS, OUTCOMES, Step, provider

HISTORY_PATHS = dict(PATHS, neighbor=PC + 0x80)
OLD_SOURCE_COUNT = 2
INPUT_NAMES = ('neighbor', 'current', 'old-first', 'old-second')


def neighbor_preparation():
    """Normal side-history discovery while shared Main counters start at0/1."""
    yield Step('neighbor-base-negative', 'neighbor', ((0, False, False), (1, False, False)), ((0, 0), (None, None)), False)
    yield Step('neighbor-base-positive-first', 'neighbor', ((0, True, True),), ((1, 0), (None, None)), False)
    yield Step('neighbor-base-positive', 'neighbor', ((0, True, True),), ((2, 0), (None, None)), False)
    yield Step('neighbor-earlier-install', 'neighbor', ((0, False, True), (1, False, False)),
               ((1, 0), (provider(0, 3), None)), allocation=(7, 0))
    yield Step('neighbor-later-install', 'neighbor', ((0, False, False), (1, True, True)),
               ((0, 1), (provider(0, 2), provider(1, 4))), allocation=(7, 1))
    yield Step('neighbor-base-agrees-before-strengthening', 'neighbor', ((0, False, False), (1, True, True)),
               ((0, 2), (None, None)), False)
    yield Step('neighbor-later-strong-without-protection', 'neighbor', OUTCOMES, ((0, 3), (provider(0, 1), provider(1, 5))))
    yield Step('neighbor-earlier-distinct-old-state', 'neighbor', ((0, True, True),), ((1, 3), (provider(0, 2), provider(1, 5))))


def expected_profile(name, *, serviced):
    if name not in HISTORY_PATHS or type(serviced) is not bool:
        raise ValueError('consumer needs a declared logical history and visibility phase')
    if name == 'displaced':
        providers = (None, None)
    elif name == 'original':
        providers = (provider(1, 0 if serviced else 1), provider(0, 7 if serviced else 4))
    else:
        providers = (provider(0, 1 if serviced else 2), provider(1, 6 if serviced else 5))
    return (0, 3), providers
