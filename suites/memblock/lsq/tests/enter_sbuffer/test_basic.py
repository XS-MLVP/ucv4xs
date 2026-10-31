from suites.memblock.lsq.legacy_pins import P

async def test_empty_ready_never_implies_consumption(enter_sbuffer):
    env = enter_sbuffer
    await env.idle(5, ready=(True, True))
    assert env.observed[P.p_empty]
    assert not any(env.observed[P.io(f"toSbuffer_req_{lane}_valid")] or env.observed[P.io(f"deqPtrMove_{lane}")] for lane in range(2))
    env.coverage.sample(("ESB-IDLE.empty_ready",), env.last_tick)
    env.coverage.sample(("ESB-IDLE.empty_ready",), env.last_tick, checked=True)


async def test_one_request_is_buffered_until_real_sbuffer_consumption(enter_sbuffer):
    env = enter_sbuffer
    await env.cycle(env.write())
    env.arm("ESB-HOLD.head")
    await env.idle(6)
    assert env.observed[P.p_toSbuffer_req_0_valid] and not env.observed[P.p_empty]
    assert env.observed[P.p_deqPtrMove_0] == 0
    await env.drain()
