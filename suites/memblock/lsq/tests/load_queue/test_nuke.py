"""Real RAR/RAW storage, revoke, release and two-store recovery paths.

Queries remain on active dispatched ROB/LQ identities. The full-slot RAR CAM
probe varies the still-uncompleted head's public query address: that is an
explicit UNIT-INTERFACE CAM stress, not a claim about one immutable software
instruction accessing many physical addresses or an architectural outcome.
"""
from dataclasses import replace

import pytest

from lsqverify.load_queue.actor import LoadActor
from lsqverify.load_queue.types import Inputs
from lsqverify.rar.types import Query as RarQuery, Release
from lsqverify.raw.types import Query as RawQuery, SqPtr, Store
from lsqverify.vlq.types import QueuePtr, RobPtr


async def allocate(actor, count):
    uids = []
    while count:
        batch = min(count, 8)
        uids.extend(await actor.dispatch((1,) * batch))
        count -= batch
    return uids


def rar_query(owner, *, nc=False, address=None):
    return RarQuery(True, owner.rob, QueuePtr.encode(owner.position), owner.load.paddr if address is None else address, True, nc)


def raw_query(owner, *, address=None, mask=255, data=True):
    u = owner.load.execution.uop
    return RawQuery(True, owner.rob, u.sq, owner.load.paddr if address is None else address, mask, data, u.rvc, u.ftq, u.offset, u.checkpoint)


@pytest.mark.parametrize("lane", range(3))
async def test_rar_all_96_slots_unique_address_cam_unit_interface(lq, lane):
    actor = LoadActor(lq)
    uids = await allocate(actor, 97)
    old = actor.owner(uids[0])
    for uid in uids[1:]:
        queries = [RarQuery()] * 3
        queries[lane] = rar_query(actor.owner(uid), nc=True)
        await actor.step(Inputs(rar_queries=tuple(queries)))
        assert lq.pre_observed[f"io_ldu_rarNukeQuery_{lane}_req_ready"]
    lq.reach("LQ-RAR.all_slots")
    for uid in uids[1:]:
        address = actor.owner(uid).load.paddr
        query = rar_query(old, address=address)
        queries = [RarQuery()] * 3
        queries[(lane + 1) % 3] = query
        await actor.step(Inputs(rar_queries=tuple(queries)))
        assert lq.observed[f"io_ldu_rarNukeQuery_{(lane + 1) % 3}_resp_bits_nuke"]
    await actor.drain()
    actor.checked(("LQ-RAR.all_slots",), uids)


@pytest.mark.parametrize("age", (1, 2))
@pytest.mark.parametrize("lane", range(3))
async def test_shared_rar_revoke_then_same_lq_query_has_no_ghost(lq, lane, age):
    actor = LoadActor(lq)
    uids = await allocate(actor, 2)
    old, young = [actor.owner(uid) for uid in uids]
    queries = [RarQuery()] * 3
    queries[lane] = rar_query(young, nc=True)
    await actor.step(Inputs(rar_queries=tuple(queries)))
    if age == 2:
        await actor.step()
    mask = tuple(i == lane for i in range(3))
    lq.reach("LQ-RAR.revoke")
    await actor.step(Inputs(**{"rar_revoke_last" if age == 1 else "rar_revoke_older": mask}))
    probe = [RarQuery()] * 3
    probe[(lane + 1) % 3] = rar_query(old, address=young.load.paddr)
    await actor.step(Inputs(rar_queries=tuple(probe)))
    assert not lq.observed[f"io_ldu_rarNukeQuery_{(lane + 1) % 3}_resp_bits_nuke"]
    await actor.drain()
    actor.checked(("LQ-RAR.revoke",), uids)


