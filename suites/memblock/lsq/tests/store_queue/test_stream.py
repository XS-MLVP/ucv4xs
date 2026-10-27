import pytest

from lsqverify.store_queue.actor import StoreActor


async def test_all_physical_and_virtual_slots_four_generations_actual_completion(sq):
    actor = StoreActor(sq, seed=0x6101)
    uids = []
    for generation in range(4):
        for index in range(64):
            uids.extend(actor.add(size=(index + generation) % 5, lane=index % 8).flows)
        await actor.drain()
    assert len(actor.completed) == 256
    actor.checked(("SQ-WRITE.slots", "SQ-DISPATCH.lanes", "SQ-WRITE.sizes", "SQ-READY.upper"), uids)


async def test_real_vector_128_flows_capacity_and_force_write(sq):
    actor = StoreActor(sq, seed=0x6102)
    uids = [uid for _ in range(8) for uid in actor.add(flows=16, size=4).flows]
    for _ in range(6):
        await actor.step(fair=True, issue=False)
    sq.expect({"io_sbufferCtrl_req_forceWrite": 1, "io_sqFull": 0, "io_physicalUpperSqIdx_value": 0,
               "io_physicalUpperSqIdx_second_flag": 1, "io_sqDeqPtr_value": 0}, "real VSQ physical tail is 128 but only 64 physical entries can issue")
    await actor.drain()
    actor.checked(("SQ-CAPACITY.virtual", "SQ-CAPACITY.force", "SQ-DISPATCH.multi", "SQ-CREDIT.last_flow", "SQ-READY.upper"), uids)


@pytest.mark.parametrize("seed", (0x6201, 0x6202))
@pytest.mark.parametrize("full_domain", (False, True), ids=("controlled", "full-domain"))
async def test_real_closed_loop_seeded_mix_and_fair_drain(sq, seed, full_domain):
    actor = StoreActor(sq, seed=seed)
    rng, uids, target = actor.rng, [], 240
    names = ("SQ-CONCURRENT.seeded" if full_domain else "SQ-CONCURRENT.controlled",)
    reached = False
    limit = 128 if full_domain else 48
    for _ in range(5000):
        if len(uids) < target and actor.tail - actor.head < limit:
            choice = rng.randrange(10)
            if choice == 0:
                uop = actor.add(size=3, cbo=rng.randrange(4 if full_domain else 3))
            elif choice < 3:
                uop = actor.add(size=rng.randrange(4), offset=rng.choice((0, 8)), memory=rng.choice((1, 2, 7)))
            else:
                size = rng.randrange(5)
                uop = actor.add(size=size, offset=rng.randrange(16), page=size >= 3 and rng.random() < 0.1, retry=rng.random() < 0.1)
            uids.extend(uop.flows)
        await actor.step(query=rng.random() < 0.5)
        if not reached and sq.last_change["physical"]["sta_slots"] and sq.last_change["physical"]["std_slots"]:
            sq.begin(names)
            reached = True
        if len(uids) == target:
            break
    assert len(uids) == target
    await actor.drain()
    actor.checked(names, uids)
