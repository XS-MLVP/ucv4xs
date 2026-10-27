from dataclasses import replace

import pytest

from lsqverify.load_queue.actor import LoadActor
from lsqverify.load_queue.types import Inputs, Load
from lsqverify.raw.types import Query as RawQuery, SqPtr, Store
from lsqverify.rar.types import Query as RarQuery, Release
from lsqverify.replay.types import Cause
from lsqverify.vlq.types import QueuePtr, RobPtr


async def test_shared_s3_multiple_flows_and_sparse_dispatch_complete(lq):
    actor = LoadActor(lq)
    uids = await actor.dispatch((3, 0, 5), lanes=(1, 4, 7))
    await actor.drain()
    actor.checked(("LQ-RESET.initial", "LQ-ALLOC.sparse", "LQ-ALLOC.multi_flow", "LQ-COMPLETE.prefix", "LQ-CONCURRENT.fair_drain"), uids)


@pytest.mark.parametrize("lane", range(8))
async def test_each_real_dispatch_lane_owns_new_completed_flow(lq, lane):
    actor = LoadActor(lq)
    uids = await actor.dispatch((1,), lanes=(lane,))
    await actor.drain()
    actor.checked(("LQ-ALLOC.all_lanes",), uids)


async def test_younger_s3_completion_cannot_pass_unfinished_head(lq):
    actor = LoadActor(lq)
    uids = await actor.dispatch((1, 1, 1))
    await actor.execute(uids[1:])
    for _ in range(5):
        await actor.step()
        assert not actor.completed and not lq.observed["io_lqEmpty"]
    await actor.drain()
    actor.checked(("LQ-COMPLETE.out_of_order", "LQ-COMPLETE.prefix"), uids)


@pytest.mark.parametrize("cause", (Cause.CACHE_REPLAY, Cause.WAY_PREDICTION, Cause.BANK_CONFLICT, Cause.VIOLATION))
async def test_replay_output_requires_shared_s3_feedback_before_lq_completion(lq, cause):
    actor = LoadActor(lq)
    uids = await actor.dispatch((1, 1, 1), configure=lambda load: replace(load, execution=replace(load.execution, need_replay=True, causes=1 << cause)))
    await actor.execute(uids)
    lq.reach("LQ-COMPLETE.replay_blocks", "LQ-REPLAY.feedback", "LQ-REPLAY.banks", "LQ-REPLAY.metadata")
    for _ in range(8):
        await actor.step()
        assert not actor.completed
    assert all(lq.observed[f"io_replay_{bank}_valid"] for bank in range(3))
    for _ in range(3):
        await actor.step()
    await actor.step(Inputs(replay_ready=(True,) * 3))
    assert len(actor.issued) == 3 and not actor.completed
    await actor.feedback(uids)
    await actor.drain()
    actor.checked(("LQ-COMPLETE.replay_blocks", "LQ-REPLAY.feedback", "LQ-REPLAY.banks", "LQ-REPLAY.metadata", "LQ-REPLAY.backpressure"), uids)


async def test_shared_s3_without_address_update_keeps_lq_live(lq):
    actor = LoadActor(lq)
    uids = await actor.dispatch()
    owner = actor.owner(uids[0])
    owner.load = replace(owner.load, update_address=False)
    await actor.execute(uids)
    for _ in range(5):
        await actor.step()
    assert not actor.completed
    owner.load = replace(owner.load, update_address=True)
    await actor.drain()
    actor.checked(("LQ-COMPLETE.address_blocks",), uids)


async def test_real_vlq_head_reclaims_rar_without_external_head_drive(lq):
    actor = LoadActor(lq)
    uids = await actor.dispatch((1, 1, 1))
    old, young = actor.owner(uids[0]), actor.owner(uids[2])
    address = 0xABC0040
    queries = (RarQuery(True, young.rob, QueuePtr.encode(young.position), address, True, True), RarQuery(), RarQuery())
    await actor.step(Inputs(rar_queries=queries))
    probe = (RarQuery(True, old.rob, QueuePtr.encode(old.position), address), RarQuery(), RarQuery())
    await actor.step(Inputs(rar_queries=probe))
    assert lq.observed["io_ldu_rarNukeQuery_0_resp_bits_nuke"]
    await actor.drain()
    # Querying the former head is not a new allocation; all young RAR owners
    # must have been reclaimed by the real internal VLQ pointer connection.
    await actor.step(Inputs(rar_queries=probe))
    assert not lq.observed["io_ldu_rarNukeQuery_0_resp_bits_nuke"]
    actor.checked(("LQ-HEAD.rar_release", "LQ-RAR.nc"), uids)


async def test_real_raw_store_collision_routes_original_load_and_mdp(lq):
    actor = LoadActor(lq)
    # A prior store occupies ROB0; dispatched loads start at ROB1.
    actor.rob_sequence = 1
    uids = await actor.dispatch((1, 1, 1))
    owner = actor.owner(uids[0])
    query = RawQuery(True, owner.rob, SqPtr.encode(10), owner.load.paddr, 0xFF, True,
                     owner.load.execution.uop.rvc, owner.load.execution.uop.ftq, owner.load.execution.uop.offset, owner.load.execution.uop.checkpoint)
    await actor.step(Inputs(raw_queries=(query, RawQuery(), RawQuery())))
    await actor.step()
    store = Store(True, RobPtr.encode(0), owner.load.paddr, 0xFF, ftq_value=17, ftq_offset=9)
    await actor.step(Inputs(stores=(store, Store())))
    await actor.step()
    await actor.step()
    assert lq.observed["io_nuke_rollback_0_valid"] and lq.observed["io_mdpTrain_valid"]
    assert lq.observed["io_nuke_rollback_0_bits_robIdx_value"] == owner.rob.value
    # Real SQ address progress releases RAW, independent of VLQ completion.
    await actor.step(Inputs(address_ready=SqPtr.encode(11)))
    # Keep this monotonic external SQ pointer while completing the loads.
    await actor.execute(uids, controls=Inputs(address_ready=SqPtr.encode(11)))
    for _ in range(8):
        await actor.step(Inputs(address_ready=SqPtr.encode(11)))
    actor.checked(("LQ-RAW.collision", "LQ-RAW.train", "LQ-CONCURRENT.directed"), uids)
