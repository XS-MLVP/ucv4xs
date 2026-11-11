"""InstrUncache top-level directed and randomized contract tests."""

from __future__ import annotations

from dataclasses import replace
import os
import random

import pytest

from suites.frontend.instr_uncache.testbenches.instr_uncache.checker import check_acquire
from suites.frontend.instr_uncache.testbenches.instr_uncache.checker import check_no_response
from suites.frontend.instr_uncache.testbenches.instr_uncache.checker import check_request_accepted
from suites.frontend.instr_uncache.testbenches.instr_uncache.checker import check_response
from suites.frontend.instr_uncache.testbenches.instr_uncache.checker import check_response_loss_persists
from suites.frontend.instr_uncache.testbenches.instr_uncache.checker import check_single_outstanding
from suites.frontend.instr_uncache.testbenches.instr_uncache.checker import check_source_filter
from suites.frontend.instr_uncache.testbenches.instr_uncache.checker import check_wfi
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import IDLE
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import REFILL_REQ
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import REFILL_RESP
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import SEND_RESP
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import aligned_bus_address
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import fetch_window
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import refill_needs_resend
from suites.frontend.instr_uncache.testbenches.instr_uncache.model import Inputs

BASE = 0x3A00_0000
BEAT = 0x1122_3344_5566_7788
NON_RVC_HIGH = 0xCAFF_0000_0000_0000
SECOND_BEAT = 0xDEF3_5678_9ABC_1234


def expected_resend_data(first: int, second: int) -> int:
    return (((second & 0xFFFF) << 16) | ((first >> 48) & 0xFFFF)) & 0xFFFF_FFFF


def legal_random_address(rng: random.Random) -> int:
    choice = rng.randrange(3)
    if choice == 0:
        return (rng.randrange(0, 1 << 40) * 2) & ~1
    if choice == 1:
        return BASE + ((rng.randrange(0, 0x1000)) & ~1)
    return ((rng.randrange(0, 1 << 30)) << 12) | 0xFFE


@pytest.mark.feature("INC-TOP-001")
async def test_top_request_stall_acquire_and_complete(instr_uncache_agent):
    agent = instr_uncache_agent
    addr = BASE + 6
    accepted = await agent.request(addr, mem_back_mm=0, mem_page_nc=1)
    check_request_accepted(accepted)
    assert agent.state == REFILL_REQ

    stalled = await agent.acquire(ready=0)
    assert stalled.before.a_valid == 1
    assert stalled.events.acquire_fire == 0
    assert stalled.state_after == REFILL_REQ
    issued = await agent.acquire(ready=1)
    check_acquire(issued, aligned_bus_address(addr), mm=0, nc=1)
    assert issued.state_after == REFILL_RESP

    await agent.grant(BEAT)
    response = await agent.idle()
    check_response(response, data=fetch_window(addr, BEAT), corrupt=0, denied=0,
                   need_resend=0)
    assert response.state_after == IDLE


@pytest.mark.feature("INC-TOP-004")
@pytest.mark.parametrize("selector", [0, 1, 2, 3])
async def test_top_address_window_and_user_attributes(instr_uncache_agent, selector):
    agent = instr_uncache_agent
    addr = BASE + selector * 2
    await agent.request(addr, mem_back_mm=selector & 1, mem_page_nc=(selector >> 1) & 1)
    acquire = await agent.acquire()
    check_acquire(acquire, aligned_bus_address(addr), mm=selector & 1,
                  nc=(selector >> 1) & 1)
    await agent.grant(BEAT)
    response = await agent.idle()
    check_response(response, data=fetch_window(addr, BEAT), corrupt=0, denied=0,
                   need_resend=0)


@pytest.mark.feature("INC-TOP-004")
async def test_top_high_legal_address_toggles_address_bit_42(instr_uncache_agent):
    agent = instr_uncache_agent
    addr = 0x7FF_FFFF_F000
    await agent.request(addr, mem_back_mm=1, mem_page_nc=0)
    acquire = await agent.acquire()
    check_acquire(acquire, aligned_bus_address(addr), mm=1, nc=0)
    await agent.grant(BEAT)
    response = await agent.idle()
    check_response(response, data=fetch_window(addr, BEAT), corrupt=0, denied=0,
                   need_resend=0)


