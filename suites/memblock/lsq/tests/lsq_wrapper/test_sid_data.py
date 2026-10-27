"""Mixed seeds expose s2 bytes even when both s1 error metadata are clean."""
import pytest
from dataclasses import replace

from .bus_owners import BusOwners


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("reuse", (False, True), ids=("different-sid-control", "response-freed-sid"))
async def test_clean_responses_keep_original_unconsumed_s2_bytes_after_legal_sid_reuse(lsq, lane, reuse):
    trace = BusOwners(lsq, lane=lane)
    # The legacy bus actor intentionally supplies distinct interface metadata.
    # This new normal-producer reproduction binds fullVA to the same Load VA.
    trace.loads = tuple(replace(load, fullva=load.execution.vaddr) for load in trace.loads)
    # Equal clean errors intentionally let the original s1 check finish.
    # Different original bytes remain mandatory at the real s2 consumption.
    for payload in trace.payload.values():
        payload.update(error=False, nderr=False)
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
