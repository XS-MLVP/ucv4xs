"""Independent address-region/PLRU reference, not a copy of RTL state bits."""
from dataclasses import dataclass
from operator import index

from suites.frontend.bpu.models.address import encode_pruned_pc


@dataclass(frozen=True, slots=True)
class RegionAllocation:
    pointer: int
    reused: bool
    evicted_region: int | None


class IttageRegionModel:
    """Successful non-PC-region allocation writes, using byte addresses.

    Existing-region writes touch PLRU too; prediction reads do not. Entries
    retain a pointer and an offset when that pointer's region is replaced.
    Heap-order tree nodes deliberately differ from Rocket's packed state.
    This BPU-domain expected generator uses Scoreboard's callable comparison.
    """

    def __init__(self, count: int = 16, region_width: int = 20):
        count, region_width = index(count), index(region_width)
        if count < 2 or count & (count - 1):
            raise ValueError("region count must be a power of two, at least two")
        if region_width < 1:
            raise ValueError("byte-address region width must be positive")
        self.count = count
        self.region_width = region_width
        self._regions: list[int | None] = [None] * count
        self._older = [0] * (count - 1)

    @property
    def regions(self) -> tuple[int | None, ...]:
        return tuple(self._regions)

    def _victim(self) -> int:
        node = 0
        while node < self.count - 1:
            node = 2 * node + 1 + self._older[node]
        return node - self.count + 1

    def _touch(self, pointer: int) -> None:
        node = 0
        for bit in range(self.count.bit_length() - 2, -1, -1):
            direction = (pointer >> bit) & 1
            self._older[node] = 1 - direction
            node = 2 * node + 1 + direction

    def allocate(self, target: int) -> RegionAllocation:
        """Apply one qualifying region-table write, not arbitrary feedback."""
        target = index(target)
        encode_pruned_pc(target)
        region = target >> self.region_width
        reused = region in self._regions
        pointer = (self._regions.index(region) if reused else
                   self._regions.index(None) if None in self._regions else self._victim())
        evicted = None if reused else self._regions[pointer]
        self._regions[pointer] = region
        self._touch(pointer)
        return RegionAllocation(pointer, reused, evicted)

    def decode(self, pointer: int, offset: int) -> int:
        pointer, offset = index(pointer), index(offset)
        if not 0 <= pointer < self.count:
            raise ValueError("region pointer is out of range")
        if not 0 <= offset < (1 << self.region_width) or offset & 1:
            raise ValueError("target offset must be an aligned byte address within the region")
        region = self._regions[pointer]
        if region is None:
            raise ValueError("region pointer has not been allocated")
        return (region << self.region_width) | offset