@pytest.mark.feature("INC-TOP-004")
async def test_top_cross_bus_resend_uses_real_entry_and_arbiter(instr_uncache_agent):
    agent = instr_uncache_agent
    addr = BASE + 6
    assert refill_needs_resend(addr, NON_RVC_HIGH, corrupt=0, resending=0)
    await agent.request(addr)
    await agent.acquire()
    first = await agent.grant(NON_RVC_HIGH)
    assert first.state_after == REFILL_REQ
    assert agent.snapshot()["resends"] == 1
    second = await agent.acquire()
    check_acquire(second, aligned_bus_address(addr, 1), mm=1, nc=0)
    await agent.grant(SECOND_BEAT)
    response = await agent.idle()
    check_response(response, data=expected_resend_data(NON_RVC_HIGH, SECOND_BEAT),
                   corrupt=0, denied=0, need_resend=0)


@pytest.mark.feature("INC-TOP-004")
@pytest.mark.parametrize("corrupt, denied", [(1, 0), (1, 1)])
async def test_top_cross_bus_exception_suppresses_resend(instr_uncache_agent, corrupt, denied):
    agent = instr_uncache_agent
    addr = BASE + 6
    await agent.request(addr)
    await agent.acquire()
    refill = await agent.grant(NON_RVC_HIGH, corrupt=corrupt, denied=denied)
    assert refill.state_after == SEND_RESP
    response = await agent.idle()
    check_response(response, data=None, corrupt=corrupt, denied=denied,
                   need_resend=0)
    assert response.events.acquire_fire == 0


@pytest.mark.feature("INC-TOP-004")
@pytest.mark.parametrize("beat, corrupt, expected_need", [
    (NON_RVC_HIGH, 0, 1),
    (0x0002_0000_0000_0000, 0, 0),
    (NON_RVC_HIGH, 1, 0),
])
async def test_top_cross_page_need_resend_conditions(instr_uncache_agent, beat, corrupt,
                                                     expected_need):
    agent = instr_uncache_agent
    addr = BASE + 0xFFE
    await agent.request(addr)
    await agent.acquire()
    await agent.grant(beat, corrupt=corrupt)
    response = await agent.idle()
    check_response(response, data=None if corrupt else fetch_window(addr, beat),
                   corrupt=corrupt, denied=0, need_resend=expected_need)
    assert response.events.acquire_fire == 0


@pytest.mark.feature("INC-TOP-004")
@pytest.mark.parametrize("corrupt, denied", [(0, 0), (1, 0), (1, 1)])
async def test_top_exception_flags_are_forwarded(instr_uncache_agent, corrupt, denied):
    agent = instr_uncache_agent
    addr = BASE + 2
    await agent.request(addr)
    await agent.acquire()
    await agent.grant(BEAT, corrupt=corrupt, denied=denied)
    response = await agent.idle()
    clean = corrupt == 0 and denied == 0
    check_response(response, data=fetch_window(addr, BEAT) if clean else None,
                   corrupt=corrupt, denied=denied, need_resend=0)
    if denied:
        assert response.before.resp_corrupt == 1


@pytest.mark.feature("INC-TOP-002")
async def test_top_filters_nonzero_d_source(instr_uncache_agent):
    agent = instr_uncache_agent
    addr = BASE + 0
    await agent.request(addr)
    await agent.acquire()
    filtered = await agent.grant(0xDEAD_BEEF_0000_0000, source=1)
    check_source_filter(filtered)
    assert filtered.state_after == REFILL_RESP
    assert agent.snapshot()["filtered_grants"] == 1

    filtered_again = await agent.grant(0x1111_2222_3333_4444, source=1, corrupt=1)
    check_source_filter(filtered_again)
    assert filtered_again.state_after == REFILL_RESP
    assert filtered_again.before.resp_valid == 0

    await agent.grant(BEAT, source=0)
    response = await agent.idle()
    check_response(response, data=fetch_window(addr, BEAT), corrupt=0, denied=0,
                   need_resend=0)

    # A stale nonzero-source D response while idle must not create a request.
    stale = await agent.grant(0xAAAA_BBBB_CCCC_DDDD, source=1)
    check_source_filter(stale)
    assert stale.state_after == IDLE
    assert stale.before.req_ready == 1


@pytest.mark.feature("INC-TOP-003")
async def test_top_wfi_blocks_a_and_reports_safe(instr_uncache_agent):
    agent = instr_uncache_agent
    await agent.request(BASE + 4)
    blocked = await agent.acquire(ready=1, wfi_req=1)
    check_wfi(blocked)
    assert blocked.before.a_valid == 0
    assert blocked.state_after == REFILL_REQ
    issued = await agent.acquire(ready=1, wfi_req=0)
    check_acquire(issued, aligned_bus_address(BASE + 4), mm=1, nc=0)
    unsafe = await agent.idle(wfi_req=0)
    check_wfi(unsafe)
    assert unsafe.before.wfi_safe == 0
    await agent.grant(BEAT, wfi_req=1)
    response = await agent.idle()
    check_response(response, data=fetch_window(BASE + 4, BEAT), corrupt=0, denied=0,
                   need_resend=0)


