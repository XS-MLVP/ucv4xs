"""First native observations before line-gap-driven expansion."""


async def test_empty_and_unmatched_store(raw):
    await raw.idle(4)
    await raw.probe((raw.store(0x18000),), expect={0: None})
    await raw.idle(4)
    assert raw.observed.ready == (True, True, True) and not raw.observed.full


async def test_single_load_conflict_and_actual_metadata(raw):
    load = raw.request(2, 0x18000, tag=85)
    await raw.cycle({1: load})
    await raw.probe((raw.store(0x18000, tag=99),), expect={0: load})
    await raw.idle(4)


async def test_head_release_is_visible_to_later_store(raw):
    load = raw.request(2, 0x18000, tag=54)
    await raw.cycle({0: load})
    await raw.probe((raw.store(0x18000),), expect={0: load})
    await raw.advance_head(2)
    await raw.probe((raw.store(0x18000),), expect={0: None})
    await raw.settle_free()
    assert len(raw.model.free.available) == 56
