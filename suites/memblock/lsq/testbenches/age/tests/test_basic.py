"""Small first pass; no removal, multi-lane, high-index or reuse traffic yet."""


async def test_cold_empty_and_no_ready(age):
    for _ in range(4):
        assert await age.cycle() is None


async def test_single_lane_order_and_ready_subset(age):
    await age.insert_order((1, 3, 2))
    assert await age.cycle(ready=(1, 2, 3)) == 1
    assert await age.cycle(ready=(2, 3)) == 3
    assert await age.cycle(ready=(2,)) == 2
    assert await age.cycle() is None
