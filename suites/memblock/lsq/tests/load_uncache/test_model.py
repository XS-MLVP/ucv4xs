"""First cycles checked against the complete independent parent reference."""
import pytest


@pytest.mark.parametrize("nc", (False, True))
async def test_reference_full_original_transaction(load_uncache, nc):
    env = load_uncache
    request = env.request(nc=nc, lq=139, tag=7)
    await env.enqueue({2: request})
    await env.take_bus(request, 0)
    await env.bind(0, 3)
    await env.respond(3, 0x0123456789ABCDEF, error=nc, nderr=not nc)
    await env.wait_wakeup(request)
    await env.consume(request, 0x0123456789ABCDEF, lane=2, error=nc, nderr=not nc)
