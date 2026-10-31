
from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.load_queue.actor import LoadActor
from suites.memblock.lsq.load_queue.types import Bus, Bypass, Inputs


@pytest.mark.parametrize("nc", (True, False), ids=("nc", "mmio"))
@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("fault", (False, True))
async def test_real_bus_wakeup_replay_bypass_shared_feedback_complete(lq, nc, lane, fault):
    actor = LoadActor(lq)
    def configure(load):
        return replace(load, execution=replace(load.execution, nc=nc, need_replay=True, causes=1), mmio=not nc)
    uids = await actor.dispatch(configure=configure)
    await transfer(actor, uids, nc=nc, lane=lane, fault=fault)


async def transfer(actor, uids, *, nc, lane, fault):
    lq = actor.env
    owner = actor.owner(uids[0])
    base = Inputs(pending=owner.rob, pending_next=owner.rob)
    await actor.execute(uids, controls=base)
    lq.reach("LQ-UNCACHE.nc" if nc else "LQ-UNCACHE.mmio", "LQ-UNCACHE.wake", "LQ-UNCACHE.bypass")
    for _ in range(40):
        if lq.observed[P.p_uncache_req_valid]:
            break
        await actor.step(base)
        assert not any(lq.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    else:
        raise AssertionError("real Uncache request did not reach public LoadQueue bus")
    assert lq.observed[P.p_uncache_req_bits_addr] == owner.load.paddr
    assert lq.observed[P.p_uncache_req_bits_nc] == int(nc)
    mid = lq.observed[P.p_uncache_req_bits_id]
    await actor.step(replace(base, bus=Bus(ready=True)))
    await actor.step(replace(base, bus=Bus(ack=True, mid=mid, sid=7)))
    for _ in range(3):
        await actor.step(base)
        assert not any(lq.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    data = 0x9988776655443322
    await actor.step(replace(base, bus=Bus(response=True, response_id=7, data=data, error=fault, nderr=fault)))
    for _ in range(40):
        if any(lq.observed[P.io(f"replay_{bank}_valid")] for bank in range(3)):
            break
        await actor.step(base)
    else:
        raise AssertionError("real internal Uncache wake did not unblock Replay")
    await actor.step(replace(base, replay_ready=(True,) * 3))
    assert uids[0] in actor.issued and uids[0] not in actor.completed
    bypass = [Bypass()] * 3
    bypass[lane] = Bypass(True, owner.load.execution.uop.lq, nc, not nc)
    await actor.step(replace(base, bypass=tuple(bypass)))
    prefix = P.io(f"bypass_{lane}_")
    assert lq.observed[prefix + "s1Resp_valid"] and lq.observed[prefix + "s1Resp_bits_paddr"] == owner.load.paddr
    assert lq.observed[P.p_exceptionInfo_valid] and lq.observed[P.p_exceptionInfo_bits_vaddr] == owner.load.fullva
    await actor.step(base)
    assert lq.observed[prefix + "s2Resp_valid"] and lq.observed[prefix + "s2Resp_bits_data"] == data * ((1 << 64) + 1)
    assert lq.observed[prefix + "s2Resp_bits_derr"] == lq.observed[prefix + "s2Resp_bits_nderr"] == int(fault)
    await actor.feedback(uids, controls=base)
    await actor.drain(controls=base)
    actor.checked(("LQ-UNCACHE.nc" if nc else "LQ-UNCACHE.mmio", "LQ-UNCACHE.wake", "LQ-UNCACHE.bypass"), uids)
    if fault:
        actor.checked(("LQ-UNCACHE.errors",), uids)
    return mid


@pytest.mark.parametrize("lane", range(3))
async def test_all_real_uncache_entry_ids_both_types_complete_new_uids(lq, lane):
    actor = LoadActor(lq)
    visited, all_uids = set(), []
    for index in range(64):
        nc = bool(index // 16 % 2)
        uids = await actor.dispatch(configure=lambda load: replace(load, execution=replace(load.execution, nc=nc, need_replay=True, causes=1), mmio=not nc))
        mid = await transfer(actor, uids, nc=nc, lane=lane, fault=bool(index % 2))
        visited.add((mid, nc))
        all_uids.extend(uids)
    assert visited == {(entry, kind) for entry in range(16) for kind in (False, True)}
    actor.checked(("LQ-UNCACHE.all_entries",), all_uids)
