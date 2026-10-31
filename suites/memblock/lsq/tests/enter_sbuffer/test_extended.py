
from dataclasses import replace
import random

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.enter_sbuffer.types import Inputs, Offer, Write, encode


@pytest.mark.parametrize("odd_tail", (False, True))
async def test_pair_backpressure_and_surviving_tail_compacts_to_lane0(enter_sbuffer, odd_tail):
    env = enter_sbuffer
    if odd_tail:
        await env.cycle(env.write(90))
        await env.drain()
    first, second = env.write(1), env.write(2)
    change = await env.cycle(first, second)
    first_uid, second_uid = [item["uid"] for item in change["accepted"]]
    env.arm("ESB-HOLD.both")
    await env.idle(6)
    change = await env.cycle(ready=(True, False))
    assert [x["uid"] for x in change["consumed"]] == [first_uid]
    assert env.observed[P.p_toSbuffer_req_0_bits_data] == second.data
    assert not env.observed[P.p_toSbuffer_req_1_valid]
    env.arm(("ESB-ORDER.lane_compaction", "ESB-HOLD.tail_after_head"), [second_uid])
    await env.idle(4)
    await env.drain()


async def test_only_accepted_prefix_owns_capacity_then_reoffer_tail_at_lane0(enter_sbuffer):
    env = enter_sbuffer
    await env.cycle(env.write(1))
    first, second = env.write(2), env.write(3)
    change = await env.cycle(first, second)
    assert len(change["accepted"]) == 1 and change["accepted"][0]["write"]["data"] == first.data
    assert env.pre_observed[P.p_fromDeqModule_0_ready] and not env.pre_observed[P.p_fromDeqModule_1_ready]
    first_uid = change["accepted"][0]["uid"]
    change = await env.cycle(second, ready=(True, False))
    second_uid = change["accepted"][0]["uid"]
    assert env.model.sequence == 3
    env.arm("ESB-ADMIT.partial_accept", [first_uid, second_uid])
    await env.drain()


@pytest.mark.parametrize("old_count,new_count", ((1, 1), (1, 2), (2, 1), (2, 2)))
async def test_simultaneous_consumption_reuses_exact_capacity(enter_sbuffer, old_count, new_count):
    env = enter_sbuffer
    old = tuple(env.write(i + 1) for i in range(old_count))
    new = tuple(env.write(i + 20) for i in range(new_count))
    change = await env.cycle(*old)
    uids = [x["uid"] for x in change["accepted"]]
    change = await env.cycle(*new, ready=(True, True))
    assert len(change["consumed"]) == old_count and len(change["accepted"]) == new_count
    assert [x["write"]["data"] for x in change["consumed"]] == [w.data for w in old]
    uids.extend(x["uid"] for x in change["accepted"])
    name = {1: "one", 2: "two"}
    env.arm(f"ESB-REUSE.{name[old_count]}_to_{name[new_count]}", uids)
    await env.drain()


async def test_full_without_consumer_fire_does_not_accept_or_overwrite(enter_sbuffer):
    env = enter_sbuffer
    change = await env.cycle(env.write(1), env.write(2))
    uids = [x["uid"] for x in change["accepted"]]
    pending = (env.write(31), env.write(32))
    for _ in range(5):
        change = await env.cycle(*pending)
        assert not change["accepted"] and not change["consumed"]
        assert not env.observed[P.p_fromDeqModule_0_ready] and not env.observed[P.p_fromDeqModule_1_ready]
    env.arm("ESB-REUSE.full_block", uids)
    await env.cycle(*pending, ready=(True, True))
    await env.drain()


@pytest.mark.parametrize("separate", (False, True))
async def test_split_two_writes_contribute_exactly_one_sq_credit(enter_sbuffer, separate):
    env = enter_sbuffer
    first, second = env.write(11, credit=False), env.write(12)
    await env.cycle(first, second)
    env.arm("ESB-CREDIT.split_separate" if separate else "ESB-CREDIT.split_pair")
    if separate:
        await env.cycle(ready=(True, False))
        assert [env.pre_observed[P.io(f"deqPtrMove_{i}")] for i in range(2)] == [0, 0]
        await env.idle(4)
        await env.cycle(ready=(True, False))
        assert [env.pre_observed[P.io(f"deqPtrMove_{i}")] for i in range(2)] == [1, 0]
    else:
        await env.cycle(ready=(True, True))
        assert [env.pre_observed[P.io(f"deqPtrMove_{i}")] for i in range(2)] == [0, 1]
    await env.drain()


@pytest.mark.parametrize("old_credit", (False, True))
async def test_same_cycle_overwrite_uses_old_consumption_credit(enter_sbuffer, old_credit):
    env = enter_sbuffer
    await env.cycle(env.write(5, credit=old_credit))
    old_uid = env.model.order[0].uid
    await env.cycle(env.write(6, credit=not old_credit), ready=(True, False))
    assert env.pre_observed[P.p_deqPtrMove_0] == old_credit
    assert env.observed[P.p_deqPtrMove_0] == (not old_credit)
    env.arm("ESB-CREDIT.same_cycle_old_flag", [old_uid, env.model.order[0].uid])
    await env.drain()


