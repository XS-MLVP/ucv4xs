"""MiniConfig MainBTB replacement reference, independent of observed victims.

The two alignment banks each own 64 LRU cells indexed by halfword PC[9:4].
Entry SRAM uses PC[10:5] and bank PC[4], so sets separated by 32 share LRU.
This models normal allocations and single-hit feedback, not stale-key shadows.
"""
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import replace


@dataclass
class MbtbTwoWayLru:
    """Two-way replacement policy; no observed DUT state updates this model."""

    victim: int = 1

    def __post_init__(self):
        self._require_way(self.victim)

    @staticmethod
    def _require_way(way):
        if not isinstance(way, int) or way not in (0, 1):
            raise ValueError("MainBTB two-way LRU requires physical way 0/1")

    def touch(self, way):
        self._require_way(way)
        self.victim = 1 - way

    def allocate(self):
        selected = self.victim
        self.touch(selected)
        return selected


@dataclass(frozen=True)
class MbtbReplacementGeometry:
    align: int
    bank: int
    entry_set: int
    replacement_index: int


def mbtb_replacement_geometry(pc, position):
    if not isinstance(pc, int) or pc < 0 or pc & 15:
        raise ValueError("replacement reference requires a nonnegative aligned halfword PC")
    if not isinstance(position, int) or not 0 <= position < 16:
        raise ValueError("replacement reference requires a position in 0..15")
    return MbtbReplacementGeometry(position // 8, (pc >> 4) & 1,
                                   (pc >> 5) & 63, (pc >> 4) & 63)


class MbtbReplacementState:
    """Reset-initialized indexed LRU; feedback is supplied by the test intent."""

    def __init__(self):
        self._cells = {}

    def _cell(self, pc, position):
        geometry = mbtb_replacement_geometry(pc, position)
        key = (geometry.align, geometry.replacement_index)
        return self._cells.setdefault(key, MbtbTwoWayLru())

    def victim(self, pc, position):
        return self._cell(pc, position).victim

    def allocate(self, pc, position):
        return self._cell(pc, position).allocate()

    def feedback(self, pc, position, way, *, taken):
        MbtbTwoWayLru._require_way(way)
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
    MbtbTwoWayLru._require_way(align)
    MbtbTwoWayLru._require_way(way)
    if newcomer.branch_type != 1 or newcomer.position // 8 != align or newcomer.target < 0:
        raise ValueError("replacement readback requires a conditional branch in the selected alignment bank")
    active = align * 2 + way
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
    return expected


def expected_mbtb_replacement_feedback(prepared, align, way, *, taken):
    """Single conditional feedback changes only its weak counter/direction."""
    MbtbTwoWayLru._require_way(align)
    MbtbTwoWayLru._require_way(way)
    if not isinstance(taken, int) or taken not in (0, 1):
        raise ValueError("replacement feedback outcome must be 0/1")
    active = align * 2 + way
    entry = prepared['entries'][active]
    meta = prepared['meta_entries'][align][way]
    if not entry.valid or entry.branch_type != 1 or not meta['rawHit'] or meta['counter_value'] != 2:
        raise ValueError("replacement qualification requires a genuine counter-2 conditional hit")
    expected = deepcopy(prepared)
    expected['entries'] = tuple(replace(value, taken=taken) if index == active else value
                                for index, value in enumerate(expected['entries']))
    expected['meta_entries'][align][way]['counter_value'] = 3 if taken else 1
    return expected