@pytest.mark.feature("INC-TOP-003")
async def test_top_single_outstanding_and_second_request_after_completion(
        instr_uncache_agent):
    agent = instr_uncache_agent
    first = BASE + 0
    await agent.request(first)
    for _ in range(3):
        rejected = await agent.cycle(Inputs(req_valid=1, req_addr=BASE + 0x20,
                                             a_ready=0))
        assert rejected.events.req_fire == 0
        check_single_outstanding(rejected)
    await agent.acquire()
    await agent.grant(BEAT)
    response = await agent.idle()
    check_response(response, data=fetch_window(first, BEAT), corrupt=0, denied=0,
                   need_resend=0)
    second = await agent.request(BASE + 0x20)
    check_request_accepted(second)
    await agent.reset(cycles=1, reason="finish the second outstanding request")


@pytest.mark.feature("INC-TOP-003")
async def test_top_response_loss_then_delivery(instr_uncache_agent):
    agent = instr_uncache_agent
    addr = BASE + 0x10
    await agent.request(addr)
    await agent.acquire()
    for _ in range(2):
        missing = await agent.idle()
        check_no_response(missing)
        check_response_loss_persists(missing, REFILL_RESP)
    await agent.grant(BEAT)
    response = await agent.idle()
    check_response(response, data=fetch_window(addr, BEAT), corrupt=0, denied=0,
                   need_resend=0)


@pytest.mark.feature("INC-TOP-003")
async def test_top_reset_cancels_outstanding(instr_uncache_agent):
    agent = instr_uncache_agent
    await agent.request(BASE + 0x20)
    await agent.acquire()
    await agent.reset(cycles=2, reason="directed top cancellation")
    assert agent.state == IDLE
    assert agent.snapshot()["aborted"] == 1
    addr = BASE + 0x40
    await agent.request(addr)
    await agent.acquire()
    await agent.grant(BEAT)
    await agent.idle()
    assert agent.state == IDLE


@pytest.mark.feature("INC-TOP-001")
@pytest.mark.feature("INC-TOP-003")
@pytest.mark.feature("INC-TOP-004")
async def test_top_randomized_protocol_matches_composed_model(instr_uncache_agent):
    agent = instr_uncache_agent
    seed = int(os.environ.get("UCV_SEED", "1"))
    rng = random.Random(seed ^ 0x70F0_0001)
    for _ in range(320):
        state = agent.state
        if state == IDLE:
            if rng.random() < 0.65:
                inputs = Inputs(
                    req_valid=1,
                    req_addr=legal_random_address(rng),
                    req_mem_back_mm=rng.randrange(2),
                    req_mem_page_nc=rng.randrange(2),
                    a_ready=rng.randrange(2),
                    wfi_req=rng.randrange(2),
                )
            else:
                inputs = Inputs(a_ready=rng.randrange(2), wfi_req=rng.randrange(2))
        elif state == REFILL_REQ:
            inputs = Inputs(a_ready=rng.randrange(2), wfi_req=rng.randrange(2))
        elif state == REFILL_RESP:
            if rng.random() < 0.85:
                corrupt = rng.randrange(2)
                denied = rng.randrange(2) if corrupt else 0
                # Normal traffic is source 0; occasional source 1 checks filtering.
                source = 1 if rng.random() < 0.1 else 0
                inputs = Inputs(d_valid=1, d_source=source,
                                d_data=rng.getrandbits(64), d_corrupt=corrupt,
                                d_denied=denied, wfi_req=rng.randrange(2))
            else:
                inputs = Inputs(wfi_req=rng.randrange(2))
        else:
            inputs = Inputs(wfi_req=rng.randrange(2))
        if rng.random() < 0.008:
            inputs = replace(inputs, reset=1, req_valid=0, d_valid=0)
        await agent.cycle(inputs)

    for _ in range(16):
        if agent.state == IDLE:
            break
        if agent.state == REFILL_REQ:
            await agent.acquire()
        elif agent.state == REFILL_RESP:
            await agent.grant(rng.getrandbits(64), source=0)
        else:
            await agent.idle()
    assert agent.state == IDLE, f"seed {seed}: top did not drain"
