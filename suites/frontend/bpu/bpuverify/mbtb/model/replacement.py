"""DefaultConfig MainBTB replacement reference, independent of observed victims.

The two alignment banks each own 256 LRU cells indexed by halfword PC[12:5].
Entry SRAM uses PC[14:7] and bank PC[6:5], so sets separated by 64 share LRU.
This models normal allocations and single-hit feedback, not stale-key shadows.
"""
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import replace


@dataclass
class MbtbFourWayLru:
    """MRU-to-LRU order, updated only from the independently planned inputs."""

    order: tuple[int, ...] = (0, 1, 2, 3)

    def __post_init__(self):
        if type(self.order) is not tuple or len(self.order) != 4 or set(self.order) != set(range(4)):
            raise ValueError("MainBTB LRU requires a permutation of physical ways 0..3")
        for way in self.order:
            self._require_way(way)

    @staticmethod
    def _require_way(way):
        if type(way) is not int or way not in range(4):
            raise ValueError("MainBTB LRU requires physical way 0..3")

    @property
    def victim(self):
        return self.order[-1]

    def touch(self, way):
        self._require_way(way)
        self.order = (way, *(other for other in self.order if other != way))

    def allocate(self):
        selected = self.victim
        self.touch(selected)
        return selected


def require_alignment(align):
    if type(align) is not int or align not in (0, 1):
        raise ValueError("MainBTB alignment bank must be 0/1")


@dataclass(frozen=True)
class MbtbReplacementGeometry:
    align: int
    bank: int
    entry_set: int
    replacement_index: int


def mbtb_replacement_geometry(pc, position):
    if not isinstance(pc, int) or pc < 0 or pc & 31:
        raise ValueError("replacement reference requires a nonnegative aligned halfword PC")
    if not isinstance(position, int) or not 0 <= position < 32:
        raise ValueError("replacement reference requires a position in 0..31")
    return MbtbReplacementGeometry(position // 16, (pc >> 5) & 3,
                                   (pc >> 7) & 255, (pc >> 5) & 255)


class MbtbReplacementState:
    """Reset-initialized indexed LRU; feedback is supplied by the test intent."""

    def __init__(self):
        self._cells = {}

    def _cell(self, pc, position):
        geometry = mbtb_replacement_geometry(pc, position)
        key = (geometry.align, geometry.replacement_index)
        return self._cells.setdefault(key, MbtbFourWayLru())

    def victim(self, pc, position):
        return self._cell(pc, position).victim

    def allocate(self, pc, position):
        return self._cell(pc, position).allocate()

    def feedback(self, pc, position, way, *, taken):
        MbtbFourWayLru._require_way(way)
        if not isinstance(taken, int) or taken not in (0, 1):
            raise ValueError("replacement feedback outcome must be 0/1")
        cell = self._cell(pc, position)
        if taken:
            cell.touch(way)


def expected_mbtb_replacement_state(prepared, align, way, newcomer):
    """Replace a known conditional resident, preserve every other field.

    The selected victim gets the new target/position and a weak taken counter.
    The test supplies its way from independent LRU intent, never DUT output.
    """
    require_alignment(align)
    MbtbFourWayLru._require_way(way)
    if newcomer.branch_type != 1 or newcomer.position // 16 != align or newcomer.target < 0:
        raise ValueError("replacement readback requires a conditional branch in the selected alignment bank")
    active = align * 5 + way
    entry = prepared['entries'][active]
    meta = prepared['meta_entries'][align][way]
    if not entry.valid or entry.branch_type != 1 or not meta['rawHit'] or meta['counter_value'] not in range(4):
        raise ValueError("replacement readback requires a genuine conditional resident")
    expected = deepcopy(prepared)
    expected['entries'] = tuple(replace(value, target=newcomer.target, position=newcomer.position, taken=1)
                                if index == active else value
                                for index, value in enumerate(expected['entries']))
    expected['meta_entries'][align][way]['position'] = newcomer.position
    expected['meta_entries'][align][way]['counter_value'] = 2
    # A miss snapshots the evicted branch into VictimBTB. Its initial direction
    # is weak taken; a previously visible earlier victim still has priority.
    victim_slot = align * 5 + 4
    previous = expected['entries'][victim_slot]
    if not previous.valid or entry.position < previous.position:
        values = list(expected['entries'])
        values[victim_slot] = replace(entry, taken=1)
        expected['entries'] = tuple(values)
        expected['meta_entries'][align][4].update(rawHit=1, position=entry.position,
            counter_value=2, attribute=dict(branchType=entry.branch_type, rasAction=entry.ras_action))
    return expected


def expected_mbtb_replacement_feedback(prepared, align, way, *, taken):
    """Single conditional feedback changes only its weak counter/direction."""
    require_alignment(align)
    MbtbFourWayLru._require_way(way)
    if not isinstance(taken, int) or taken not in (0, 1):
        raise ValueError("replacement feedback outcome must be 0/1")
    active = align * 5 + way
    entry = prepared['entries'][active]
    meta = prepared['meta_entries'][align][way]
    if not entry.valid or entry.branch_type != 1 or not meta['rawHit'] or meta['counter_value'] != 2:
        raise ValueError("replacement qualification requires a genuine counter-2 conditional hit")
    expected = deepcopy(prepared)
    expected['entries'] = tuple(replace(value, taken=taken) if index == active else value
                                for index, value in enumerate(expected['entries']))
    expected['meta_entries'][align][way]['counter_value'] = 3 if taken else 1
    return expected
