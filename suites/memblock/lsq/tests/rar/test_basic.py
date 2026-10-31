"""First pass for genuine request/response, event and free-pool timing."""
from suites.memblock.lsq.rar.types import RobPtr


async def test_empty_idle_and_event_outputs(rar):
    await rar.idle(5)
    assert rar.observed.ready == (True, True, True)
    assert not rar.observed.full
    assert rar.observed.perf_fire == rar.observed.perf_nuke == 0


async def test_nc_allocation_then_unique_old_load_query(rar):
    address = 0x10000
    change = await rar.cycle({0: rar.request(2, address, rob=RobPtr.encode(2))})
    assert len(change.allocated) == 1
    assert not rar.observed.responses[0].nuke
    await rar.probe((address,), rob=RobPtr.encode(1), expect=(True,))
    await rar.idle(3)


async def test_three_lane_records_then_head_removal(rar):
    addresses = (0x10000, 0x10100, 0x10200)
    change = await rar.cycle({i: rar.request(10 + i, address) for i, address in enumerate(addresses)})
    assert len(change.allocated) == 3
    await rar.probe(addresses, rob=RobPtr.encode(1), expect=(True, True, True))
    await rar.advance_head(12)
    await rar.probe(addresses, rob=RobPtr.encode(1), expect=(False, False, False))
    await rar.idle(4)
    assert len(rar.model.free.available) == 96
