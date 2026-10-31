"""Minimal public-interface checks for two GitHub-only Forward gaps.

These are deliberately independent of the existing ForwardModel.result
prediction: one uses the model only for its normal output contract, the other
checks a byte-origin/blocking property directly on the sampled public pins.
"""

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.forward.types import Translation
from suites.memblock.lsq.raw.types import SqPtr


@pytest.mark.parametrize("lane", range(3))
async def test_retired_wait_target_across_flag_wrap_must_not_wait(forward, lane):
    """#6714: a retired MDP target must not be re-classified as out of range."""
    env = forward
    # deq=131 -> upper=195; wait target 66 is exactly one physical window
    # older, but its flag/value makes isNotBefore(upper) true as well.
    await env.cycle(dequeue=SqPtr.encode(131), upper=SqPtr.encode(195))
    source = env.store(vaddr=0x10000)
    bank = env.bank({(131 % 64): source})
    query = env.query(sq=132, wait=True, wait_sq=SqPtr.encode(66))
    await env.request(query, source.paddr, lane=lane, stores=bank)


@pytest.mark.parametrize("lane", range(3))
async def test_multi_match_partial_forward_mask_must_block(forward, lane):
    """#6229/#6312: multi-match with an incomplete real forward mask must not
    look like a safe full forward.  The public response can either block the
    load (forwardInvalid/matchInvalid/addrInvalid/dataInvalid) or forward every
    byte; silently forwarding only the lower half is the bug."""
    env = forward
    older = env.store(vaddr=0x10000, size=4, data=0x11111111111111111111111111111111)
    younger = env.store(vaddr=0x10000, size=4, data=0x22222222222222222222222222222222,
                        mask=0x00FF)  # 16B span, but only the lower 8B are held
    bank = env.bank({0: older, 1: younger})
    query = env.query(vaddr=0x10000, sq=2, size=4)
    change = await env.cycle({lane: query}, stores=bank)
    uid = change["accepted"][0]["uid"]
    change = await env.cycle(translations={lane: Translation(older.paddr)})
    assert any(answer["uid"] == uid for answer in change["responses"])
    post = env.observed
    prefix = P.io(f"query_{lane}_s2Resp_")
    assert post[prefix + "valid"]
    mask = sum(bool(post[prefix + f"bits_forwardMask_{byte}"]) << byte for byte in range(16))
    blocked = any(post[prefix + field] for field in (
        "bits_forwardInvalid", "bits_matchInvalid", "bits_addrInvalid_valid", "bits_dataInvalid_valid"))
    assert blocked or mask == 0xFFFF, (
        "multi-match partial forward was accepted without blocking", lane, hex(mask), post)
