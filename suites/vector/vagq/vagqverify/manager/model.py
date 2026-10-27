"""Ring allocation over an owned set; no RTL/register reads or Boolean-network copy."""
from dataclasses import dataclass

from .types import Allocation, Beat, Offer


@dataclass(frozen=True, slots=True)
class State:
    occupied: frozenset[int] = frozenset()

    def __post_init__(self):
        if not self.occupied <= frozenset(range(8)):
            raise ValueError('occupied position outside the eight-entry ring')

    def decision(self, beat: Beat) -> Allocation:
        if not isinstance(beat.request, Offer) or not 1 <= beat.request.count <= 8:
            return Allocation()
        for start in range(8):
            window = {(start + offset) % 8 for offset in range(beat.request.count)}
            if not window & self.occupied:
                return Allocation(1, start, sum(1 << position for position in window))
        return Allocation()

    def following(self, beat: Beat, *, reset: bool = False) -> 'State':
        if reset:
            return State()
        if beat.recovery is not None:
            return State(beat.recovery)
        retained = self.occupied - beat.released
        inserted = beat.walked if beat.walked is not None else positions(self.decision(beat).mask)
        return State(frozenset(retained | inserted))


def positions(mask: int) -> frozenset[int]:
    return frozenset(position for position in range(8) if mask & (1 << position))
