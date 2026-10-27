"""Two logical branch learning timelines, independent of DUT state or ports."""
from dataclasses import dataclass
from bpuverify.bpu.model.tage.forwarding import PC, POSITIONS, TARGETS

PATHS = dict(original=PC ^ 0x648, displaced=PC ^ 0xad8)
TABLE, SOURCE_COUNT = 3, 3
OUTCOMES = ((0, False, False), (1, True, False))


def provider(way, counter):
    return TABLE, way, counter, 0


@dataclass(frozen=True, slots=True)
class Step:
    name: str
    context: str
    outcomes: tuple
    expected: tuple
    enabled: bool = True
    allocation: tuple | None = None
    save: bool = False


def preparation():
    """Normal allocations and outcomes, with hand-derived postconditions.

    B's agreeing base is prepared BEFORE strengthening its provider, avoiding
    a useful reward that would forbid the later declared replacement. A weak
    old B then makes the second displaced allocation choose the other owner.
    """
    o, c = 'original', 'displaced'
    tt, ff, ft = ((0, True, True),), ((0, False, False), (1, False, False)), OUTCOMES
    a_bad = ((0, False, True), (1, False, False))
    b_bad = ((0, False, False), (1, True, True))
    yield Step('learn-later', o, ((1, True, True),), ((None, 2), (None, None)))
    yield Step('learn-earlier', o, tt, ((2, 2), (None, None)))
    yield Step('base-both-negative-first', o, a_bad, ((1, 1), (None, None)), False)
    yield Step('base-both-negative', o, ff, ((0, 0), (None, None)), False)
    yield Step('base-earlier-positive-first', o, tt, ((1, 0), (None, None)), False)
    yield Step('base-earlier-positive', o, tt, ((2, 0), (None, None)), False)
    yield Step('original-a-install', o, a_bad, ((1, 0), (provider(0, 3), None)), allocation=(3, 0))
    yield Step('original-b-install', o, b_bad, ((0, 1), (provider(0, 2), provider(1, 4))), allocation=(3, 1))
    yield Step('base-agrees-before-strengthening', o, b_bad, ((0, 2), (None, None)), False)
    yield Step('original-b-strong-without-protection', o, ft, ((0, 3), (provider(0, 1), provider(1, 5))))
    yield Step('save-original-pair', o, tt, ((1, 3), (provider(0, 2), provider(1, 5))), save=True)
    yield Step('displaced-base-negative-first', c, ((0, False, False), (1, False, True)), ((0, 2), (None, None)), False)
    yield Step('displaced-base-negative', c, ((0, False, False), (1, False, True)), ((0, 1), (None, None)), False)
    yield Step('displaced-base-positive-first', c, tt, ((1, 1), (None, None)), False)
    yield Step('displaced-base-positive', c, tt, ((2, 1), (None, None)), False)
    yield Step('displaced-a-install', c, a_bad, ((1, 0), (provider(0, 3), None)), allocation=(3, 0))
    yield Step('displaced-a-leaves-weak', c, ((0, False, False),), ((0, 0), (provider(0, 2), None)))
    yield Step('old-b-becomes-weak', o, ((0, False, False), (1, False, True)), ((0, 0), (None, provider(1, 4))))
    yield Step('displaced-b-replaces-weak', c, b_bad, ((0, 1), (provider(0, 1), provider(1, 4))), allocation=(3, 1))
    yield Step('original-base-positive-first', o, tt, ((1, 1), (None, None)), False)
    yield Step('original-base-positive', o, tt, ((2, 1), (None, None)), False)
    yield Step('original-a-reinstalls-on-other-owner', o, a_bad, ((1, 0), (provider(1, 3), None)), allocation=(3, 1))
    yield Step('original-a-leaves-weak', o, ((0, False, False),), ((0, 0), (provider(1, 2), None)))
    yield Step('original-b-reinstalls-on-other-owner', o, b_bad, ((0, 1), (provider(1, 1), provider(0, 4))), allocation=(3, 0))


def counters_after(accepted):
    if type(accepted) is not int or not 0 <= accepted <= SOURCE_COUNT:
        raise ValueError('only three distinct declared old outcomes are available')
    return max(0, 1 - accepted), min(7, 4 + accepted)
