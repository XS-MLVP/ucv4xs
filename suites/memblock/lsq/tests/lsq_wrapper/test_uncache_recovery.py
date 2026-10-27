"""Real Wrapper cancellation phases, external cleanup and capacity rollback."""
import pytest

from lsqverify.load_queue.types import Load
from lsqverify.vlq.types import QueuePtr
from .uncache_recovery import UncacheRecoveryOwners


async def full(trace, count=16):
    loads = [trace.make_load(pos) for pos in range(count)]
    await trace.dispatch(loads, with_store=True)
    await trace.enqueue(list(range(count)))
    return loads


@pytest.mark.parametrize("phase", ("holding_mmio", "buffered_nc", "waiting_response", "returned_data"))
async def test_full_16_uncache_cancel_each_public_phase_cleanup_then_same_slot_new_uids_complete(lsq, phase):
    trace = UncacheRecoveryOwners(lsq, kind="mmio_memory" if phase == "holding_mmio" else "nc")
    old = await full(trace)
    jobs = []
    if phase in ("waiting_response", "returned_data"):
        jobs = [await trace.accept() for _ in range(16)]
        assert {a["mid"] for a in jobs} == set(range(16))
    if phase == "returned_data":
        for attempt in jobs:
            await trace.respond(attempt, error=True, nderr=True)
        await trace.idle(6)
    assert bool(lsq.observed["io_uncache_req_valid"]) == (phase == "buffered_nc")
    if phase == "buffered_nc":
        buffered = {pin: lsq.observed[pin] for pin in ("io_uncache_req_bits_id", "io_uncache_req_bits_addr")}
    lsq.reach("LSQ-RECOVER.all", "LSQ-RECOVER.reuse")
    assert await trace.cancel(old[0].execution.uop.rob) == QueuePtr.encode(0)
    if phase == "buffered_nc":
        assert lsq.observed["io_uncache_req_valid"] and all(lsq.observed[pin] == value for pin, value in buffered.items())
        jobs = [await trace.accept(sid=7)]
    for attempt in jobs:
        if attempt["response"] is None:
            await trace.respond(attempt, error=True, nderr=True)
    await trace.discard_cancelled_returns()
    new = await trace.refill(lane=1)
    assert {a["mid"] for a in new} == set(range(16))
    await trace.finish()
    # All Load-side entries cancelled while the old Store survives. Do not
    # call this the complete both-branch LSQ-RECOVER.all acceptance yet.
    lsq.prove("LSQ-RECOVER.reuse")
    if phase == "buffered_nc":
        lsq.prove("LSQ-RECOVER.buffered_load", "LSQ-BUS.cancelled_return")
    if phase == "waiting_response":
        lsq.prove("LSQ-RECOVER.sent_load", "LSQ-BUS.cancelled_return")


@pytest.mark.parametrize("target_mid", range(16))
async def test_each_real_mid_wakeup_cancel_keeps_15_external_responses_then_full_refill(lsq, target_mid):
    trace = UncacheRecoveryOwners(lsq)
    old = await full(trace)
    jobs = [await trace.accept() for _ in range(16)]
    assert {attempt["mid"] for attempt in jobs} == set(range(16))
    target = next(attempt for attempt in jobs if attempt["mid"] == target_mid)
    await trace.respond(target, error=bool(target_mid & 1), nderr=bool(target_mid & 2))
    # Next actual edge is the shared redirect; no extra actor idle edge is
    # allowed to turn the targeted wakeup into the later output phase.
    assert await trace.cancel(old[0].execution.uop.rob) == QueuePtr.encode(0)
    for attempt in reversed(jobs):
        if attempt is not target:
            await trace.respond(attempt, error=True, nderr=True)
    await trace.discard_cancelled_returns()
    new = await trace.refill(lane=target_mid % 3)
    assert {attempt["mid"] for attempt in new} == set(range(16))
    await trace.finish()
    lsq.prove("LSQ-RECOVER.sent_load", "LSQ-RECOVER.reuse", "LSQ-BUS.cancelled_return")


@pytest.mark.parametrize("occupied", (14, 15, 16))
async def test_real_uncache_capacity_rollback_oldest_rejected_metadata_shared_flush_and_reuse(lsq, occupied):
    trace = UncacheRecoveryOwners(lsq)
    await full(trace, occupied)
    new = [trace.make_load(pos) for pos in range(occupied, occupied + 3)]
    await trace.dispatch(new)
    await trace.cycle(loads=tuple(reversed(new)))
    await trace.cycle()
    rejected = new[16 - occupied]
    u, p = rejected.execution.uop, "io_nack_rollback_0_"
    lsq.expect({p+"valid": 1, p+"bits_robIdx_flag": int(u.rob.flag), p+"bits_robIdx_value": u.rob.value,
                p+"bits_robIdx_isFormer": int(u.rob.former), p+"bits_ftqIdx_flag": int(u.ftq.flag),
                p+"bits_ftqIdx_value": u.ftq.value, p+"bits_ftqOffset": u.offset, p+"bits_isRVC": int(u.rvc),
                p+"bits_level": 1, p+"bits_debug_runahead_checkpoint_id": u.checkpoint},
               "full real Uncache pool rejects original oldest missing capacity, complete recovery metadata")
    assert await trace.cancel(u.rob) == QueuePtr.encode(16)
    # The accepted prefix includes any free slots from the triple batch. The
    # rejected suffix must not appear on the bus or borrow an old response.
    attempts = [await trace.transfer() for _ in range(16)]
    assert {a["position"] for a in attempts} == set(range(16))
    await trace.consume_visible(range(16), 2)
    await trace.idle(6)
    await trace.refill(occupied + 3 - 16, lane=0)
    await trace.finish()
    lsq.prove("LSQ-RECOVER.partial", "LSQ-RECOVER.reuse")
