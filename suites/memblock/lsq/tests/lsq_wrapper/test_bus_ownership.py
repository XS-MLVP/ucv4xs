"""Full legal three-owner overlap and response-freed SID reuse, strict oracles."""

import pytest

from .bus_owners import BusOwners

from suites.memblock.lsq.legacy_pins import P


@pytest.mark.parametrize("lane", (0, 2))
@pytest.mark.parametrize("delay", (1, 4))
@pytest.mark.parametrize("nc_store", (False, True), ids=("serial-io", "nc-control"))
async def test_old_nc_load_response_cannot_unlock_later_serial_store(lsq, lane, delay, nc_store):
    trace = BusOwners(lsq, nc_store=nc_store, lane=lane)
    await trace.allocate()
    await trace.execute(0)
    await trace.accept("load0")
    await trace.ack("load0", 1)
    # Global ROB still names old Store0; both younger NC Loads may execute
    # speculatively, without retiring either past the unfinished older Store.
    await trace.issue_store()
    await trace.wait("store")
    await trace.execute(1)
    for _ in range(10):
        await trace.step()
    await trace.accept("store")
    await trace.ack("store", 2)
    for _ in range(delay):
        await trace.step(trace.bus(ready=False))
        lsq.expect({P.p_uncache_req_valid: int(nc_store)}, "NC overlap or strict IO serial exclusion before unrelated response")
    lsq.reach("LSQ-BUS.serial", "LSQ-BUS.resp_route")
    await trace.respond("load0")
    # This is an ORIGINAL previously accepted NC Load's response, not the
    # currently serial Store's. The latter still owes its own response.
    lsq.expect({P.p_uncache_req_valid: int(nc_store)}, "unrelated old NC Load response must not clear later serial Store")
    if nc_store:
        await trace.accept("load1")
        await trace.ack("load1", 3)
    else:
        for _ in range(3):
            await trace.step(trace.bus(ready=True))
            lsq.expect({P.p_uncache_req_valid: 0}, "serial Store exclusion survives unrelated response", before=True)
    await trace.respond("store")
    if not nc_store:
        await trace.accept("load1")
        await trace.ack("load1", 3)
    await trace.respond("load1")
    for pos in range(2):
        await trace.consume(pos, lane)
    await trace.finish()
    lsq.prove("LSQ-BUS.resp_route", "LSQ-BUS.nc_outstanding" if nc_store else "LSQ-BUS.serial")


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("fault", (False, True))
@pytest.mark.parametrize("reuse", (False, True), ids=("different-sid-control", "returned-sid-reused"))
async def test_returned_sid_is_reusable_before_old_load_bypass_without_corrupting_it(lsq, lane, fault, reuse):
    trace = BusOwners(lsq, lane=lane, old_fault=fault)
    await trace.allocate()
    await trace.execute(0)
    await trace.accept("load0")
    await trace.ack("load0", 4)
    await trace.respond("load0")
    for _ in range(5):
        await trace.step()
    assert not trace.checked_data and not trace.feedback
    await trace.execute(1)
    await trace.accept("load1")
    await trace.ack("load1", 4 if reuse else 5)
    if reuse:
        lsq.reach("LSQ-BUS.sid_reuse")
    await trace.respond("load1")
    for _ in range(6):
        await trace.step()
    for pos in range(2):
        await trace.consume(pos, lane)
    await trace.finish()
    if reuse:
        lsq.prove("LSQ-BUS.sid_reuse")
