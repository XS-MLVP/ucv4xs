"""Small semantic oracles, deliberately independent of the existing models."""

from dataclasses import replace

import pytest

from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.replay.env.codec import encode as replay_encode
from suites.memblock.lsq.testbenches.replay.env.ports import decode_observation
from suites.memblock.lsq.testbenches.replay.transactions import Cause
from suites.memblock.lsq.testbenches.replay.transactions import Enqueue
from suites.memblock.lsq.testbenches.replay.transactions import Inputs as ReplayInputs
from suites.memblock.lsq.testbenches.replay.transactions import Uop
from suites.memblock.lsq.testbenches.vlq.transactions import QueuePtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr


@pytest.mark.parametrize("review_dut", ["load_queue_replay"], indirect=True)
@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("target", (0, 1))
@pytest.mark.parametrize("bitmap", (False, True))
async def test_invalid_feedback_must_not_relax_a_live_strict_owner(review_dut, lane, target, bitmap):
    e = review_dut
    e.metadata = dict(issue="LRQ-STRICT-001", lane=lane, target=target, bitmap=bitmap,
        domain="Replay input valid-only noninterference, one immutable normal LD; no private slot selection")
    uop = Uop(rob=RobPtr.encode(10), lq=QueuePtr.encode(20), sq=SqPtr.encode(8), offset=1,
        operation=6, strict=True, load_wait=True, store_set_hit=True, wait_sq=SqPtr.encode(7))
    req = Enqueue(True, uop, vaddr=0x10000, mask=255, aligned_type=3, need_replay=True,
        causes=1 << Cause.ADDRESS_DEPENDENCE, address_sq=SqPtr.encode(7))
    base = ReplayInputs(address_bits=(1 << 7) if bitmap else 0, upper=SqPtr.encode(64))

    async def cycle(**changes):
        await e.step(replay_encode(replace(base, **changes)))

    await cycle(enqueues=(req, Enqueue(), Enqueue()))
    e.check("new original strict Load allocated", e.snapshot(decode_observation).replay_allocate, 1)
    e.event("strict_owner_input", uid=1, ROB=10, LQ=20, SQ=8, dependency_SQ=7, strict=1,
        PA_low12=0, VA=0x10000, mask=255, opcode=6, lastBeat_PA5=0)
    for _ in range(4):
        await cycle()
    e.check("strict owner initially blocked", [e.snapshot(decode_observation).replay[i].valid for i in range(3)], [0, 0, 0])
    dirty = replace(req, valid=False, replay_feedback=True, slot=target, need_replay=False, causes=0,
        uop=replace(req.uop, strict=False))
    await cycle(enqueues=tuple(dirty if i == lane else Enqueue() for i in range(3)))
    e.event("disabled_feedback_input", lane=lane, valid=0, schedIndex=target, isLoadReplay=1,
        no_address_wakeup=True, continuous_ready_pointer=0, address_ready_bit7=int(bitmap))
    early = []
    for _ in range(6):
        for bank in range(3):
            if e.snapshot(decode_observation).replay[bank].valid:
                early.append(dict(tick=e.tick, bank=bank, slot=e.snapshot(decode_observation).replay[bank].replay_queue_idx,
                    strict=e.snapshot(decode_observation).replay[bank].strict))
        await cycle()
    e.event("strict_blocked_window_end", early_valid_observations=early,
        original_owner_still_allocated=e.snapshot(decode_observation).replay_allocate)
    e.check("disabled feedback has no scheduling side effect", early, [], fatal=False)
    base = replace(base, address_ready=SqPtr.encode(8))
    await cycle()
    e.event("legal_dependency_release", address_ready_pointer=8)
    for _ in range(30):
        if any(e.snapshot(decode_observation).replay[i].valid for i in range(3)):
            break
        await cycle()
    banks = [i for i in range(3) if e.snapshot(decode_observation).replay[i].valid]
    e.check("original Load available after legal release", len(banks), 1)
    bank = banks[0]
    slot = e.snapshot(decode_observation).replay[bank].replay_queue_idx
    e.check("public output owner identity", [e.snapshot(decode_observation).replay[bank].rob_idx_value,
        e.snapshot(decode_observation).replay[bank].strict], [10, 1])
    await cycle(ready=tuple(i == bank for i in range(3)))
    e.check("real original Replay grant", e.snapshot(decode_observation, before=True).replay[bank].valid, 1)
    e.event("actual_Replay_grant_after_legal_release", uid=1, public_slot=slot, bank=bank)
    done = replace(req, replay_feedback=True, slot=slot, need_replay=False, causes=0)
    await cycle(enqueues=(done, Enqueue(), Enqueue()))
    e.event("same_public_slot_success_feedback", uid=1, slot=slot, need_rep=False)
    for _ in range(5):
        await cycle()
    e.check("original Replay owner actually freed", e.snapshot(decode_observation).replay_allocate, 0)
    e.finish()
