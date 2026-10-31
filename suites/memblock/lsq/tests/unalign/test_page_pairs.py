
from dataclasses import asdict
import hashlib

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.psq.checks import ptr_values
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.store_payload import add_digest
from suites.memblock.lsq.unalign.types import Request
from suites.memblock.lsq.uq_page_pairs import BASES, save, second_pa


def check_packet(pins, prefix, sq, pa):
    want = {prefix + "paddr": pa, **ptr_values(prefix + "sqIdx_", sq)}
    assert all(pins[key] == value for key, value in want.items()), (prefix, sq, pa, want)


async def test_two_pages_hold_full_third_waits_then_real_slot_reuse(unalign, tmp_path):
    env, profiles, stream, sequence = unalign, [], hashlib.sha256(), 0
    for profile, base in enumerate(BASES):
        owners = []
        for index in range(2):
            req = Request(True, SqPtr.encode(base + index), second_pa(profile, index))
            await env.cycle({index: req}, address_ready=req.sq)
            assert env.pre_observed[P.io(f"fromStaS1_{index}_ready")]
            owners.append(dict(uid=sequence + 1, slot=sequence % 2))
            sequence += 1
            check_packet(env.observed, P.io(f"forwardEntries_{owners[-1]['slot']}_"), base + index, req.paddr)
        env.arm("UQ-PAGE.paired_lifetimes", owners)
        third_pa = (2 if profile % 2 == 0 else (1 << 36) - 3) << 12
        third = Request(True, SqPtr.encode(base + 2), third_pa)
        lane = profile % 2
        for _ in range(3):
            await env.cycle({lane: third}, address_ready=third.sq)
            assert not env.pre_observed[P.io(f"fromStaS1_{lane}_ready")]
            assert all(env.observed[P.io(f"forwardValid_{slot}")] for slot in range(2))
            check_packet(env.observed, P.p_toDeqModule_bits_, base, second_pa(profile, 0))
        await env.cycle({lane: third}, address_ready=third.sq, ready=True)
        assert not env.pre_observed[P.io(f"fromStaS1_{lane}_ready")]
        check_packet(env.pre_observed, P.p_toDeqModule_bits_, base, second_pa(profile, 0))
        await env.cycle({lane: third}, address_ready=third.sq, ready=True)
        assert env.pre_observed[P.io(f"fromStaS1_{lane}_ready")]
        check_packet(env.pre_observed, P.p_toDeqModule_bits_, base + 1, second_pa(profile, 1))
        last = dict(uid=sequence + 1, slot=sequence % 2)
        sequence += 1
        env.arm("UQ-PAGE.paired_lifetimes", [last])
        check_packet(env.observed, P.io(f"forwardEntries_{last['slot']}_"), base + 2, third_pa)
        await env.cycle(ready=True)
        check_packet(env.pre_observed, P.p_toDeqModule_bits_, base + 2, third_pa)
        await env.idle(2, ready=True)
        assert not env.observed[P.p_toDeqModule_valid] and not any(env.observed[P.io(f"forwardValid_{slot}")] for slot in range(2))
        item = dict(profile=profile, pair_SQ=[base, base + 1], pair_PA=[second_pa(profile, j) for j in range(2)],
                    pair_public_slots=[owner["slot"] for owner in owners], third_SQ=base + 2, third_PA=third_pa,
                    third_slot=last["slot"], actual_page_completions=3, held_full_cycles=3)
        add_digest(stream, item); profiles.append(item)
    assert sequence == len(env.coverage.completed) == 24 and not env.coverage.canceled
    save(tmp_path / "uq-page-pairs-witness.json", "unalign_queue", profiles, stream, completed_page_uids=24,
         scope="public two-slot forward/head identity and page retention, blocked valid third producer until actual acceptance/consumption; no parent Store lifetime claimed at the leaf")
