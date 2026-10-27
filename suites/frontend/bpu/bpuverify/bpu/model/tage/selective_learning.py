"""Learning eligibility and current saturation are independent per branch."""
from dataclasses import dataclass
from bpuverify.bpu.model.tage.service import FULL_RETAINED_RETOUCH

COMPANIONS = ('feedback-absent', 'already-saturated')
CAPACITIES = ('room-remains', 'retained-capacity-full')
BOUNDARIES = ('still-pending', 'already-serviced')
DIRECTIONS = ('earlier-negative', 'later-positive')


@dataclass(frozen=True, slots=True)
class Program:
    companion: str
    capacity: str
    boundary: str
    direction: str = DIRECTIONS[0]

    def __post_init__(self):
        if self.companion not in COMPANIONS or self.capacity not in CAPACITIES or self.boundary not in BOUNDARIES or self.direction not in DIRECTIONS:
            raise ValueError('declared companion, capacity and service boundary required')

    @property
    def name(self):
        label = '.'.join((self.companion, self.capacity, self.boundary))
        return label if self.direction == DIRECTIONS[0] else self.direction+'.'+label

    @property
    def active(self): return int(self.direction == DIRECTIONS[1])

    @property
    def initial(self): return (2, 7) if self.active == 0 else (0, 5)

    @property
    def original(self): return self.initial[self.active]

    @property
    def proposal(self): return 1 if self.active == 0 else 6

    @property
    def bound(self): return 0 if self.active == 0 else 7

    @property
    def reverse_outcome(self):
        return ((0, True, True),) if self.active == 0 else ((0, False, False), (1, False, True))

    @property
    def restore_outcome(self):
        return ((0, False, False),) if self.active == 0 else ((0, False, False), (1, True, False))

    @property
    def reversed_values(self): return ((1, 3), (1, 7)) if self.active == 0 else ((0, 2), (0, 6))

    @property
    def paths(self): return FULL_RETAINED_RETOUCH.paths[:2 if self.capacity == CAPACITIES[0] else 4]

    @property
    def target(self): return len(self.paths)-1

    @property
    def feedback_order(self): return (*range(len(self.paths)), self.target, self.target)

    @property
    def first_batch(self):
        return tuple(range(len(self.feedback_order) - int(self.boundary == BOUNDARIES[1])))

    @property
    def outcome(self):
        if self.active == 0:
            return ((0, False, False),) + (() if self.companion == COMPANIONS[0] else ((1, True, False),))
        return (() if self.companion == COMPANIONS[0] else ((0, False, False),)) + ((1, True, False),)

    def counters(self, history, accepted):
        if history not in range(len(self.paths)) or type(accepted) is not int or accepted < 0:
            raise ValueError('declared history and nonnegative accepted count required')
        return (max(0, 2-accepted), 7) if self.active == 0 else (0, min(7, 5+accepted))


PROGRAMS = tuple(Program(c, n, b) for c in COMPANIONS for n in CAPACITIES for b in BOUNDARIES)
LATER_PROGRAMS = tuple(Program(c, n, b, DIRECTIONS[1]) for c in COMPANIONS for n in CAPACITIES for b in BOUNDARIES)
ALL_PROGRAMS = PROGRAMS + LATER_PROGRAMS
RULES = ('real-unsaturated-originals', 'independent-learning-eligibility',
    'current-boundary-retains-obligation', 'old-consumers-before-service',
    'all-and-only-qualified-services', 'new-consumers-after-service',
    'reverse-learning-and-restoration', 'originals-and-other-histories-preserved')


def preparation(direction=DIRECTIONS[0]):
    """Normal feedback establishes TAGE 2/7 or 0/5 with Main 0/3.

    Apply after every history has its normal 2/5 providers. TAGE learning is
    temporarily disabled while preparing Main; no counter/metadata is seeded.
    """
    if direction not in DIRECTIONS: raise ValueError('declared original direction required')
    yield True, ((0, False, False), (1, True, False)), ((0, 3), (1, 6))
    yield True, ((0, False, False), (1, True, False)), ((0, 3), (0, 7))
    if direction == DIRECTIONS[0]:
        yield True, ((0, True, True),), ((1, 3), (1, 7))
        yield True, ((0, True, True),), ((2, 3), (2, 7))
        yield False, ((0, False, True),), ((1, 3), (None, None))
        yield False, ((0, False, False),), ((0, 3), (None, None))
    else:
        yield True, ((0, False, False), (1, False, True)), ((0, 2), (0, 6))
        yield True, ((0, False, False), (1, False, True)), ((0, 1), (0, 5))
        yield False, ((0, False, False), (1, True, True)), ((0, 2), (None, None))
        yield False, ((0, False, False), (1, True, False)), ((0, 3), (None, None))


def eligible_counter(original, current, taken):
    """Closed-form per-branch obligation; neither input comes from actual DUT."""
    if any(type(v) is not int or not 0 <= v <= 7 for v in (original, current)) or type(taken) is not bool:
        raise ValueError('three-bit original/current and semantic outcome required')
    delta = 1 if taken else -1
    proposal, effect = max(0, min(7, original+delta)), max(0, min(7, current+delta))
    return proposal != original or effect != current, proposal, effect
