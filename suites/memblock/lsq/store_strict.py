"""Public strict/precise byte checks and external-owner parent stimulus only."""
from dataclasses import asdict, replace
import hashlib
import json

from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.psq.checks import read_ptr
from suites.memblock.lsq.psq.types import Address, Data
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.store_payload import add_digest, payload
from suites.memblock.lsq.vlq.types import RobPtr


def record(generation, slot):
    va, pa, value = payload(generation, slot)
    return va, pa, value & ((1 << 64) - 1)


def check_response(pins, lane, expected, dependency, *, blocked):
    """An invalid dependency payload is never compared or called a success."""
    p = f"io_forward_{lane}_s2Resp_"
    values = {p + "valid": 1, p + "bits_addrInvalid_valid": int(blocked)}
    if blocked:
        ptr = SqPtr.encode(dependency)
        values.update({p + "bits_addrInvalid_bits_first_flag": int(ptr.first),
                       p + "bits_addrInvalid_bits_second_flag": int(ptr.second),
                       p + "bits_addrInvalid_bits_value": ptr.value})
    else:
        for suffix in ("forwardInvalid", "matchInvalid", "dataInvalid_valid"):
            values[p + "bits_" + suffix] = 0
        for byte in range(16):
            values[p + f"bits_forwardMask_{byte}"] = int(byte < 8)
            if byte < 8:
                values[p + f"bits_forwardData_{byte}"] = expected[2] >> (8 * byte) & 255
    diff = {key: [pins[key], value] for key, value in values.items() if pins[key] != value}
    assert not diff, ("store-strict-public-response", lane, dependency, blocked, diff)
    return {key: pins[key] for key in values}


async def parent_lifetimes(env, actor, dut, tmp_path):
    assert dut in ("physical_store_queue", "store_queue")
    lives, stream, all_uids = [], hashlib.sha256(), []
    for generation in range(4):
        start = generation * 64
        assert actor.head == actor.tail == start and not actor.live
        owners = []
        for slot in range(64):
            item = actor.add(size=3)
            uid = item if dut == "physical_store_queue" else item.flows[0]
            owner = actor.all[uid]
            va, pa, value = record(generation, slot)
            owner.address = replace(owner.address, vaddr=va, paddr=pa)
            owner.data = replace(owner.data, data=value)
            actor.emit("strict_payload_before_issue", uid=uid, position=owner.position, vaddr=va, paddr=pa, data=value)
            owners.append(owner)
        if dut == "physical_store_queue":
            hold = dict(retired=SqPtr.encode(start), precommit_valid=False)
        else:
            older_rob = actor.uops[actor.flow_uop[owners[0].uid]].rob_order - 1
            hold = dict(advance_rob=False, rob_head=RobPtr.encode(older_rob, former=bool(older_rob % 2)))
        hold["sbuffer_ready"] = (False, False)
        for _ in range(8):
            await actor.step(fair=True, issue=False, **hold)
        for slot in range(0, 64, 2):
            addresses = (owners[slot].address, owners[slot + 1].address if slot + 1 < 63 else Address())
            await actor.step(fair=True, issue=False, addresses=addresses,
                             data=(owners[slot].data, owners[slot + 1].data), **hold)
        for _ in range(6):
            await actor.step(fair=True, issue=False, **hold)
        assert all(owner.data_sent for owner in owners)
        assert all(owner.s2_done for owner in owners[:63]) and not owners[63].address_parts
        assert read_ptr(env.observed, "io_toLoadQueue_stAddrReadySqPtr_") == (start + 63) % 256
        assert not env.observed["io_toLoadQueue_stAddrReadyVec_63"]
        assert actor.head == start
        expected = record(generation, 0)
        responses = dict(strict_blocked=0, precise_unblocked=0, strict_after_STA_unblocked=0)

        async def query(strict, label, blocked):
            q = Query(True, expected[0], SqPtr.encode(start + 64), 3, wait=True,
                      strict=strict, wait_sq=SqPtr.encode(start))
            await actor.step(fair=True, issue=False, queries=(q,) * 3, **hold)
            await actor.step(fair=True, issue=False, translations=(Translation(expected[1]),) * 3, **hold)
            for lane in range(3):
                observed = check_response(env.observed, lane, expected, start + 63, blocked=blocked)
                add_digest(stream, [generation, label, lane, observed])
                responses[label] += 1
            assert actor.head == start

        await query(True, "strict_blocked", True)
        await query(False, "precise_unblocked", False)
        lane = generation % 2
        await actor.step(fair=True, issue=False,
                         addresses=tuple(owners[63].address if source == lane else Address() for source in range(2)), **hold)
        for _ in range(6):
            await actor.step(fair=True, issue=False, **hold)
        assert owners[63].s2_done
        assert read_ptr(env.observed, "io_toLoadQueue_stAddrReadySqPtr_") == (start + 64) % 256
        assert all(env.observed[f"io_toLoadQueue_stAddrReadyVec_{slot}"] for slot in range(64))
        await query(True, "strict_after_STA_unblocked", False)
        await actor.step(fair=True, issue=False, **hold)
        assert actor.head == start
        await actor.drain()
        uids = [owner.uid for owner in owners]
        assert set(uids) <= actor.completed and all(actor.parts[uid] == {0} for uid in uids)
        assert actor.head == start + 64 and not actor.live
        if dut == "store_queue":
            assert env.observed["io_sqEmpty"]
        for owner in owners:
            add_digest(stream, ["completed", generation, owner.uid, owner.position, actor.finish_ticks[owner.uid]])
        lives.append(dict(generation=generation, head_before=start, head_after=actor.head,
                          dependency=asdict(SqPtr.encode(start + 63)), public_slots=list(range(64)),
                          responses=responses, hole_STA_lane=lane, written_owners=64,
                          sbuffer_consumed_owners=64, normal_completions=64))
        all_uids.extend(uids)
    assert len(all_uids) == len(set(all_uids)) == len(actor.completed) == 256
    assert not actor.cancelled and not actor.aborted
    scenario = "PSQ-STRICT.lifecycle" if dut == "physical_store_queue" else "SQ-STRICT.lifecycle"
    actor.checked((scenario,), all_uids)
    witness = dict(format="lsq-store-strict-lifetimes-witness-v1", dut=dut, lifetimes=lives,
                   completed_store_uids=256, checked_forward_responses=36, payload_and_completion_SHA256=stream.hexdigest(),
                   scope="four normal reused generations; public real STA/STD, strict/precise responses, Sbuffer fires and deq; no hidden/reference state reads or between-generation reset")
    (tmp_path / "store-strict-lifetimes-witness.json").write_text(json.dumps(witness, indent=2) + "\n")
