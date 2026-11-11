"""Small semantic oracles, deliberately independent of the existing models."""

import pytest

from suites.memblock.lsq.testbenches.rar.transactions import Query
from suites.memblock.lsq.testbenches.rar.transactions import QueuePtr
from suites.memblock.lsq.testbenches.rar.transactions import Release
from suites.memblock.lsq.testbenches.rar.transactions import RobPtr


@pytest.mark.parametrize("review_dut", ["load_queue_rar"], indirect=True)
@pytest.mark.parametrize("distance", range(4))
@pytest.mark.parametrize("data_valid", (False, True))
async def test_RAR_release_association_has_the_declared_age_window(review_dut, distance, data_valid):
    e = review_dut
    e.metadata = dict(issue="RAR-REL-001", distance=distance, data_valid=data_valid,
        domain="RAR current/previous release association contract; expired extra replay alone is not an ISA-data-error proof")
    if distance:
        await e.step(release=Release(True, 0x18007))
        e.event("release", PA=0x18007)
        await e.idle(distance - 1)
    fields = dict(
        queries={0: Query(True, RobPtr(False, 2, True), QueuePtr(False, 2), 0x18000, data_valid)},
        release=Release(True, 0x1801F) if distance == 0 else Release())
    await e.step(**fields)
    e.check("young cached load query accepted", int(e.pre_response.ready[0]), 1)
    e.event("younger_load_allocation", uid=1, ROB=2, LQ=2, PA=0x18000, dataValid=data_valid,
        current_release=distance == 0, no_revoke=True, head_LQ=0)
    await e.step(queries={0: Query(True, RobPtr(False, 1, True), Query().lq, 0x18000)})
    e.check("older query accepted", int(e.pre_response.ready[0]), 1)
    e.check("defined older-query response", int(e.post_response.responses[0].valid), 1)
    actual = e.post_response.responses[0].nuke
    e.event("older_load_violation_response", ROB=1, PA=0x18000, valid=1, nuke=actual)
    e.check("release association contract", actual, int(data_valid and distance in (0, 1)), fatal=False)
    await e.step(head=QueuePtr.encode(3))
    await e.idle(4, head=QueuePtr.encode(3))
    e.finish()
