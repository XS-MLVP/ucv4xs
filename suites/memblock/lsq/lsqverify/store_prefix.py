"""External byte producers and public exclusive-prefix checks only."""
from dataclasses import replace
import hashlib
import json

from lsqverify.forward.types import Query, Translation
from lsqverify.psq.checks import check_word, read_ptr
from lsqverify.psq.types import Address, Attributes, Data
from lsqverify.raw.types import SqPtr
from lsqverify.store_payload import add_digest
from lsqverify.vlq.types import RobPtr
from lsqverify.vsq.types import Dispatch

WINDOWS = ((0, 63), (63, 127), (127, 191), (191, 254), (254, 256))


def producer(generation, position):
    start, end = WINDOWS[generation]
    assert start <= position < end
    index = 0 if position == end - 1 else position - start
    offset = (index + generation * 5) % 16
    va = 0x200000 + generation * 0x10000 + index * 32 + offset
    pa = 0xA000000 + generation * 0x10000 + index * 32 + offset
    value = (position * 37 + generation * 53 + 0x23) % 256
    assert va % 4096 == pa % 4096
    return va, pa, value


def check_byte(pins, prefix, expected):
    va, pa, value = expected
    assert va % 4096 == pa % 4096
    checks = {prefix + "valid": 1}
    for flag in ("forwardInvalid", "matchInvalid", "addrInvalid_valid", "dataInvalid_valid"):
        checks[prefix + "bits_" + flag] = 0
    for byte in range(16):
        checks[prefix + f"bits_forwardMask_{byte}"] = int(byte == va % 16)
    checks[prefix + f"bits_forwardData_{va % 16}"] = value
    diff = {key: [pins[key], target] for key, target in checks.items() if pins[key] != target}
    assert not diff, ("exclusive-prefix-byte", prefix, expected, diff)


def lifetime(generation, responses, **fields):
    start, end = WINDOWS[generation]
    a, b = producer(generation, start), producer(generation, end - 1)
    assert a[:2] == b[:2] and a[2] != b[2]
    return dict(generation=generation, head_before=start, head_after=end,
                public_slots=[position % 64 for position in range(start, end)],
                offsets=sorted({producer(generation, position)[0] % 16 for position in range(start, end)}),
                exclusive_upper_first=start + 1, exclusive_upper_last=end,
                alias_first_byte=a[2], alias_last_byte=b[2], alias_vaddr=a[0], alias_paddr=a[1],
                checked_forward_responses=responses, **fields)


def save_witness(path, dut, lives, stream, **fields):
    report = dict(format="lsq-store-prefix-byte-witness-v1", dut=dut, lifetimes=lives,
                  checked_forward_responses=sum(life["checked_forward_responses"] for life in lives),
                  payload_and_completion_SHA256=stream.hexdigest(), **fields)
    path.write_text(json.dumps(report, indent=2) + "\n")


async def consume_in_program_order(env, actor, dut, owners):
    """A repeated VA is not an identity; only actual ordered fires release UIDs.

    The ordinary generic actor's address-only lookup is not used for this
    directed consumer. Its producer records and all staged DUT/model checks
    remain untouched. The external ledger is updated only from real pins.
    """
    assert all(owner.s2_done and owner.data_sent for owner in owners)
    next_fire, quiet = 0, 0
    end = owners[-1].position + 1
    credit = "io_sqDeq_" if dut == "physical_store_queue" else "io_toLsqEnqCtrl_sqDeq_"
    for _ in range(300):
        controls = dict(addresses=(Address(), Address()), data=(Data(), Data()),
                        attributes=(Attributes(), Attributes()), queries=(Query(),) * 3,
                        translations=(Translation(),) * 3, sbuffer_ready=(True, True))
        if dut == "physical_store_queue":
            actor.retired = end
            controls.update(enqueue=SqPtr.encode(end), retired=SqPtr.encode(end), precommit_valid=False)
        else:
            controls.update(dispatch=(Dispatch(),) * 8, rob_head=actor.rob_pointer(True))
        await env.cycle(**controls)
        pre, post, tick = env.pre_observed, env.observed, env.last_tick
        for lane in range(2):
            p = f"io_writeToSbuffer_req_{lane}_"
            if not pre[p + "valid"]:
                continue
            assert next_fire < len(owners), "unowned extra Sbuffer consumption"
            owner = owners[next_fire]
            offset = owner.address.vaddr % 16
            assert not actor.parts[owner.uid]
            check_word(env, lane, owner.address.vaddr // 16 * 16, owner.address.paddr // 16 * 16,
                       1 << offset, owner.data.data << (8 * offset), before=True)
            actor.parts[owner.uid].add(0)
            actor.finish_ticks[owner.uid] = tick
            actor.emit("prefix_UID_sbuffer_fire", uid=owner.uid, position=owner.position, lane=lane, tick=tick)
            next_fire += 1
        delta = (read_ptr(post) - actor.head) % 256
        assert delta <= 2 and post[credit + "valid"] == int(bool(delta))
        if delta:
            assert post[credit + "bits"] == delta
        for position in range(actor.head, actor.head + delta):
            owner = actor.live[position]
            assert owner.uid not in actor.completed and actor.parts[owner.uid] == {0}
            assert actor.finish_ticks[owner.uid] + 2 == tick
            actor.completed.add(owner.uid)
            del actor.live[position]
            actor.emit("prefix_UID_normal_dequeue", uid=owner.uid, position=position, tick=tick)
        actor.head += delta
        quiet = quiet + 1 if actor.head == end and not actor.live else 0
        assert not pre["io_toDCache_req_valid"] and not pre["io_toUncacheBuffer_req_valid"]
        if quiet == 6:
            assert next_fire == len(owners)
            if dut == "store_queue":
                assert post["io_sqEmpty"]
            return
    raise AssertionError("ordered original UID consumer did not normally drain")


