"""Strict contract probes: known RTL mismatches remain ordinary failures."""
import pytest

from lsqverify.rar.types import Query, QueuePtr, Release, RobPtr


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("distance", range(4))
@pytest.mark.parametrize("data_valid", (True, False))
async def test_isolated_release_age_is_exactly_current_or_previous(rar, lane, distance, data_valid):
    address = 0x18000
    if distance:
        await rar.cycle(release=Release(True, address + 7))
        await rar.idle(distance - 1)
    await rar.cycle({lane: rar.request(2, address, nc=False, data=data_valid)},
                    release=Release(True, address + 31) if distance == 0 else Release())
    expected = data_valid and distance in (0, 1)
    await rar.probe((address,), rob=RobPtr.encode(1), expect=(expected,))
    if not expected:
        await rar.cycle(release=Release(True, address))
        await rar.probe((address,), rob=RobPtr.encode(1), expect=(False,))
        await rar.probe((address,), rob=RobPtr.encode(1), expect=(True,))
    await rar.idle(3)


async def test_existing_record_late_release_uses_hash_alias(rar):
    address = 0x18000
    alias = address ^ (1 << 17) ^ (1 << 28)
    await rar.cycle({2: rar.request(2, address, nc=False, data=False)})
    await rar.probe((address,), rob=RobPtr.encode(1), expect=(False,))
    await rar.cycle(release=Release(True, alias))
    await rar.probe((address,), rob=RobPtr.encode(1), expect=(False,))
    await rar.probe((address,), rob=RobPtr.encode(1), expect=(True,))


async def test_new_record_is_not_visible_to_same_edge_other_lane(rar):
    address = 0x18000
    old_query = Query(True, RobPtr.encode(1), QueuePtr(), address)
    await rar.cycle({0: rar.request(2, address, rob=RobPtr.encode(2)), 2: old_query})
    assert rar.observed.responses[2].valid and not rar.observed.responses[2].nuke
    await rar.probe((address,), rob=RobPtr.encode(1), expect=(True,))
