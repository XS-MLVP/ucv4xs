"""First pass: intentionally no return traffic, to establish a measurable baseline."""


async def test_initial_pool_and_single_allocations(freelist):
    env = freelist
    got = []
    for _ in range(5):
        got.extend((await env.cycle(1)).allocated)
    assert got == list(range(5))
    assert env.model.owned == set(range(5))


async def test_batch_allocation_exhaustion_and_idle(freelist):
    env = freelist
    got = await env.exhaust()
    assert got == tuple(range(env.spec["size"]))
    assert len(set(got)) == env.spec["size"]
    await env.idle(4)


async def test_partial_batches_and_sparse_confirmation(freelist):
    env = freelist
    a = await env.cycle(2)
    b = await env.cycle(1, confirmation_mask=0b100)
    c = await env.cycle(3)
    assert a.allocated + b.allocated + c.allocated == tuple(range(6))
    await env.idle(3)
