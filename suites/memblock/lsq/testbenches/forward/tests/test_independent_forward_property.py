"""ForwardModule property probes: no predictor may veto the observation.

The fixture uses the ordinary public driver but replaces the pin-predicting
model with one that only tracks accepted transactions.  Assertions come from
``suites.memblock.lsq.testbenches.forward.checker``, which reads the original producer ledger
and never the RTL's span/decision fields.
"""

import pytest

from suites.memblock.lsq.testbenches.forward.checker import forward_byte_violations
from suites.memblock.lsq.testbenches.forward.transactions import Translation
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr


async def _respond(env, query, paddr, lane, stores):
    await env.cycle({lane: query}, stores=stores)
    await env.cycle(translations={lane: Translation(paddr)})
    return env.response.responses[lane]


@pytest.mark.parametrize("lane", range(3))
async def test_partial_store_coverage_must_block_or_forward_every_produced_byte(forward_property, lane):
    env = forward_property
    older = env.store(vaddr=0x10000, size=4, data=0x11111111111111111111111111111111)
    # 16B span, but only the lower 8 bytes are actually written.
    younger = env.store(vaddr=0x10000, size=4, data=0x22222222222222222222222222222222, mask=0x00FF)
    stores = env.bank({0: older, 1: younger})
    query = env.query(vaddr=0x10000, sq=2, size=4)
    post = await _respond(env, query, older.paddr, lane, stores)
    assert post.valid
    load = type("LoadView", (), {"vaddr": query.vaddr, "paddr": older.paddr, "mask": 0xFFFF})()
    violations = forward_byte_violations(load, [(0, older), (1, younger)], post)
    assert violations == [], ("accepted a response that loses produced bytes", lane, violations)


@pytest.mark.parametrize("lane", range(3))
async def test_fully_covered_bytes_are_a_clean_control(forward_property, lane):
    env = forward_property
    older = env.store(vaddr=0x10000, size=4, data=0x33333333333333333333333333333333)
    stores = env.bank({0: older})
    query = env.query(vaddr=0x10000, sq=1, size=4)
    post = await _respond(env, query, older.paddr, lane, stores)
    load = type("LoadView", (), {"vaddr": query.vaddr, "paddr": older.paddr, "mask": 0xFFFF})()
    assert forward_byte_violations(load, [(0, older)], post) == []
    # Sensitivity check: the oracle must reject the same clean trace when one
    # produced byte is silently dropped and the response is not blocked.
    mutant = type(post)(**{**post.__dict__, "forward_mask": post.forward_mask & ~(1 << 8)})
    assert forward_byte_violations(load, [(0, older)], mutant), (
        "oracle accepted a trace with a dropped produced byte")


async def test_retired_wait_target_is_not_an_address_stall(forward_property):
    """A retired MDP target must not keep addrInvalid asserted (#6714)."""
    env = forward_property
    await env.cycle(dequeue=SqPtr.encode(131), upper=SqPtr.encode(195))
    source = env.store(vaddr=0x10000)
    stores = env.bank({131 % 64: source})
    query = env.query(sq=132, wait=True, wait_sq=SqPtr.encode(66))
    post = await _respond(env, query, source.paddr, 0, stores)
    assert post.addr_invalid == 0, "retired wait target kept the load waiting"
