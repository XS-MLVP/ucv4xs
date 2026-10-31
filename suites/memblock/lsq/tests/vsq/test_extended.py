"""Cases defined by the contract and initial missing-line classification."""

import random

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import Redirect, RobPtr


async def consume_prefix(env, start, end):
    """Fair PSQ agent: consume no more than two already-retired flows/edge."""
    for position in range(start, end, 2):
        await env.cycle(physical_deq=SqPtr.encode(min(position + 2, end)), consumed=True)
    await env.idle(2)


async def test_every_dispatch_lane_uses_all_virtual_slots_and_both_sq_flags(vsq):
    env = vsq
    names = ("VSQ-SNAPSHOT.all_slots", "VSQ-SNAPSHOT.flags", "VSQ-REUSE.wrap", "VSQ-CAPACITY.virtual")
    env.coverage.sample(names, env.last_tick)
    uids = []
    for lane in range(8):
        # 128 uops but only 64 flows: the real physical reservation need not
        # exceed one 64-entry window just to exercise all virtual snapshots.
        for slot in range(128):
            change = await env.cycle(env.requests({lane: (lane * 129 + slot + 1, slot % 2)}))
            item = change["accepted"][0]
            assert item["position"] % 128 == slot and item["lane"] == lane
            uids.append(item["uid"])
        await env.drain(RobPtr.encode(lane * 129 + 129), limit=48)
        await consume_prefix(env, lane * 64, (lane + 1) * 64)
    env.arm(names, uids)
    await env.idle(1)


async def test_same_rob_slot_uops_are_precommitted_one_snapshot_at_a_time(vsq):
    env = vsq
    change = await env.cycle(env.requests({lane: (10, 1 + lane % 2) for lane in range(8)}))
    env.arm(("VSQ-PRECOMMIT.multi_uop", "VSQ-PRECOMMIT.payload"))
    seen = []
    for _ in range(12):
        change = await env.cycle(rob_head=RobPtr.encode(10))
        seen.extend(item["end"] for item in change["precommitted"])
        assert env.observed[P.p_toPhysicalQueue_retiredPtr_value] == 0
    assert seen == [1, 3, 4, 6, 7, 9, 10, 12]
    await env.drain(RobPtr.encode(11))


async def test_rob_former_and_latter_have_distinct_precommit_and_retire_boundaries(vsq):
    env = vsq
    await env.cycle(env.requests({0: (RobPtr.encode(10, former=True), 1), 1: (RobPtr.encode(10, former=False), 2)}))
    env.arm(("VSQ-PRECOMMIT.slot", "VSQ-PRECOMMIT.payload"))
    await env.idle(4, rob_head=RobPtr.encode(10, former=True))
    assert env.observed[P.p_toPhysicalQueue_preCommitPtr_bits_value] == 1
    await env.idle(5, rob_head=RobPtr.encode(10, former=False))
    assert env.observed[P.p_toPhysicalQueue_preCommitPtr_bits_value] == 3
    assert env.observed[P.p_toPhysicalQueue_headRobIdx_isFormer] == 0
    assert env.observed[P.p_toPhysicalQueue_retiredPtr_value] == 1
    await env.drain(RobPtr.encode(11))


@pytest.mark.parametrize("flows", (1, 4, 16))
async def test_precommit_psq_consumption_releases_only_after_complete_interval(vsq, flows):
    env = vsq
    change = await env.cycle(env.requests({0: (10, flows)}))
    uid = change["accepted"][0]["uid"]
    env.arm(("VSQ-RELEASE.precommit",), [uid])
    await env.idle(4, rob_head=RobPtr.encode(10))
    # PSQ exposes the moved pointer before its registered consumption-valid.
    # Keep physical pointers monotone even in the valid-gating control.
    await env.cycle(physical_deq=SqPtr.encode(1 if flows == 1 else 0), consumed=False)
    assert not env.observed[P.p_empty] and not env.coverage.completed
    if flows == 1:
        env.arm("VSQ-RELEASE.pulse", [uid])
    if flows > 1:
        await env.cycle(physical_deq=SqPtr.encode(2), consumed=True)
        await env.idle(3)
        assert not env.observed[P.p_empty]
        env.arm("VSQ-RELEASE.partial", [uid])
    start = 2 if flows > 1 else 0
    for end in range(start + 2, flows + 2, 2):
        await env.cycle(physical_deq=SqPtr.encode(min(end, flows)), consumed=True)
    await env.idle(5)
    assert env.observed[P.p_empty] and uid in env.coverage.completed


async def test_one_psq_double_consumption_can_release_two_precommitted_uops(vsq):
    env = vsq
    await env.cycle(env.requests({0: (10, 1), 7: (10, 1)}))
    env.arm(("VSQ-RELEASE.two", "VSQ-RELEASE.precommit"))
    await env.idle(5, rob_head=RobPtr.encode(10))
    await env.cycle(physical_deq=SqPtr.encode(2), consumed=True)
    await env.idle(5)
    assert env.observed[P.p_empty] and len(env.coverage.completed) == 2


