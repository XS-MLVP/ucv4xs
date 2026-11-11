from dataclasses import asdict
import hashlib

from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.store_queue.model.store_payload import add_digest
from suites.memblock.lsq.testbenches.unalign.transactions import Request
from suites.memblock.lsq.testbenches.unalign.model.uq_page_pairs import BASES
from suites.memblock.lsq.testbenches.unalign.model.uq_page_pairs import save
from suites.memblock.lsq.testbenches.unalign.model.uq_page_pairs import second_pa


def check_packet(entry, sq, pa):
    assert entry is not None, (sq, pa)
    assert entry.paddr == pa and entry.sq == SqPtr.encode(sq), (entry, sq, pa)


async def test_two_pages_hold_full_third_waits_then_real_slot_reuse(unalign, tmp_path):
    env, profiles, stream, sequence = unalign, [], hashlib.sha256(), 0
    for profile, base in enumerate(BASES):
        owners = []
        for index in range(2):
            req = Request(True, SqPtr.encode(base + index), second_pa(profile, index))
            await env.cycle({index: req}, address_ready=req.sq)
            assert env.pre_response.accept_ready[index]
            owners.append(dict(uid=sequence + 1, slot=sequence % 2))
            sequence += 1
            check_packet(env.response.forward_entries[owners[-1]["slot"]], base + index, req.paddr)
        env.arm("UQ-PAGE.paired_lifetimes", owners)
        third_pa = (2 if profile % 2 == 0 else (1 << 36) - 3) << 12
        third = Request(True, SqPtr.encode(base + 2), third_pa)
        lane = profile % 2
        for _ in range(3):
            await env.cycle({lane: third}, address_ready=third.sq)
            assert not env.pre_response.accept_ready[lane]
            assert all(env.response.forward_entries[slot] is not None for slot in range(2))
            check_packet(env.response.to_deq, base, second_pa(profile, 0))
        await env.cycle({lane: third}, address_ready=third.sq, ready=True)
        assert not env.pre_response.accept_ready[lane]
        check_packet(env.pre_response.to_deq, base, second_pa(profile, 0))
        await env.cycle({lane: third}, address_ready=third.sq, ready=True)
        assert env.pre_response.accept_ready[lane]
        check_packet(env.pre_response.to_deq, base + 1, second_pa(profile, 1))
        last = dict(uid=sequence + 1, slot=sequence % 2)
        sequence += 1
        env.arm("UQ-PAGE.paired_lifetimes", [last])
        check_packet(env.response.forward_entries[last["slot"]], base + 2, third_pa)
        await env.cycle(ready=True)
        check_packet(env.pre_response.to_deq, base + 2, third_pa)
        await env.idle(2, ready=True)
        assert env.response.to_deq is None and env.response.forward_entries == (None, None)
        item = dict(profile=profile, pair_SQ=[base, base + 1], pair_PA=[second_pa(profile, j) for j in range(2)],
                    pair_public_slots=[owner["slot"] for owner in owners], third_SQ=base + 2, third_PA=third_pa,
                    third_slot=last["slot"], actual_page_completions=3, held_full_cycles=3)
        add_digest(stream, item); profiles.append(item)
    assert sequence == len(env.coverage.completed) == 24 and not env.coverage.canceled
    save(tmp_path / "uq-page-pairs-witness.json", "unalign_queue", profiles, stream, completed_page_uids=24,
         scope="public two-slot forward/head identity and page retention, blocked valid third producer until actual acceptance/consumption; no parent Store lifetime claimed at the leaf")