async def parent_windows(env, actor, dut, tmp_path):
    assert dut in ("physical_store_queue", "store_queue")
    lives, stream, uids = [], hashlib.sha256(), []
    for gen, (start, end) in enumerate(WINDOWS):
        assert actor.head == actor.tail == start and not actor.live
        owners = []
        for position in range(start, end):
            va, pa, value = producer(gen, position)
            item = actor.add(size=0, offset=va % 16)
            uid = item if dut == "physical_store_queue" else item.flows[0]
            owner = actor.all[uid]
            assert owner.position == position and not owner.address_parts and not owner.data_sent
            owner.address = replace(owner.address, vaddr=va, paddr=pa)
            owner.data = replace(owner.data, data=value)
            actor.emit("prefix_byte_before_issue", uid=uid, position=position, vaddr=va, paddr=pa, data=value)
            owners.append(owner)
        if dut == "physical_store_queue":
            hold = dict(retired=SqPtr.encode(start), precommit_valid=False)
        else:
            older = actor.uops[actor.flow_uop[owners[0].uid]].rob_order - 1
            hold = dict(advance_rob=False, rob_head=RobPtr.encode(older, former=bool(older % 2)))
        hold["sbuffer_ready"] = (False, False)
        for _ in range(200):
            await actor.step(fair=True, **hold)
            assert actor.head == start and not ({owner.uid for owner in owners} & actor.completed)
            if all(owner.s2_done and owner.data_sent for owner in owners):
                break
        else:
            raise AssertionError("all real prefix STA/STD did not arrive")
        responses = 0
        for owner in owners:
            expected = producer(gen, owner.position)
            q = Query(True, expected[0], SqPtr.encode(owner.position + 1), 0)
            await actor.step(fair=True, issue=False, queries=(q,) * 3, **hold)
            await actor.step(fair=True, issue=False, translations=(Translation(expected[1]),) * 3, **hold)
            for lane in range(3):
                check_byte(env.observed, f"io_forward_{lane}_s2Resp_", expected)
                add_digest(stream, [gen, owner.uid, owner.position, owner.position + 1, lane, *expected])
                responses += 1
            assert actor.head == start
        await actor.step(fair=True, issue=False, **hold)
        await consume_in_program_order(env, actor, dut, owners)
        current = [owner.uid for owner in owners]
        assert set(current) <= actor.completed and all(actor.parts[uid] == {0} for uid in current)
        assert actor.head == end and not actor.live
        if dut == "store_queue":
            assert env.observed["io_sqEmpty"]
        for owner in owners:
            add_digest(stream, ["real_consumed_and_dequeued", owner.uid, owner.position, actor.finish_ticks[owner.uid]])
        lives.append(lifetime(gen, responses, normal_store_completions=end - start,
                              sbuffer_consumed_owners=end - start, younger_alias_written_before_first_query=True))
        uids.extend(current)
    assert len(uids) == len(set(uids)) == len(actor.completed) == 256
    assert not actor.cancelled and not actor.aborted
    actor.checked(("PSQ-WINDOW.prefix_byte" if dut == "physical_store_queue" else "SQ-WINDOW.prefix_byte",), uids)
    save_witness(tmp_path / "store-prefix-byte-witness.json", dut, lives, stream,
                 completed_store_uids=256, scope="actual STA/STD before all queries, public prefix/byte checks, real Sbuffer consumption and normal reuse; no hidden/reference reads or between-window reset")
