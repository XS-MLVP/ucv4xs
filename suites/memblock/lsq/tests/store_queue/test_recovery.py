
import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.store_queue.actor import StoreActor


@pytest.mark.parametrize("phase", ("queue", "cache", "uncache", "wb"))
async def test_active_reset_real_both_queues_same_slot_new_uid_completes(sq, phase):
    actor = StoreActor(sq)
    old = actor.add(cbo=1 if phase in ("cache", "wb") else None, memory=2 if phase == "uncache" else 0)
    for _ in range(35):
        await actor.step(fair=True, sbuffer_ready=(False, False), cache_response=False, uncache_response=False, writeback_ready=False)
        if phase == "queue" and sq.observed[P.p_writeToSbuffer_req_0_valid]:
            break
        if phase in ("cache", "wb", "uncache") and actor.pending:
            break
    if phase == "queue":
        assert sq.observed[P.p_writeToSbuffer_req_0_valid]
    else:
        assert actor.pending is not None
        if phase == "wb":
            await actor.step(fair=True, writeback_ready=False)
            assert sq.observed[P.p_writeBack_valid]
    assert await actor.reset() == list(old.flows)
    new = actor.add(size=2)
    await actor.drain()
    assert actor.all[new.flows[0]].position == actor.all[old.flows[0]].position == 0
    actor.checked(("SQ-RESET.active",), new.flows)


@pytest.mark.parametrize("with_page", (False, True))
async def test_exception_and_optional_uq_cancel_all_new_uid_finishes(sq, with_page):
    actor = StoreActor(sq)
    old = actor.add(exception=True)
    young = actor.add(page=True, offset=12) if with_page else None
    for _ in range(35):
        await actor.step(fair=True, advance_rob=False, sbuffer_ready=(False, False))
        if all(actor.all[uid].s2_done for uop in (old, young) if uop for uid in uop.flows):
            break
    assert not actor.completed and not sq.observed[P.p_writeToSbuffer_req_0_valid]
    cancelled = await actor.cancel(old, flush_self=True)
    assert cancelled == [*old.flows, *(young.flows if young else ())]
    new = actor.add(size=3, page=with_page)
    new_page = actor.add(size=3, page=True) if with_page else None
    await actor.drain()
    names = ("SQ-PERMIT.exception", "SQ-RECOVER.empty", "SQ-RECOVER.suffix", "SQ-REUSE.cancelled")
    if with_page:
        assert actor.all[young.flows[0]].page_sent and actor.all[new_page.flows[0]].page_sent
        assert actor.all[young.flows[0]].position == actor.all[new_page.flows[0]].position
        names += ("SQ-RECOVER.page",)
    actor.checked(names, (*new.flows, *(new_page.flows if new_page else ())))


@pytest.mark.parametrize("base", (0, 62))
async def test_suffix_recovery_across_sq_flags_and_new_owners(sq, base):
    actor = StoreActor(sq, seed=0x6301)
    if base:
        for _ in range(base):
            actor.add()
        await actor.drain()
    keep, cancel0, cancel1 = actor.add(), actor.add(), actor.add()
    for _ in range(18):
        await actor.step(fair=True, advance_rob=False, sbuffer_ready=(False, False))
    old = await actor.cancel(keep)
    assert old == [*cancel0.flows, *cancel1.flows]
    new = [actor.add(), actor.add()]
    assert [actor.all[item.flows[0]].position for item in new] == [base + 1, base + 2]
    await actor.drain()
    names = ("SQ-RECOVER.suffix", "SQ-REUSE.cancelled") + (("SQ-RECOVER.wrap",) if base else ())
    actor.checked(names, [*keep.flows, *(uid for item in new for uid in item.flows)])


async def test_release_retired_prefix_then_walk_keeps_exclusive_end(sq):
    actor = StoreActor(sq)
    uops = [actor.add() for _ in range(14)]
    for _ in range(50):
        await actor.step(fair=True, advance_rob=False, sbuffer_ready=(False, False))
        if all(actor.all[uid].s2_done and actor.all[uid].data_sent for item in uops for uid in item.flows):
            break
    assert all(actor.all[uid].s2_done and actor.all[uid].data_sent for item in uops for uid in item.flows)
    for item in uops[:10]:
        item.retired_by_rob = True
    actor.rob_order = uops[10].rob_order
    await actor.step(issue=False, dispatch=False, advance_rob=False, rob_head=uops[10].rob, sbuffer_ready=(False, False))
    old = await actor.cancel(uops[10])
    assert old == [uid for item in uops[11:] for uid in item.flows]
    new = [actor.add() for _ in range(3)]
    await actor.drain()
    actor.checked(("SQ-RECOVER.release_walk", "SQ-RECOVER.suffix", "SQ-REUSE.cancelled"), [*uops[10].flows, *(uid for item in new for uid in item.flows)])