async def test_rob_retirement_and_psq_release_are_not_counted_twice(vsq):
    env = vsq
    await env.cycle(env.requests({0: (10, 1), 1: (10, 1)}))
    env.arm("VSQ-RACE.retire_release")
    await env.idle(4, rob_head=RobPtr.encode(10))
    await env.cycle(rob_head=RobPtr.encode(11))
    await env.cycle(physical_deq=SqPtr.encode(2), consumed=True)
    await env.idle(6)
    assert env.observed[P.p_toPhysicalQueue_retiredPtr_value] == 2 and env.observed[P.p_empty]


@pytest.mark.parametrize("kind", ("empty", "none", "all"))
async def test_empty_zero_and_all_cancel_recovery_use_defined_physical_end(vsq, kind):
    env = vsq
    if kind != "empty":
        await env.cycle(env.requests({0: (10, 2), 7: (11, 1)}))
    cutoff = 20 if kind == "none" else 0
    await env.cycle(redirect=Redirect(True, RobPtr.encode(cutoff), False))
    history = await env.idle(6)
    recoveries = [change["recovery"] for change in history if change["recovery"]]
    assert len(recoveries) == 1 and recoveries[0]["end"] == (3 if kind == "none" else 0)
    await env.cycle(env.requests({3: (21, 1)}))
    env.arm(("VSQ-RECOVER.empty" if kind == "empty" else f"VSQ-REDIRECT.{kind}", "VSQ-RECOVER.stall"))
    await env.drain(RobPtr.encode(22))


async def test_release_retired_heads_before_walk_and_hold_redirect_rob_snapshot(vsq):
    env = vsq
    await env.cycle(env.requests({lane: (10 + lane, 1) for lane in range(8)}))
    await env.cycle(env.requests({lane: (18 + lane, 1) for lane in range(4)}))
    await env.cycle(rob_head=RobPtr.encode(15))
    await env.cycle(redirect=Redirect(True, RobPtr.encode(18), False))
    changes = await env.idle(2, rob_head=RobPtr.encode(30))
    changes.extend(await env.idle(6, rob_head=RobPtr.encode(15)))
    recovery = [change["recovery"] for change in changes if change["recovery"]]
    assert len(recovery) == 1 and recovery[0]["end"] == 9
    assert env.observed[P.p_toPhysicalQueue_retiredPtr_value] == 5
    await env.cycle(env.requests({7: (22, 1)}))
    env.arm(("VSQ-WALK.release_first", "VSQ-WALK.head_snapshot", "VSQ-REDIRECT.partial"))
    await env.drain(RobPtr.encode(23))


async def test_redirect_release_walks_after_head_is_consumed(vsq):
    """A redirect first releases the retired head, then walks the suffix.

    The two phases are externally observable through the recovery stall and
    redirect pointer; the model does not inspect the DUT's internal state
    register or entry array.
    """
    env = vsq
    change = await env.cycle(env.requests({0: (10, 1), 1: (11, 1)}))
    survivor, younger = change["accepted"]
    env.arm("VSQ-WALK.release_first", [survivor["uid"]])

    # The public ROB head is sampled on an idle edge before it can retire the
    # current VSQ head; do not combine that setup edge with redirect.
    await env.cycle(rob_head=RobPtr.encode(11))
    await env.cycle(
        redirect=Redirect(True, RobPtr.encode(10), False),
        rob_head=RobPtr.encode(11),
    )
    assert env.observed[P.p_sqRecoverStall]
    changes = await env.idle(8, rob_head=RobPtr.encode(11))
    recoveries = [item["recovery"] for item in changes if item["recovery"]]
    assert len(recoveries) == 1 and recoveries[0]["end"] == 1
    assert younger["uid"] in env.coverage.canceled

    await env.cycle(env.requests({7: (20, 1)}))
    env.arm("VSQ-REUSE.cancel", [env.last_change["accepted"][0]["uid"]])
    await env.drain(RobPtr.encode(21))


@pytest.mark.parametrize("flush_self", (False, True))
async def test_redirect_age_respects_rob_wrap_and_former_latter(vsq, flush_self):
    env = vsq
    # Start an empty ROB observation near the wrap before dispatch arrives.
    await env.idle(3, rob_head=RobPtr.encode(158))
    await env.cycle(env.requests({0: (RobPtr.encode(158), 1), 1: (RobPtr.encode(159, former=True), 1),
                                 2: (RobPtr.encode(159, former=False), 1), 3: (RobPtr.encode(160), 1)}))
    await env.cycle(redirect=Redirect(True, RobPtr.encode(159, former=True), flush_self))
    changes = await env.idle(6)
    recovery = [change["recovery"] for change in changes if change["recovery"]]
    assert len(recovery) == 1 and recovery[0]["end"] == (1 if flush_self else 2)
    await env.cycle(env.requests({7: (161, 1)}))
    env.arm(("VSQ-REDIRECT.rob_flags", "VSQ-REDIRECT.slots"))
    await env.drain(RobPtr.encode(162))


