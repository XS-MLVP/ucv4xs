
import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import Redirect, RobPtr
from suites.memblock.lsq.vsq.types import Dispatch


async def test_empty_has_no_retire_or_recovery(vsq):
    env = vsq
    await env.idle(6)
    assert env.observed[P.p_empty] and not env.observed[P.p_toPhysicalQueue_redirectPtr_valid]
    env.coverage.sample(("VSQ-IDLE.quiet",), env.last_tick)
    env.coverage.sample(("VSQ-IDLE.quiet",), env.last_tick, checked=True)


@pytest.mark.parametrize("lane", range(8))
async def test_single_store_head_precommit_then_real_retirement(vsq, lane):
    env = vsq
    change = await env.cycle(env.requests({lane: (10, 1)}))
    env.arm(("VSQ-INTERVAL.one", "VSQ-PRECOMMIT.head", "VSQ-PRECOMMIT.payload", "VSQ-RETIRE.rob", "VSQ-RETIRE.latency"))
    await env.idle(4, rob_head=RobPtr.encode(10))
    assert env.observed[P.p_toPhysicalQueue_preCommitPtr_valid]
    assert env.observed[P.p_toPhysicalQueue_preCommitPtr_bits_value] == 1
    assert env.observed[P.p_toPhysicalQueue_retiredPtr_value] == 0 and not env.observed[P.p_empty]
    await env.drain(RobPtr.encode(11))
    env.arm("VSQ-RETIRE.no_duplicate", [change["accepted"][0]["uid"]])
    await env.idle(3)


async def test_sparse_lanes_nonstore_and_disabled_payload_do_not_allocate(vsq):
    env = vsq
    req = env.requests({0: (10, 2), 3: (11, 4), 7: (12, 0)})
    req[1] = Dispatch(True, False, RobPtr.encode(1), 16, SqPtr.encode(99))
    req[5] = Dispatch(False, True, RobPtr.encode(2), 16, SqPtr.encode(200))
    await env.cycle(req)
    env.arm(("VSQ-ADMIT.sparse", "VSQ-ADMIT.need_alloc", "VSQ-ADMIT.disabled", "VSQ-INTERVAL.zero", "VSQ-INTERVAL.multi", "VSQ-ORDER.short"))
    await env.drain(RobPtr.encode(13))


async def test_eight_uops_retire_physical_sum_not_virtual_count(vsq):
    env = vsq
    change = await env.cycle(env.requests({lane: (10 + lane, (1, 2, 3, 4, 0, 1, 2, 16)[lane]) for lane in range(8)}))
    env.arm(("VSQ-ADMIT.dense", "VSQ-ORDER.batch8", "VSQ-INTERVAL.maximum", "VSQ-INTERVAL.multi"))
    await env.idle(4)
    assert env.observed[P.p_toPhysicalQueue_retiredPtr_value] == 0
    env.arm("VSQ-ORDER.head_block", [item["uid"] for item in change["accepted"]])
    await env.drain(RobPtr.encode(18))


@pytest.mark.parametrize("flush_self", (False, True))
async def test_redirect_keeps_exclusive_end_then_new_uid_uses_canceled_interval(vsq, flush_self):
    env = vsq
    await env.cycle(env.requests({0: (10, 2), 1: (11, 4), 2: (12, 1)}))
    old = list(env.last_change["accepted"])
    await env.cycle(redirect=Redirect(True, RobPtr.encode(11), flush_self))
    await env.idle(6)
    assert not env.observed[P.p_sqRecoverStall]
    expected = 2 if flush_self else 6
    assert env.observed[P.p_toPhysicalQueue_physicalQueueEnqPtr_value] == expected
    await env.cycle(env.requests({7: (13, 1)}))
    new_uid = env.last_change["accepted"][0]["uid"]
    assert new_uid > old[-1]["uid"]
    env.arm(("VSQ-REDIRECT.flush_self" if flush_self else "VSQ-REDIRECT.flush_after", "VSQ-REDIRECT.partial",
             "VSQ-WALK.direct", "VSQ-RECOVER.stall", "VSQ-REUSE.cancel"), [new_uid])
    await env.drain(RobPtr.encode(14))