@pytest.mark.parametrize("phase", ("one_live", "two_live", "wrapped"))
async def test_active_reset_aborts_old_writes_without_consumption_credit(enter_sbuffer, phase):
    env = enter_sbuffer
    if phase == "wrapped":
        await env.cycle(env.write(17))
        await env.drain()
    await env.cycle(*(env.write(i + 1, credit=False if i == 0 else True) for i in range(2 if phase == "two_live" else 1)))
    await env.idle(3)
    await env.reset()
    await env.cycle(env.write(99))
    env.arm("ESB-RESET." + phase)
    await env.drain()


async def test_disabled_payload_noise_cannot_modify_pending_write(enter_sbuffer):
    env = enter_sbuffer
    await env.cycle(env.write(1))
    env.arm(("ESB-IDLE.disabled_noise", "ESB-ADMIT.disabled"))
    for index in range(8):
        await env.cycle(offers=(Offer(False, env.write(index + 100, credit=bool(index % 2))), Offer(False, env.write(index + 200))))
        assert len(env.model.order) == 1 and env.observed[P.p_toSbuffer_req_0_bits_data] == env.write(1).data
    await env.drain()


@pytest.mark.parametrize("field,width", (("data", 128), ("mask", 16), ("paddr", 48), ("vaddr", 50)))
async def test_walking_one_zero_payload_is_not_regenerated(enter_sbuffer, field, width):
    env = enter_sbuffer
    scene = {"data": "data_bits", "mask": "mask_bits", "paddr": "address_bits", "vaddr": "address_bits"}[field]
    for bit in range(width):
        for complement in (False, True):
            value = (1 << bit) ^ (((1 << width) - 1) if complement else 0)
            first = replace(env.write(1 + bit), **{field: value}, wline=complement)
            second = replace(env.write(256 + bit), **{field: value ^ ((1 << width) - 1)}, wline=not complement)
            await env.cycle(first, second)
            env.arm(("ESB-PAYLOAD." + scene, "ESB-PAYLOAD.wline"))
            await env.drain()


async def test_consecutive_double_width_has_no_empty_bubble_or_duplicate(enter_sbuffer):
    env = enter_sbuffer
    uids = []
    for batch in range(160):
        change = await env.cycle(env.write(batch * 2 + 1, credit=bool(batch % 2)), env.write(batch * 2 + 2), ready=(True, True))
        assert len(change["accepted"]) == 2 and len(change["consumed"]) == (2 if batch else 0)
        assert not env.observed[P.p_empty]
        uids.extend(x["uid"] for x in change["accepted"])
    env.arm(("ESB-REUSE.consecutive", "ESB-ORDER.wrap", "ESB-CONCURRENT.throughput"), uids)
    await env.drain()


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_valid_prefix_flow_and_fair_final_drain(enter_sbuffer, seed):
    env = enter_sbuffer
    rng, pending, uids, tag = random.Random(seed), [], [], 0
    for cycle in range(1000):
        for _ in range(rng.randrange(4)):
            tag += 1
            pending.append(replace(env.write(tag, credit=rng.random() < 0.7), data=rng.getrandbits(128), mask=rng.getrandbits(16)))
        n = min(2, len(pending))
        if n == 2 and not pending[1].credit:
            n = 1
        ready = rng.choice(((False, False), (True, False), (True, True)))
        change = await env.cycle(*pending[:n], ready=ready)
        del pending[:len(change["accepted"])]
        uids.extend(x["uid"] for x in change["accepted"])
    while pending:
        n = min(2, len(pending))
        if n == 2 and not pending[1].credit:
            n = 1
        change = await env.cycle(*pending[:n], ready=(True, True))
        del pending[:len(change["accepted"])]
        uids.extend(x["uid"] for x in change["accepted"])
    env.arm("ESB-CONCURRENT.seeded", uids)
    await env.drain()


async def test_static_illegal_producer_domains_are_rejected_not_driven(enter_sbuffer):
    env = enter_sbuffer
    malformed = (Inputs((Offer(), Offer(True))), Inputs(ready=(False, True)), Inputs((Offer(), Offer(False, Write(credit=False)))),
                 Inputs((Offer(True, Write(paddr=1 << 48)), Offer())), Inputs((Offer(True, Write(vaddr=1 << 50)), Offer())),
                 Inputs((Offer(True, Write(data=1 << 128)), Offer())), Inputs((Offer(True, Write(mask=-1)), Offer())))
    for inp in malformed:
        with pytest.raises(ValueError):
            encode(inp)
    await env.cycle(env.write(8))
    await env.drain()
