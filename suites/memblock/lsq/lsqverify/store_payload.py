"""Public-input pool stimulus and byte oracle; never reads reference internals."""
from dataclasses import replace
import hashlib
import json

from lsqverify.forward.types import Query, Translation
from lsqverify.psq.checks import read_ptr
from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import RobPtr


def payload(generation, slot):
    assert generation in range(4) and slot in range(64)
    va = ((1 << 50) - (1 << 20) if generation % 2 == 0 else 0x200000) + slot * 16
    pa = ((1 << 48) - (1 << 20) if generation % 2 == 0 else 0x1000000) + slot * 16
    pattern = int.from_bytes(bytes((slot * 19 + byte * 31) % 256 for byte in range(16)), "little")
    value = ((1 << 128) - 1, pattern, pattern ^ ((1 << 128) - 1), 0)[generation]
    return va, pa, value


def check_forward(pins, prefix, expected):
    va, pa, data = expected
    assert va % 4096 == pa % 4096
    assert pins[prefix + "valid"] == 1, (prefix, "missing S2")
    for suffix in ("forwardInvalid", "matchInvalid", "addrInvalid_valid", "dataInvalid_valid"):
        assert pins[prefix + "bits_" + suffix] == 0, (prefix, suffix)
    for byte in range(16):
        assert pins[prefix + f"bits_forwardMask_{byte}"] == 1, (prefix, byte, "mask")
        assert pins[prefix + f"bits_forwardData_{byte}"] == data >> (8 * byte) & 255, (prefix, byte, "payload")


def add_digest(stream, record):
    stream.update(json.dumps(record, separators=(",", ":")).encode() + b"\n")


async def parent_pool(env, actor, dut, tmp_path):
    """Real STA/STD, S2, three Forward lanes, ROB permission and actual drain."""
    assert dut in ("physical_store_queue", "store_queue")
    lifetimes, all_uids, stream = [], [], hashlib.sha256()
    for generation in range(4):
        start = actor.head
        assert start == generation * 64 and actor.tail == start and not actor.live
        owners = []
        for slot in range(64):
            item = actor.add(size=4)
            uid = item if dut == "physical_store_queue" else item.flows[0]
            owner = actor.all[uid]
            # Customize only the caller-owned, not-yet-issued producer record.
            # Existing actors/models and their failure traceback locations stay
            # unchanged; the allocation UID and ownership are not reassigned.
            va, pa, value = payload(generation, slot)
            assert va % 16 == pa % 16 == 0 and va % 4096 == pa % 4096
            assert not owner.address_parts and not owner.data_sent
            owner.address = replace(owner.address, vaddr=va, paddr=pa)
            owner.data = replace(owner.data, data=value)
            actor.emit("payload_before_issue", uid=uid, position=owner.position, vaddr=va, paddr=pa, data=value)
            owners.append(owner)
        # These controls are external protocol choices, not reference state.
        if dut == "physical_store_queue":
            hold = dict(retired=SqPtr.encode(start), precommit_valid=False)
        else:
            older_rob = actor.uops[actor.flow_uop[owners[0].uid]].rob_order - 1
            hold = dict(advance_rob=False, rob_head=RobPtr.encode(older_rob, former=bool(older_rob % 2)))
        hold["sbuffer_ready"] = (False, False)
        for _ in range(200):
            await actor.step(fair=True, **hold)
            assert actor.head == start and not ({owner.uid for owner in owners} & actor.completed)
            if all(owner.s2_done and owner.data_sent for owner in owners):
                break
        else:
            raise AssertionError("not every external pool owner reached real STA/S2/STD")
        assert {owner.position % 64 for owner in owners} == set(range(64))
        query_count = 0
        for slot, owner in enumerate(owners):
            expected = payload(generation, slot)
            q = Query(True, owner.address.vaddr, SqPtr.encode(start + 64), 4)
            await actor.step(fair=True, issue=False, queries=(q,) * 3, **hold)
            await actor.step(fair=True, issue=False, queries=(Query(),) * 3,
                             translations=(Translation(owner.address.paddr),) * 3, **hold)
            for lane in range(3):
                check_forward(env.observed, f"io_forward_{lane}_s2Resp_", expected)
                add_digest(stream, [generation, owner.uid, owner.position, lane, *expected])
                query_count += 1
            assert actor.head == start
        await actor.step(fair=True, issue=False, **hold)
        await actor.drain()
        uids = {owner.uid for owner in owners}
        assert uids <= actor.completed and all(actor.parts[uid] == {0} for uid in uids)
        assert actor.head == start + 64 and read_ptr(env.observed) == (start + 64) % 256
        if dut == "store_queue":
            assert env.observed["io_sqEmpty"]
        assert query_count == 192
        for owner in owners:
            add_digest(stream, ["consumed", generation, owner.uid, owner.position, actor.finish_ticks[owner.uid]])
        lifetimes.append(dict(generation=generation, head_before=start, head_after=actor.head,
                              public_slots=sorted(owner.position % 64 for owner in owners),
                              first_payload=payload(generation, 0), last_payload=payload(generation, 63),
                              written_owners=64, checked_three_lane_responses=query_count,
                              sbuffer_consumed_owners=64, normal_completions=64))
        all_uids.extend(sorted(uids))
    assert len(all_uids) == len(set(all_uids)) == len(actor.completed) == 256
    assert not actor.cancelled and not actor.aborted
    scenario = "PSQ-PAYLOAD.pool" if dut == "physical_store_queue" else "SQ-PAYLOAD.pool"
    actor.checked((scenario,), all_uids)
    witness = dict(format="lsq-store-payload-pool-witness-v1", dut=dut, lifetimes=lifetimes,
                   distinct_uids=256, checked_three_lane_responses=768, completed_owners=256,
                   sbuffer_consumed_owners=256, payload_and_consumption_SHA256=stream.hexdigest(),
                   scope="external UID/STA/STD history, real public S2 bytes and actual Sbuffer fire + dequeue; no hidden DUT/reference reads, no reset/cancel between lifetimes")
    (tmp_path / "store-payload-pool-witness.json").write_text(json.dumps(witness, indent=2) + "\n")