async def test_adjacent_redirects_tighten_suffix_without_double_cancel(vsq):
    env = vsq
    await env.cycle(env.requests({lane: (10 + lane, 1) for lane in range(8)}))
    await env.cycle(redirect=Redirect(True, RobPtr.encode(15), False))
    changes = [await env.cycle(redirect=Redirect(True, RobPtr.encode(12), False))]
    changes.extend(await env.idle(8))
    recovery = [change["recovery"]["end"] for change in changes if change["recovery"]]
    assert recovery == [6, 3]
    await env.cycle(env.requests({7: (18, 1)}))
    env.arm("VSQ-RECOVER.adjacent")
    await env.drain(RobPtr.encode(19))


@pytest.mark.parametrize("during_recovery", (False, True))
async def test_reset_aborts_old_owners_and_new_uid_retires(vsq, during_recovery):
    env = vsq
    await env.cycle(env.requests({0: (10, 1), 7: (11, 4)}))
    old_uids = {item["uid"] for item in env.last_change["accepted"]}
    if during_recovery:
        await env.cycle(redirect=Redirect(True, RobPtr.encode(0), False))
        await env.idle(1)
        assert env.observed[P.p_sqRecoverStall]
    for _ in range(3):
        await env.cycle(reset=True)
    await env.cycle(env.requests({7: (20, 1)}))
    new_uid = env.last_change["accepted"][0]["uid"]
    assert new_uid > max(old_uids)
    env.arm("VSQ-RESET.recovery" if during_recovery else "VSQ-RESET.active", [new_uid])
    await env.drain(RobPtr.encode(21))


@pytest.mark.parametrize("lane", (0, 7))
async def test_same_cycle_dispatch_redirect_interface_boundary_has_no_ghost(vsq, lane):
    env = vsq
    await env.cycle(env.requests({0: (10, 1), 1: (11, 1)}))
    # UNIT-INTERFACE only: after checking the full real upstream path,
    # dispatch.valid=RegNext(do_enq && !redirect), and MemBlock redirects
    # have the SAME extra register. Normal producers suppress this overlap.
    # Retain the ordinary failure, but never call it a legal architecture bug.
    env.coverage.sample(("VSQ-RACE.dispatch_redirect",), env.last_tick)
    await env.cycle(env.requests({lane: (12, 1)}), redirect=Redirect(True, RobPtr.encode(10), False))
    await env.idle(7)
    await env.cycle(env.requests({7: (13, 1)}))
    env.arm("VSQ-RACE.dispatch_redirect")
    await env.drain(RobPtr.encode(14))


@pytest.mark.parametrize("lane", (0, 3, 7))
async def test_real_producer_dispatch_precedes_redirect_by_one_cycle(vsq, lane):
    env = vsq
    await env.cycle(env.requests({0: (10, 1), 1: (11, 1)}))
    await env.cycle(env.requests({lane: (12, 1)}))
    await env.cycle(redirect=Redirect(True, RobPtr.encode(10), False))
    changes = await env.idle(7)
    recoveries = [change["recovery"] for change in changes if change["recovery"]]
    assert len(recoveries) == 1 and recoveries[0]["end"] == 1
    await env.cycle(env.requests({7: (13, 1)}))
    env.arm(("VSQ-REDIRECT.partial", "VSQ-REUSE.cancel"))
    await env.drain(RobPtr.encode(14))


@pytest.mark.parametrize("seed", (55, 20261018))
async def test_seeded_dispatch_rob_and_psq_prefixes_fairly_drain(vsq, seed):
    env = vsq
    rng = random.Random(seed)
    env.coverage.sample(("VSQ-CONCURRENT.seeded",), env.last_tick)
    uids, physical_end, rob_base = [], 0, 1
    for _ in range(20):
        count = rng.randrange(1, 20)
        position, epoch_flows = 0, 0
        while position < count:
            lanes = sorted(rng.sample(range(8), rng.randrange(1, min(8, count - position) + 1)))
            mapping = {}
            for lane in lanes:
                flows = rng.randrange(4)
                mapping[lane] = (rob_base + position, flows)
                epoch_flows += flows
                position += 1
            change = await env.cycle(env.requests(mapping))
            uids.extend(item["uid"] for item in change["accepted"])
        await env.idle(rng.randrange(1, 5), rob_head=RobPtr.encode(rob_base))
        await env.drain(RobPtr.encode(rob_base + count), limit=40)
        await consume_prefix(env, physical_end, physical_end + epoch_flows)
        physical_end += epoch_flows
        rob_base += count + 1
    assert not env.model.outstanding and env.observed[P.p_empty]
    env.arm("VSQ-CONCURRENT.seeded", uids)
    await env.idle(1)
