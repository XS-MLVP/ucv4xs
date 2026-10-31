"""First complete lifecycles, independently parameterized over all 16 native IDs."""
from suites.memblock.lsq.uncache_entry.types import RobPtr


async def test_idle_has_no_request_wakeup_output_or_report(entry):
    await entry.idle(5)
    out = entry.observed
    assert not any((out.flush, out.mmio_select, out.slave_valid, out.bus.valid, out.nc_wakeup.valid,
                    out.mmio_wakeup.valid, out.nc.valid, out.mmio.valid, out.exception.valid))


async def test_nc_complete_without_waiting_for_rob_permission(entry):
    req = entry.request(nc=True)
    await entry.cycle(req, pending=RobPtr.encode(0))
    assert not entry.observed.bus.valid
    await entry.complete(sid=entry.spec["entry_id"])


async def test_mmio_complete_after_registered_rob_permission(entry):
    req = entry.request(nc=False)
    await entry.cycle(req, pending=req.rob)
    assert not entry.observed.bus.valid
    await entry.complete(sid=entry.spec["entry_id"])
