
from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.load_queue.recovery import RecoveringActor
from suites.memblock.lsq.load_queue.types import Bus, Inputs, Load
from suites.memblock.lsq.rar.types import Query as RarQuery
from suites.memblock.lsq.raw.types import Query as RawQuery
from suites.memblock.lsq.replay.types import Cause, TlbHint
from suites.memblock.lsq.vlq.types import QueuePtr, Redirect


@pytest.mark.parametrize("all_cancel", (False, True))
@pytest.mark.parametrize("concurrent", (False, True))
async def test_shared_redirect_real_queues_and_same_slot_new_uid_completion(lq, all_cancel, concurrent):
    actor = RecoveringActor(lq)
    uids = await actor.dispatch((1,) * 8)
    owners = [actor.owner(uid) for uid in uids]
    await actor.step(Inputs(rar_queries=tuple(RarQuery(True, o.rob, QueuePtr.encode(o.position), o.load.paddr, True) for o in owners[1:4]),
                            raw_queries=tuple(RawQuery(True, o.rob, o.load.execution.uop.sq, o.load.paddr, 255, True) for o in owners[4:7])))
    for owner in owners[6:]:
        owner.load = replace(owner.load, execution=replace(owner.load.execution, need_replay=True, causes=1 << Cause.TLB_MISS, tlb_id=9))
    await actor.execute(uids[6:])
    for _ in range(3):
        await actor.step()
    red = Redirect(True, owners[0 if all_cancel else 3].rob, all_cancel)
    controls = Inputs(redirect=red)
    if concurrent:
        controls = replace(controls, loads=(owners[5].load, Load(), Load()))
    names = ("LQ-RECOVER.all" if all_cancel else "LQ-RECOVER.partial", "LQ-RECOVER.reuse")
    lq.reach(*names)
    if concurrent:
        lq.reach("LQ-RECOVER.concurrent")
    await actor.step(controls)
    old_uids = sorted(actor.cancelled)
    await actor.settle()
    new_uids = await actor.dispatch((1,) * len(old_uids))
    await actor.drain()
    assert set(new_uids) <= actor.completed
    actor.prove_reuse(names + (("LQ-RECOVER.concurrent",) if concurrent else ()), old_uids)


async def test_sent_uncache_redirect_waits_for_original_response_then_same_slot_reuse(lq):
    actor = RecoveringActor(lq)
    uids = await actor.dispatch(configure=lambda load: replace(load, execution=replace(load.execution, nc=True, need_replay=True, causes=1)))
    owner = actor.owner(uids[0])
    await actor.execute(uids)
    for _ in range(40):
        if lq.observed[P.p_uncache_req_valid]:
            break
        await actor.step()
    assert lq.observed[P.p_uncache_req_valid]
    mid = lq.observed[P.p_uncache_req_bits_id]
    await actor.step(Inputs(bus=Bus(ready=True)))
    await actor.step(Inputs(bus=Bus(ack=True, mid=mid, sid=8)))
    lq.reach("LQ-RECOVER.sent_uncache")
    await actor.step(Inputs(redirect=Redirect(True, owner.rob, True)))
    await actor.settle()
    for _ in range(4):
        await actor.step()
        assert not lq.observed[P.p_replayAllocate] and not any(lq.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    await actor.step(Inputs(bus=Bus(response=True, response_id=8, data=0xAABBCCDD, error=True, nderr=True)))
    for _ in range(5):
        await actor.step()
    new = await actor.dispatch()
    await actor.drain()
    actor.prove_reuse(("LQ-RECOVER.sent_uncache",), uids)
    assert set(new) <= actor.completed


@pytest.mark.parametrize("phase", ("active", "blocked", "selected", "issued", "bus"))
async def test_active_reset_aborts_old_owner_and_same_physical_lq_new_uid_completes(lq, phase):
    actor = RecoveringActor(lq)
    def configure(load):
        cause = Cause.UNCACHE if phase == "bus" else Cause.TLB_MISS if phase == "blocked" else Cause.BANK_CONFLICT
        return replace(load, execution=replace(load.execution, need_replay=True, causes=1 << cause, nc=phase == "bus", tlb_id=9))
    old = await actor.dispatch(configure=configure)
    if phase != "active":
        await actor.execute(old)
        for _ in range(5):
            await actor.step(Inputs(replay_ready=(True,) * 3 if phase == "issued" else (False,) * 3))
    if phase == "bus":
        assert lq.observed[P.p_uncache_req_valid]
        mid = lq.observed[P.p_uncache_req_bits_id]
        await actor.step(Inputs(bus=Bus(ready=True)))
        await actor.step(Inputs(bus=Bus(ack=True, mid=mid, sid=3)))
    name = "LQ-RESET.active" if phase == "active" else "LQ-RESET.waiting"
    lq.reach(name)
    assert await actor.reset() == old
    new = await actor.dispatch()
    await actor.drain()
    actor.prove_reuse((name,), old)
    assert set(new) <= actor.completed
