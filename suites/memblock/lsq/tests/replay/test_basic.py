"""First native cycles: independently checked ownership, dispatch and feedback."""

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.replay.types import Cause, LqWakeup, TlbHint


async def test_empty_has_no_hidden_owner_or_replay(replay):
    await replay.idle(5)
    assert not replay.observed[P.p_replayAllocate] and not replay.observed[P.p_lqFull]
    assert not any(replay.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    replay.coverage.sample(("LRQ-IDLE.empty",), replay.last_tick)
    replay.coverage.sample(("LRQ-IDLE.empty",), replay.last_tick, checked=True)


async def test_direct_bank_conflict_replays_but_waits_for_feedback(replay):
    req = replay.request()
    await replay.cycle({2: req})
    uid = replay.uid(req)
    slot, fired_uid = await replay.issue()
    assert fired_uid == uid and slot == 0
    await replay.idle(5)
    assert replay.observed[P.p_replayAllocate] and not replay.model.pool.expected().empty
    assert not any(replay.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    await replay.complete(slot, lane=1)
    assert not replay.observed[P.p_replayAllocate]


async def test_tlb_waits_for_matching_delayed_hint(replay):
    req = replay.request(Cause.TLB_MISS)
    await replay.cycle({1: req})
    uid = replay.uid(req)
    await replay.idle(6, slow_tlb=TlbHint(True, req.tlb_id ^ 1))
    assert not any(replay.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    await replay.cycle(slow_tlb=TlbHint(True, req.tlb_id))
    replay.arm(("LRQ-TLB.slow", "LRQ-TLB.mismatch"), [uid])
    await replay.complete()


async def test_uncache_waits_for_original_lq_wakeup(replay):
    req = replay.request(Cause.UNCACHE, nc=True)
    await replay.cycle({0: req})
    uid = replay.uid(req)
    await replay.idle(5)
    assert not any(replay.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    await replay.cycle(nc=LqWakeup(True, req.uop.lq))
    replay.arm("LRQ-UNCACHE.nc", [uid])
    await replay.complete()
