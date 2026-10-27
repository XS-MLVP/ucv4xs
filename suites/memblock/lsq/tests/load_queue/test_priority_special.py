from dataclasses import replace

import pytest

from lsqverify.load_queue.actor import LoadActor
from lsqverify.load_queue.types import Inputs
from lsqverify.replay.types import Cause, TlbHint
from lsqverify.vlq.types import RobPtr


@pytest.mark.parametrize("bank", range(3))
@pytest.mark.parametrize("window", ("head", "near", "wrap"))
async def test_real_vlq_program_head_feedback_overrides_replay_insertion_age(lq, bank, window):
    actor = LoadActor(lq)
    if window == "wrap":
        padding = await actor.dispatch((16,) * 7 + (7,))
        await actor.drain()
        assert set(padding) <= actor.completed and actor.head == 119
    uids = []
    for count in (8, 4):
        uids.extend(await actor.dispatch((1,) * count))
    target = uids[0 if window == "head" else 1]
    order = list(uids[4:12])
    order.insert(6 + bank, target)
    for uid in order:
        owner = actor.owner(uid)
        owner.load = replace(owner.load, execution=replace(owner.load.execution, need_replay=True, causes=1 << Cause.BANK_CONFLICT))
    for offset in range(0, 9, 3):
        await actor.execute(order[offset:offset + 3])
    for _ in range(3):
        await actor.step()
    assert lq.observed[f"io_replay_{bank}_bits_replayQueueIdx"] == bank
    await actor.step(Inputs(replay_ready=tuple(i == bank for i in range(3))))
    assert lq.observed[f"io_replay_{bank}_valid"]
    assert lq.observed[f"io_replay_{bank}_bits_replayQueueIdx"] == 6 + bank
    assert lq.observed[f"io_replay_{bank}_bits_uop_lqIdx_value"] == actor.owner(target).position % 120
    lq.reach("LQ-HEAD.replay_priority")
    await actor.drain()
    actor.checked(("LQ-HEAD.replay_priority",), uids)


@pytest.mark.parametrize("eligible,former_change", ((False, False), (True, False), (True, True)))
async def test_special_mode_exact_2048_boundary_and_real_next_rob_head(lq, eligible, former_change):
    actor = LoadActor(lq)
    def configure(load):
        return replace(load, execution=replace(load.execution, need_replay=True, causes=1 << Cause.TLB_MISS,
                                               tlb_id=15, special_eligible=eligible))
    uids = await actor.dispatch(configure=configure)
    owner = actor.owner(uids[0])
    base = Inputs(pending=owner.rob, pending_next=owner.rob)
    await actor.execute(uids, controls=base)
    trigger = lq.last_tick
    for _ in range(2046):
        await actor.step(base)
        assert not lq.observed["io_specialMode"]
    assert (lq.last_tick - trigger) // 2 == 2046
    await actor.step(base)
    assert not lq.observed["io_specialMode"]
    await actor.step(base)
    assert bool(lq.observed["io_specialMode"]) == eligible
    next_head = replace(owner.rob, former=not owner.rob.former) if former_change else RobPtr.encode(1)
    moved = replace(base, pending_next=next_head)
    await actor.step(moved)
    assert not lq.observed["io_specialMode"]
    await actor.step(replace(moved, fast_tlb=TlbHint(True, 15)))
    await actor.drain(controls=moved)
    if eligible:
        actor.checked(("LQ-SPECIAL.threshold", "LQ-SPECIAL.head_change"), uids)
