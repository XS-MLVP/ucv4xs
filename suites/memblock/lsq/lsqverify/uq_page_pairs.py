"""External paired cross-page producers and public first-word byte oracle."""
from dataclasses import asdict, replace
import hashlib
import json

from lsqverify.psq.types import Address, Data, SecondPage
from lsqverify.raw.types import SqPtr
from lsqverify.store_payload import add_digest
from lsqverify.vlq.types import RobPtr

BASES = (0, 62, 64, 126, 128, 190, 192, 254)


def second_pa(profile, owner):
    assert profile in range(8) and owner in range(2)
    return (((1 << 36) - 1 - owner) if profile % 2 == 0 else owner) << 12


def record(profile, owner):
    position = BASES[profile] + owner
    va, pa = 0x400000 + position * 8192 + 4092, 0x8000000 + position * 8192 + 4092
    value = ((1 << 64) - 1, 0x0123456789ABCDEF, 0xFEDCBA9876543210, 0)[profile % 4]
    value ^= owner * 0x1020304050607080
    return va, pa, value


def check_first_word(pins, prefix, expected):
    _, _, value = expected
    checks = {prefix + "valid": 1}
    for flag in ("forwardInvalid", "matchInvalid", "addrInvalid_valid", "dataInvalid_valid"):
        checks[prefix + "bits_" + flag] = 0
    for byte in range(16):
        checks[prefix + f"bits_forwardMask_{byte}"] = int(byte >= 12)
        if byte >= 12:
            checks[prefix + f"bits_forwardData_{byte}"] = value >> (8 * (byte - 12)) & 255
    diff = {key: [pins[key], want] for key, want in checks.items() if pins[key] != want}
    assert not diff, ("cross-page-original-first-four-bytes", prefix, diff)


def save(path, dut, profiles, stream, **fields):
    report = dict(format="lsq-uq-page-pairs-witness-v1", dut=dut, profiles=profiles,
                  public_trace_SHA256=stream.hexdigest(), **fields)
    path.write_text(json.dumps(report, indent=2) + "\n")


async def parent_pairs(env, actor, dut, tmp_path):
    stream, profiles, main_uids = hashlib.sha256(), [], []
    for profile, base in enumerate(BASES):
        assert not actor.live and actor.head == actor.tail <= base
        fillers = []
        while actor.tail < base:
            item = actor.add()
            fillers.extend((item,) if dut == "physical_store_queue" else item.flows)
        if fillers:
            await actor.drain()
        assert actor.head == base
        owners = []
        for index in range(2):
            item = actor.add(page=True, size=3)
            uid = item if dut == "physical_store_queue" else item.flows[0]
            owner = actor.all[uid]
            va, pa, value = record(profile, index)
            assert owner.position == base + index and not owner.address_parts and not owner.data_sent
            owner.address = replace(owner.address, vaddr=va, paddr=pa)
            owner.data = replace(owner.data, data=value)
            owner.second_page = second_pa(profile, index)
            actor.emit("page_pair_before_issue", uid=uid, position=owner.position, vaddr=va, paddr=pa,
                       second_page=owner.second_page, data=value)
            owners.append(owner)
        if dut == "physical_store_queue":
            hold = dict(retired=SqPtr.encode(base), precommit_valid=False)
        else:
            older = actor.uops[actor.flow_uop[owners[0].uid]].rob_order - 1
            hold = dict(advance_rob=False, rob_head=RobPtr.encode(older, former=bool(older % 2)))
        hold["sbuffer_ready"] = (False, False)
        for _ in range(3):
            await actor.step(fair=True, issue=False, **hold)
        for index, owner in enumerate(owners):
            await actor.step(fair=True, issue=False,
                addresses=tuple(owner.address if lane == index else Address() for lane in range(2)),
                data=tuple(owner.data if lane == 1 - index else Data() for lane in range(2)), **hold)
        handshakes = []
        for index, owner in enumerate(owners):
            request = SecondPage(True, SqPtr.encode(owner.position), owner.second_page)
            for _ in range(30):
                await actor.step(fair=True, issue=False,
                    second_pages=tuple(request if lane == index else SecondPage() for lane in range(2)), **hold)
                if env.pre_observed[f"io_fromStoreUnit_unalignQueueReq_{index}_ready"]:
                    break
            else:
                raise AssertionError("real UQ did not accept matching original second page")
            # The actor's producer selector is disabled here. This external
            # ownership update is permitted only after the actual public fire.
            owner.page_sent = True
            (actor.page_reservations if dut == "physical_store_queue" else actor.pages).add(owner.uid)
            item = dict(position=owner.position, uid=owner.uid, lane=index, sq=asdict(request.sq), paddr=owner.second_page)
            handshakes.append(item)
            add_digest(stream, ["actual_page_fire", profile, item])
            tail = replace(owner.address, vaddr=owner.address.vaddr // 16 * 16 + 16,
                           paddr=owner.second_page, last=True)
            await actor.step(fair=True, issue=False,
                addresses=tuple(tail if lane == index else Address() for lane in range(2)), **hold)
            for _ in range(4):
                await actor.step(fair=True, issue=False, **hold)
        assert actor.head == base and all(owner.s2_done and owner.data_sent and owner.page_sent for owner in owners)
        assert all(not actor.parts[owner.uid] for owner in owners)
        await actor.drain()
        current = [owner.uid for owner in owners]
        assert set(current) <= actor.completed and all(actor.parts[uid] == {0, 1} for uid in current)
        assert actor.head == base + 2 and not actor.live
        for owner in owners:
            add_digest(stream, ["real_two_part_store_complete", owner.uid, owner.position, actor.finish_ticks[owner.uid]])
        profiles.append(dict(profile=profile, head_before=base, head_after=base + 2,
            fillers_completed=len(fillers), page_handshakes=handshakes,
            no_Sbuffer_consumption_before_permission=True, cross_page_store_completions=2, actual_Sbuffer_fragments=4))
        main_uids.extend(current)
    assert len(actor.completed) == 256 and len(set(main_uids)) == 16
    assert not actor.cancelled and not actor.aborted
    actor.checked(("PSQ-PAGE.paired_lifetimes" if dut == "physical_store_queue" else "SQ-PAGE.paired_lifetimes",), main_uids)
    save(tmp_path / "uq-page-pairs-witness.json", dut, profiles, stream,
         completed_store_uids=256, cross_page_store_uids=16, actual_Sbuffer_fragments=272,
         scope="actual STA/STD, public second-page fire, tail STA, original byte consumption and normal dequeue; no shared model/actor edits, reset or cancellation between profiles")
