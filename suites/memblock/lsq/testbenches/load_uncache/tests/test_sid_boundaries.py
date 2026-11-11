"""Necessary-condition controls and ordinary failing SID-retention regressions."""
import pytest


async def prepare_pair(env, sid, *, consume_old=False, separate_sid=False, new_error=False):
    a = env.request(nc=True, lq=11, rob=10, paddr=0x123456780000, tag=1)
    b = env.request(nc=True, lq=12, rob=11, paddr=0x123456781000, tag=2)
    data_a, data_b = 0x0123456789ABCDEF, 0xFEDCBA9876543210
    await env.enqueue({0: a})
    await env.take_bus(a, 0)
    await env.bind(0, sid)
    await env.respond(sid, data_a)
    await env.wait_wakeup(a)
    await env.idle(4)
    if consume_old:
        await env.consume(a, data_a, lane=0)
    await env.enqueue({1: b})
    await env.take_bus(b, 1)
    sid_b = (sid + 1) % 16 if separate_sid else sid
    await env.bind(1, sid_b)
    if not (consume_old or separate_sid):
        env.reach("LQU-ID.returned_sid_reuse")
    await env.respond(sid_b, data_b, error=new_error)
    await env.wait_wakeup(b)
    return a, b, data_a, data_b


@pytest.mark.parametrize("sid", (0, 3, 15))
async def test_old_data_held_while_new_same_sid_response_arrives(load_uncache, sid):
    env = load_uncache
    a, b, data_a, data_b = await prepare_pair(env, sid)
    await env.consume(a, data_a, lane=1)
    await env.consume(b, data_b, lane=2)
    env.prove("LQU-ID.returned_sid_reuse")


@pytest.mark.parametrize("sid", (0, 3, 15))
async def test_old_error_held_while_new_same_sid_error_arrives(load_uncache, sid):
    env = load_uncache
    a, b, data_a, data_b = await prepare_pair(env, sid, new_error=True)
    await env.consume(a, data_a, lane=1, error=False)
    await env.consume(b, data_b, lane=2, error=True)
    env.prove("LQU-ID.returned_sid_reuse")


@pytest.mark.parametrize("sid", (0, 3, 15))
@pytest.mark.parametrize("consume_old", (False, True))
async def test_controls_distinct_sid_or_old_consumed_do_not_corrupt(load_uncache, sid, consume_old):
    env = load_uncache
    a, b, data_a, data_b = await prepare_pair(env, sid, consume_old=consume_old, separate_sid=not consume_old, new_error=True)
    if not consume_old:
        await env.consume(a, data_a, lane=1)
    await env.consume(b, data_b, lane=2, error=True)
