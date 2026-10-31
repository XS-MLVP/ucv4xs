
from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.vlq.types import RobPtr


async def test_eight_four_flow_uops_retire_as_public_physical_batch_of_32(vsq):
    env = vsq
    change = await env.cycle(env.requests({lane: (10 + lane, 4) for lane in range(8)}))
    uids = [item["uid"] for item in change["accepted"]]
    assert len(uids) == 8 and all(item["flows"] == 4 for item in change["accepted"])
    assert change["accepted"][-1]["end"] == 32
    env.arm("VSQ-RETIRE.batch_width", uids)
    await env.drain(RobPtr.encode(18))
    assert env.observed[P.p_toPhysicalQueue_retiredPtr_value] == 32
    assert set(uids) <= env.coverage.completed
    follow = await env.cycle(env.requests({7: (20, 1)}))
    follow_uid = [item["uid"] for item in follow["accepted"]]
    await env.drain(RobPtr.encode(21))
    assert env.observed[P.p_toPhysicalQueue_retiredPtr_value] == 33
    assert set(follow_uid) <= env.coverage.completed
