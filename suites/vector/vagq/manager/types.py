"""Domain requests, concurrent control beats and frozen observations."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Offer:
    count: int

    def __post_init__(self):
        if not isinstance(self.count, int) or not 0 <= self.count < 16:
            raise ValueError('offer count does not fit the four-bit input')


@dataclass(frozen=True, slots=True)
class Idle:
    # Nonzero unused payload is only needed by electrical boundary probes.
    count_encoding: int = 0

    def __post_init__(self):
        if not isinstance(self.count_encoding, int) or not 0 <= self.count_encoding < 16:
            raise ValueError('idle count encoding does not fit the four-bit input')


@dataclass(frozen=True, slots=True)
class Beat:
    request: Offer | Idle = Idle()
    released: frozenset[int] = frozenset()
    recovery: frozenset[int] | None = None
    walked: frozenset[int] | None = None

    def __post_init__(self):
        if not isinstance(self.request, (Offer, Idle)):
            raise TypeError('request must be Offer or Idle')
        for name in ('released', 'recovery', 'walked'):
            entries = getattr(self, name)
            if entries is not None and (
                not isinstance(entries, frozenset) or not entries <= frozenset(range(8))
            ):
                raise ValueError(f'{name} must be an immutable set of ring positions 0..7')


@dataclass(frozen=True, slots=True)
class Allocation:
    valid: int = 0
    start: int = 0
    mask: int = 0


@dataclass(frozen=True, slots=True)
class Boundary:
    reset: bool
    beat: Beat
    allocation: Allocation


@dataclass(frozen=True, slots=True)
class Cycle:
    index: int
    before: Boundary
    after: Boundary
