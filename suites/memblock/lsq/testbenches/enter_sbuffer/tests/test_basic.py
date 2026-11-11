async def test_empty_ready_never_implies_consumption(enter_sbuffer):
    env = enter_sbuffer
    await env.idle(5, ready=(True, True))
    assert env.response.empty
    assert env.response.sbuffer_word_0 is None and env.response.sbuffer_word_1 is None
    assert env.response.deq_pointer_moves == (0, 0)
    env.coverage.sample(("ESB-IDLE.empty_ready",), env.last_tick)
    env.coverage.sample(("ESB-IDLE.empty_ready",), env.last_tick, checked=True)


async def test_one_request_is_buffered_until_real_sbuffer_consumption(enter_sbuffer):
    env = enter_sbuffer
    await env.cycle(env.write())
    env.arm("ESB-HOLD.head")
    await env.idle(6)
    assert env.response.sbuffer_word_0 is not None and not env.response.empty
    assert env.response.deq_pointer_moves[0] == 0
    await env.drain()
