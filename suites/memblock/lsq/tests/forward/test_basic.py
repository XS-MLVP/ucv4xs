import pytest


async def test_empty_queries_are_quiet_without_a_reset_port(forward):
    env = forward
    await env.idle(5)
    assert not any(env.observed[f"io_query_{lane}_s2Resp_valid"] for lane in range(3))
    env.coverage.sample(("FWD-IDLE.quiet",), env.last_tick)
    env.coverage.sample(("FWD-IDLE.quiet",), env.last_tick, checked=True)


@pytest.mark.parametrize("lane", range(3))
async def test_single_older_store_forwards_original_bytes(forward, lane):
    env = forward
    store = env.store()
    await env.request(env.query(), store.paddr, lane=lane, stores=env.bank({0: store}),
                      scenes=("FWD-SELECT.single", "FWD-VAPA.agree", "FWD-AGE.old_only"))


@pytest.mark.parametrize("lane", range(3))
async def test_selected_store_without_data_reports_dependency_not_old_value(forward, lane):
    env = forward
    store = env.store(ready=False)
    await env.request(env.query(), store.paddr, lane=lane, stores=env.bank({0: store}), scenes=("FWD-WAIT.data", "FWD-WAIT.identity"))


@pytest.mark.parametrize("lane", range(3))
async def test_historical_va1_va2_same_pa_alias_requires_replay(forward, lane):
    env = forward
    older = env.store(vaddr=0x10000, data=0x1111111111111111)
    younger = env.store(vaddr=0x20000, data=0x2222222222222222)
    await env.request(env.query(sq=2), older.paddr, lane=lane, stores=env.bank({0: older, 1: younger}),
                      scenes=("FWD-VAPA.alias", "FWD-REG.alias_6693"))


@pytest.mark.parametrize("lane", range(3))
async def test_cross_word_physical_alias_never_accepts_older_word_value(forward, lane):
    env = forward
    # Younger VA2+12 spans PA offsets12..19. The load of PA16..19 through
    # VA1+16 must not safely accept the older store at VA1+16.
    older = env.store(vaddr=0x10010, size=2, data=0x11111111)
    younger = env.store(vaddr=0x2000C, size=3, data=0x2222222222222222)
    await env.request(env.query(vaddr=0x10010, sq=2, size=2), older.paddr, lane=lane,
                      stores=env.bank({0: older, 1: younger}), scenes=("FWD-VAPA.alias_cross_word",))
