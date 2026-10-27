import pytest

from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import Redirect, RobPtr


async def consume(env, start, end):
    for value in range(start, end, 2):
        await env.cycle(physical_deq=SqPtr.encode(min(value + 2, end)), consumed=True)
    await env.idle(2)


@pytest.mark.parametrize("physical_base", (0, 63, 127, 191, 255))
async def test_cross_ring_recovery_reuses_every_canceled_virtual_slot(vsq, physical_base):
    env = vsq
    rob, end = 1, 0
    while end < physical_base:
        flows = min(16, physical_base - end)
        await env.cycle(env.requests({7: (rob, flows)}))
        await env.drain(RobPtr.encode(rob + 1))
        await consume(env, end, end + flows)
        end += flows
        rob += 2
    # Advance only virtual uop positions while keeping the physical reservation
    # unchanged. This is not a memory-direct edit or a DUT pointer as oracle.
    while env.model.head < 124:
        count = min(8, 124 - env.model.head)
        await env.cycle(env.requests({lane: (rob + lane, 0) for lane in range(count)}))
        await env.drain(RobPtr.encode(rob + count))
        rob += count + 1
    change = await env.cycle(env.requests({lane: (rob + lane, (0, 1, 2, 0, 4, 1, 1, 0)[lane]) for lane in range(8)}))
    old = change["accepted"]
    assert [item["position"] % 128 for item in old] == [124, 125, 126, 127, 0, 1, 2, 3]
    await env.cycle(redirect=Redirect(True, RobPtr.encode(rob + 2), False))
    changes = await env.idle(7)
    actual_canceled = [item for change in changes for item in change["canceled"]]
    assert {item["uid"] for item in actual_canceled} == {item["uid"] for item in old[3:]}
    recoveries = [change["recovery"] for change in changes if change["recovery"]]
    assert len(recoveries) == 1 and recoveries[0]["end"] == physical_base + 3
    ptr = SqPtr.encode(physical_base + 3)
    prefix = "io_toPhysicalQueue_physicalQueueEnqPtr_"
    assert [env.observed[prefix + key] for key in ("first_flag", "second_flag", "value")] == [int(ptr.first), int(ptr.second), ptr.value]
    change = await env.cycle(env.requests({lane: (rob + 8 + lane, 1 + lane % 2) for lane in range(5)}))
    new = change["accepted"]
    assert [item["position"] for item in new] == [item["position"] for item in old[3:]]
    assert min(item["uid"] for item in new) > max(item["uid"] for item in old)
    env.arm(("VSQ-SNAPSHOT.flags", "VSQ-REUSE.cancel", "VSQ-REDIRECT.partial"), [item["uid"] for item in new])
    await env.drain(RobPtr.encode(rob + 14))
    assert {item["uid"] for item in new} <= env.coverage.completed
