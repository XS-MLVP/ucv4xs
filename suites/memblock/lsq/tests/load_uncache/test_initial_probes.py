"""Initial public-pin chains, explicitly not the complete parent UT/reference."""

from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P


async def test_empty_parent_is_quiet(load_uncache):
    env = load_uncache
    await env.idle(5)
    env.reach("LQU-IDLE.empty")
    names = (P.p_uncache_req_valid, P.p_ncWakeup_valid, P.p_mmioWakeup_valid, P.p_rollback_valid, P.p_exceptionInfo_valid,
             *(P.io(f"bypass_{lane}_s{stage}Resp_valid") for lane in range(3) for stage in (1, 2)))
    env.expect("empty.no-public-transaction", {name: env.observed[name] for name in names}, dict.fromkeys(names, 0))
    env.prove("LQU-IDLE.empty")


@pytest.mark.parametrize("nc", (False, True))
async def test_single_original_identity_data_and_exception(load_uncache, nc):
    env = load_uncache
    req = env.request(nc=nc, lq=131, tag=7)
    await env.enqueue({2: req})
    await env.take_bus(req, 0)
    await env.bind(0, 3)
    await env.respond(3, 0x0123456789ABCDEF, error=nc, nderr=not nc)
    await env.wait_wakeup(req)
    await env.consume(req, 0x0123456789ABCDEF, lane=2, error=nc, nderr=not nc)


async def test_legitimate_two_mid_merged_sid_fanout(load_uncache):
    env = load_uncache
    a = env.request(nc=True, lq=11, rob=10, paddr=0x123456780000, vaddr=0x40000, tag=1)
    b = env.request(nc=True, lq=12, rob=11, paddr=0x123456780002, vaddr=0x40002, tag=1)
    a = replace(a, entry=replace(a.entry, mask=0x0003))
    b = replace(b, entry=replace(b.entry, mask=0x000C))
    await env.enqueue({1: a})
    await env.take_bus(a, 0)
    await env.bind(0, 3)
    await env.enqueue({2: b})
    await env.take_bus(b, 1)
    await env.bind(1, 3)
    env.reach("LQU-ID.merge")
    await env.respond(3, 0x9876543210ABCDEF)
    await env.wait_wakeup(a)
    await env.wait_wakeup(b)
    await env.consume(b, 0x9876543210ABCDEF, lane=1)
    await env.consume(a, 0x9876543210ABCDEF, lane=0)
    env.prove("LQU-ID.merge")


async def test_sid_reused_after_response_preserves_old_unconsumed_data(load_uncache):
    env = load_uncache
    a = env.request(nc=True, lq=11, rob=10, paddr=0x123456780000, tag=1)
    b = env.request(nc=True, lq=12, rob=11, paddr=0x123456781000, tag=2)
    data_a, data_b = 0x0123456789ABCDEF, 0xFEDCBA9876543210
    await env.enqueue({0: a})
    await env.take_bus(a, 0)
    await env.bind(0, 3)
    await env.respond(3, data_a)
    await env.wait_wakeup(a)  # keep A data resident; no bypass consumes it yet
    await env.enqueue({1: b})
    await env.take_bus(b, 1)
    await env.bind(1, 3)  # legal reuse: external Uncache freed SID3 on A response
    env.reach("LQU-ID.returned_sid_reuse")
    await env.respond(3, data_b)
    await env.wait_wakeup(b)
    await env.consume(a, data_a, lane=0)
    await env.consume(b, data_b, lane=1)
    env.prove("LQU-ID.returned_sid_reuse")