@pytest.mark.parametrize("previous", (False, True))
@pytest.mark.parametrize("lane", range(3))
async def test_release_window_through_real_parent_keeps_precise_line(lq, previous, lane):
    actor = LoadActor(lq)
    uids = await allocate(actor, 2)
    old, young = [actor.owner(uid) for uid in uids]
    release = Release(True, young.load.paddr)
    if previous:
        await actor.step(Inputs(release=release))
    query = [RarQuery()] * 3
    query[lane] = rar_query(young)
    await actor.step(Inputs(rar_queries=tuple(query), release=Release() if previous else release))
    lq.reach("LQ-RAR.previous_release" if previous else "LQ-RAR.release")
    probe = [RarQuery()] * 3
    probe[(lane + 1) % 3] = rar_query(old, address=young.load.paddr)
    await actor.step(Inputs(rar_queries=tuple(probe)))
    assert lq.observed[f"io_ldu_rarNukeQuery_{(lane + 1) % 3}_resp_bits_nuke"]
    await actor.drain()
    actor.checked(("LQ-RAR.previous_release" if previous else "LQ-RAR.release",), uids)


@pytest.mark.parametrize("lane", range(3))
async def test_raw_all_56_slots_actual_unique_store_rollback(lq, lane):
    actor = LoadActor(lq)
    actor.rob_sequence = 1
    uids = await allocate(actor, 56)
    for uid in uids:
        query = [RawQuery()] * 3
        query[lane] = raw_query(actor.owner(uid))
        await actor.step(Inputs(raw_queries=tuple(query)))
        assert lq.pre_observed[f"io_ldu_rawNukeQuery_{lane}_req_ready"]
    await actor.step()
    lq.reach("LQ-RAW.all_slots")
    for uid in uids:
        owner = actor.owner(uid)
        await actor.step(Inputs(stores=(Store(True, RobPtr.encode(0), owner.load.paddr, 255, ftq_value=31, ftq_offset=7), Store())))
        await actor.step()
        await actor.step()
        assert lq.observed["io_nuke_rollback_0_valid"] and lq.observed["io_nuke_rollback_0_bits_robIdx_value"] == owner.rob.value
        assert lq.observed["io_nuke_rollback_0_bits_debug_runahead_checkpoint_id"] == owner.load.execution.uop.checkpoint
    await actor.drain(controls=Inputs(address_ready=SqPtr.encode(11)))
    actor.checked(("LQ-RAW.all_slots",), uids)


@pytest.mark.parametrize("variant", ("dual", "address", "mask", "older", "miss", "revoke_one", "revoke_two"))
async def test_raw_dual_ports_negative_and_revoke(lq, variant):
    actor = LoadActor(lq)
    actor.rob_sequence = 2
    uids = await allocate(actor, 2)
    a, b = [actor.owner(uid) for uid in uids]
    await actor.step(Inputs(raw_queries=(raw_query(a), raw_query(b), RawQuery())))
    if variant == "revoke_one":
        await actor.step(Inputs(raw_revoke_last=(True, True, False)))
    else:
        await actor.step()
    if variant == "revoke_two":
        await actor.step(Inputs(raw_revoke_older=(True, True, False)))
    store_a = Store(True, RobPtr.encode(0), a.load.paddr, 255, ftq_value=17, ftq_offset=5)
    store_b = Store(True, RobPtr.encode(1), b.load.paddr, 255, ftq_value=18, ftq_offset=6)
    if variant == "address":
        store_a, store_b = replace(store_a, paddr=store_a.paddr + 16), replace(store_b, paddr=store_b.paddr + 16)
    elif variant == "mask":
        store_a, store_b = replace(store_a, mask=0xFF00), replace(store_b, mask=0xFF00)
    elif variant == "older":
        store_a, store_b = replace(store_a, rob=RobPtr.encode(10)), replace(store_b, rob=RobPtr.encode(11))
    elif variant == "miss":
        store_a, store_b = replace(store_a, tlb_miss=True), replace(store_b, tlb_miss=True)
    await actor.step(Inputs(stores=(store_a, store_b)))
    await actor.step()
    await actor.step()
    expected = variant == "dual"
    assert [bool(lq.observed[f"io_nuke_rollback_{i}_valid"]) for i in range(2)] == [expected, expected]
    name = "LQ-RAW.dual_store" if expected else "LQ-RAW.revoke" if variant.startswith("revoke") else "LQ-RAW.negative"
    lq.reach(name)
    await actor.drain(controls=Inputs(address_ready=SqPtr.encode(11)))
    actor.checked((name,), uids)
