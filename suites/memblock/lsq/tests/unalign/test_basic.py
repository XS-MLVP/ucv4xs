
from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.raw.types import SqPtr


async def test_empty_ready_has_no_head_or_forward(unalign):
    env = unalign
    await env.idle(5, ready=True)
    assert not env.observed[P.p_toDeqModule_valid]
    assert not any(env.observed[P.io(f"forwardValid_{slot}")] for slot in range(2))
    env.coverage.sample(("UQ-IDLE.empty",), env.last_tick)
    env.coverage.sample(("UQ-IDLE.empty",), env.last_tick, checked=True)


async def test_lane0_second_page_waits_for_consumer_and_clears_offset(unalign):
    env = unalign
    req = env.request()
    await env.enqueue(req)
    env.arm(("UQ-HOLD.stable", "UQ-PAGE.offset", "UQ-CAPACITY.no_flow"))
    assert not env.pre_observed[P.p_toDeqModule_valid]
    await env.idle(5)
    assert env.observed[P.p_toDeqModule_bits_paddr] == req.paddr & ~4095
    await env.drain()


async def test_lane1_requires_exact_address_ready_sq(unalign):
    env = unalign
    req = env.request(sq=11)
    await env.cycle({1: req}, address_ready=SqPtr.encode(12))
    assert not env.last_change["accepted"] and not env.observed[P.p_toDeqModule_valid]
    await env.enqueue(req, lane=1)
    env.arm("UQ-ADMIT.value")
    await env.drain()
