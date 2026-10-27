from dataclasses import replace

import pytest

from lsqverify.load_queue.actor import LoadActor
from lsqverify.load_queue.recovery import RecoveringActor
from lsqverify.load_queue.types import Bus, Bypass, Inputs
from lsqverify.vlq.types import Redirect


def nc_load(load):
    return replace(load, execution=replace(load.execution, need_replay=True, causes=1, nc=True))


async def serve(actor, uid, sid, data, *, error=False):
    lq, owner = actor.env, actor.owner(uid)
    for _ in range(80):
        if lq.observed["io_uncache_req_valid"]:
            break
        await actor.step()
    assert lq.observed["io_uncache_req_valid"] and lq.observed["io_uncache_req_bits_addr"] == owner.load.paddr
    mid = lq.observed["io_uncache_req_bits_id"]
    await actor.step(Inputs(bus=Bus(ready=True)))
    await actor.step(Inputs(bus=Bus(ack=True, mid=mid, sid=sid)))
    await actor.step(Inputs(bus=Bus(response=True, response_id=sid, data=data, error=error, nderr=error)))
    return mid


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("fault", (False, True))
@pytest.mark.parametrize("reuse", (False, True), ids=("distinct-sid-control", "returned-sid-reused"))
async def test_returned_sid_new_response_cannot_overwrite_old_unconsumed_load(lq, lane, fault, reuse):
    actor = LoadActor(lq)
    old = (await actor.dispatch(configure=nc_load))[0]
    await actor.execute([old])
    await serve(actor, old, 4, 0x1122334455667788, error=fault)
    for _ in range(5):
        await actor.step()
    assert any(lq.observed[f"io_replay_{bank}_valid"] for bank in range(3))
    new = (await actor.dispatch(configure=nc_load))[0]
    await actor.execute([new])
    if reuse:
        lq.reach("LQ-UNCACHE.sid_reuse")
    await serve(actor, new, 4 if reuse else 5, 0xAABBCCDDEEFF0011, error=not fault)
    for _ in range(12):
        await actor.step(Inputs(replay_ready=(True,) * 3))
        if {old, new} <= set(actor.issued):
            break
    assert {old, new} <= set(actor.issued)
    for uid, value, error in ((old, 0x1122334455667788, fault), (new, 0xAABBCCDDEEFF0011, not fault)):
        queries = [Bypass()] * 3
        queries[lane] = Bypass(True, actor.owner(uid).load.execution.uop.lq, True, False)
        await actor.step(Inputs(bypass=tuple(queries)))
        assert lq.observed[f"io_bypass_{lane}_s1Resp_valid"]
        await actor.step()
        assert lq.observed[f"io_bypass_{lane}_s2Resp_valid"]
        assert lq.observed[f"io_bypass_{lane}_s2Resp_bits_data"] == value * ((1 << 64) + 1)
        assert lq.observed[f"io_bypass_{lane}_s2Resp_bits_derr"] == int(error)
        await actor.feedback([uid])
    await actor.drain()
    if reuse:
        actor.checked(("LQ-UNCACHE.sid_reuse",), [old, new])


async def test_real_full_uncache_reject_rollback_recover_reuse_and_fair_drain(lq):
    actor = RecoveringActor(lq)
    uids = []
    for count in (8, 8, 1):
        uids.extend(await actor.dispatch((1,) * count, configure=nc_load))
    for uid in uids[:16]:
        await actor.execute([uid])
    for _ in range(3):
        await actor.step()
    await actor.execute([uids[16]])
    for _ in range(3):
        await actor.step()
        if lq.observed["io_nack_rollback_0_valid"]:
            break
    assert lq.observed["io_nack_rollback_0_valid"]
    assert lq.observed["io_nack_rollback_0_bits_robIdx_value"] == actor.owner(uids[16]).rob.value
    lq.reach("LQ-UNCACHE.full")
    await actor.step(Inputs(redirect=Redirect(True, actor.owner(uids[16]).rob, True)))
    await actor.settle()
    # Arbitration order is selected by real requests, not entry/model state.
    returned, payload = set(), {}
    while len(returned) < 16:
        for _ in range(80):
            if lq.observed["io_uncache_req_valid"]:
                break
            await actor.step()
        pa = lq.observed["io_uncache_req_bits_addr"]
        owner = next(actor.owner(uid) for uid in uids[:16] if actor.owner(uid).load.paddr == pa)
        assert owner.uid not in returned
        value = 0x1020304050607000 | owner.uid
        await serve(actor, owner.uid, len(returned), value, error=bool(owner.uid & 1))
        returned.add(owner.uid)
        payload[owner.uid] = value
    for _ in range(100):
        await actor.step(Inputs(replay_ready=(True,) * 3))
        if returned <= set(actor.issued):
            break
    assert returned <= set(actor.issued)
    for uid in uids[:16]:
        queries = (Bypass(True, actor.owner(uid).load.execution.uop.lq, True), Bypass(), Bypass())
        await actor.step(Inputs(bypass=queries))
        await actor.step()
        assert lq.observed["io_bypass_0_s2Resp_valid"] and lq.observed["io_bypass_0_s2Resp_bits_data"] == payload[uid] * ((1 << 64) + 1)
        await actor.feedback([uid])
    await actor.drain()
    new = await actor.dispatch()
    await actor.drain()
    actor.prove_reuse(("LQ-UNCACHE.full",), [uids[16]])
    assert set(uids[:16] + new) <= actor.completed
