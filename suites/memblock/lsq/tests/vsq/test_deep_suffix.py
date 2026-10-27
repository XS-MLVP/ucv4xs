from lsqverify.vlq.types import Redirect, RobPtr


async def test_redirect_cancels_eight_real_younger_uids_and_reuses_exact_suffix(vsq):
    env = vsq
    change = await env.cycle(env.requests({lane: (10 + lane, 1) for lane in range(8)}))
    second = await env.cycle(env.requests({lane: (18 + lane, 1) for lane in range(2)}))
    old = [item["uid"] for item in change["accepted"] + second["accepted"]]
    assert len(old) == 10
    await env.cycle(redirect=Redirect(True, RobPtr.encode(11), False))
    changes = await env.idle(10)
    recoveries = [item["recovery"] for item in changes if item["recovery"]]
    assert len(recoveries) == 1
    assert recoveries[0]["end"] == 2 and recoveries[0]["canceled_uids"] == old[2:]
    assert set(old[2:]) <= env.coverage.canceled and not (set(old[2:]) & env.coverage.completed)
    change = await env.cycle(env.requests({7: (20, 3)}))
    new = [item["uid"] for item in change["accepted"]]
    assert new and min(new) > max(old)
    env.arm(("VSQ-REDIRECT.deep_suffix", "VSQ-REUSE.cancel"), new)
    await env.drain(RobPtr.encode(23))
    assert set(new) <= env.coverage.completed and not (set(old[2:]) & env.coverage.completed)
