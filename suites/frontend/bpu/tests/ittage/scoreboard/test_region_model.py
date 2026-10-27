"""Reference policy is proved independently of DUT observations."""
import pytest

from bpuverify.ittage.model.region import IttageRegionModel
from bpuverify.ittage.model.region import RegionAllocation


def filled():
    model = IttageRegionModel()
    for pointer in range(16):
        assert model.allocate((0x410 + pointer) << 20) == RegionAllocation(pointer, False, None)
    return model


def test_empty_slots_fill_in_priority_order_and_keep_unique_regions():
    assert filled().regions == tuple(range(0x410, 0x420))


def test_full_plru_evictions_follow_bit_reversal_touch_order():
    model = filled()
    expected = (0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15)
    for new_region, victim in zip(range(0x430, 0x440), expected, strict=True):
        assert model.allocate(new_region << 20) == RegionAllocation(victim, False, 0x410 + victim)


@pytest.mark.parametrize('touch, victim', [(0, 8), (15, 0)])
def test_existing_region_write_touches_policy_without_evicting(touch, victim):
    model = filled()
    before = model.regions
    assert model.allocate(((0x410 + touch) << 20) | 0x240) == RegionAllocation(touch, True, None)
    assert model.regions == before
    assert model.allocate(0x43000360).pointer == victim


def test_replaced_pointer_redecodes_old_offset_without_touching_survivor():
    model = filled()
    before = model.decode(1, 0x120)
    assert model.allocate(0x43000360).pointer == 0
    assert model.decode(0, 0x120) == 0x43000120
    assert model.decode(0, 0x240) == 0x43000240
    assert model.decode(1, 0x120) == before


@pytest.mark.parametrize('target', [-2, 1])
def test_reference_rejects_bad_byte_addresses_before_mutating(target):
    model = filled()
    before = model.regions
    with pytest.raises(ValueError):
        model.allocate(target)
    assert model.regions == before


@pytest.mark.parametrize('pointer, offset', [(-1, 0), (16, 0), (0, -2), (0, 1), (0, 1 << 20)])
def test_reference_rejects_bad_pointer_or_offset(pointer, offset):
    with pytest.raises(ValueError):
        filled().decode(pointer, offset)


def test_reference_rejects_an_unallocated_pointer():
    with pytest.raises(ValueError, match='not been allocated'):
        IttageRegionModel().decode(0, 0)


@pytest.mark.parametrize('count, width', [(1, 20), (3, 20), (16, 0)])
def test_reference_rejects_unsupported_geometry(count, width):
    with pytest.raises(ValueError):
        IttageRegionModel(count, width)
