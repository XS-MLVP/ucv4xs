"""First complete lifecycles, independently parameterized over all 16 native IDs."""
from suites.memblock.lsq.testbenches.uncache_entry_12.transactions import RobPtr


async def test_idle_has_no_request_wakeup_output_or_report(uncache_entry_12):
    await uncache_entry_12.idle(5)
    out = uncache_entry_12.observed
    assert not any((out.flush, out.mmio_select, out.slave_valid, out.bus.valid, out.nc_wakeup.valid,
                    out.mmio_wakeup.valid, out.nc.valid, out.mmio.valid, out.exception.valid))


async def test_nc_complete_without_waiting_for_rob_permission(uncache_entry_12):
    req = uncache_entry_12.request(nc=True)
    await uncache_entry_12.cycle(req, pending=RobPtr.encode(0))
    assert not uncache_entry_12.observed.bus.valid
    await uncache_entry_12.complete(sid=uncache_entry_12.spec["entry_id"])


async def test_mmio_complete_after_registered_rob_permission(uncache_entry_12):
    req = uncache_entry_12.request(nc=False)
    await uncache_entry_12.cycle(req, pending=req.rob)
    assert not uncache_entry_12.observed.bus.valid
    await uncache_entry_12.complete(sid=uncache_entry_12.spec["entry_id"])
