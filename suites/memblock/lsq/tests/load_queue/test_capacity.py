from dataclasses import replace

from suites.memblock.lsq.load_queue.actor import LoadActor
from suites.memblock.lsq.load_queue.types import Inputs
from suites.memblock.lsq.rar.types import Query as RarQuery
from suites.memblock.lsq.raw.types import Query as RawQuery, SqPtr
from suites.memblock.lsq.replay.types import Cause
from suites.memblock.lsq.vlq.types import QueuePtr


async def test_full_virtual_queue_four_generations_and_reverse_completions(lq):
    actor = LoadActor(lq)
    all_uids = []
    for generation in range(4):
        uids = []
        for group in range(15):
            uids.extend(await actor.dispatch((8,), lanes=(group % 8,)))
        assert actor.tail - actor.head == 120
        lq.reach("LQ-ALLOC.capacity", "LQ-ALLOC.wrap", "LQ-HEAD.rollover")
        for start in range(120, 0, -3):
            await actor.execute(uids[start - 3:start])
            if start > 3:
                assert not any(uid in actor.completed for uid in uids)
        await actor.drain()
        all_uids.extend(uids)
    assert len(actor.completed) == 480 and actor.head == actor.tail == 480
    actor.checked(("LQ-ALLOC.capacity", "LQ-ALLOC.wrap", "LQ-HEAD.rollover"), all_uids)


async def fill_virtual(actor):
    uids = []
    for _ in range(15):
        uids.extend(await actor.dispatch((1,) * 8))
    return uids


async def test_real_rar_full_blocks_replay_then_vlq_completion_reclaims_and_wakes(lq):
    actor = LoadActor(lq)
    uids = await fill_virtual(actor)
    for start in range(1, 97, 3):
        owners = [actor.owner(uid) for uid in uids[start:start + 3]]
        queries = tuple(RarQuery(True, o.rob, QueuePtr.encode(o.position), o.load.paddr, True, True) for o in owners)
        await actor.step(Inputs(rar_queries=queries))
    target = actor.owner(uids[-1])
    target.load = replace(target.load, execution=replace(target.load.execution, need_replay=True, causes=1 << Cause.RAR_CAPACITY))
    await actor.execute([target.uid])
    lq.reach("LQ-CAPACITY.rar_block")
    for _ in range(8):
        await actor.step(Inputs(replay_ready=(True,) * 3))
        assert target.uid not in actor.issued and not actor.completed
    # No rarFull/head input exists on this top. Only real S3 completions can
    # move VLQ head, reclaim RAR, and unblock the internal Replay dependency.
    await actor.drain()
    actor.checked(("LQ-CAPACITY.rar_block", "LQ-CAPACITY.rar_wake"), uids)


async def test_real_raw_full_blocks_replay_and_sq_progress_reclaims_and_wakes(lq):
    actor = LoadActor(lq)
    uids = await fill_virtual(actor)
    for start in range(0, 56, 3):
        owners = [actor.owner(uid) for uid in uids[start:min(56, start + 3)]]
        queries = tuple(RawQuery(True, o.rob, o.load.execution.uop.sq, o.load.paddr, 255, True) for o in owners)
        await actor.step(Inputs(raw_queries=queries + (RawQuery(),) * (3 - len(queries))))
    target = actor.owner(uids[-1])
    target.load = replace(target.load, execution=replace(target.load.execution, need_replay=True, causes=1 << Cause.RAW_CAPACITY))
    await actor.execute([target.uid])
    lq.reach("LQ-CAPACITY.raw_block")
    for _ in range(8):
        await actor.step(Inputs(replay_ready=(True,) * 3))
        assert target.uid not in actor.issued and not actor.completed
    await actor.drain(controls=Inputs(address_ready=SqPtr.encode(11)))
    actor.checked(("LQ-CAPACITY.raw_block", "LQ-CAPACITY.raw_wake"), uids)
