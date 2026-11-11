"""InstrUncacheEntry directed and randomized contract tests."""

from __future__ import annotations

import os
import random

import pytest

from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.checker import check_acquire
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.checker import check_flush_pruned
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.checker import check_acquire_stalled
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.checker import check_no_response
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.checker import check_request_accepted
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.checker import check_response
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.checker import check_response_loss_persists
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.checker import check_single_outstanding
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.checker import check_wfi
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import IDLE
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import REFILL_REQ
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import REFILL_RESP
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import SEND_RESP
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import EntryInputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import aligned_bus_address
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import fetch_window
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import refill_needs_resend
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import replace_input

#: MMIO-ish address used by the directed tests; bit 0 must stay zero.
BASE = 0x3A00_0000
BEAT = 0x1122_3344_5566_7788
#: High halfword 0xCAFF has low bits 11, so a sel=3 fetch is non-RVC.
NON_RVC_HIGH = 0xCAFF_0000_0000_0000
SECOND_BEAT = 0xDEF3_5678_9ABC_1234


def expected_resend_data(first: int, second: int) -> int:
    """First beat supplies bus[63:48] as low half; second supplies bus[15:0]."""
    return (((second & 0xFFFF) << 16) | ((first >> 48) & 0xFFFF)) & 0xFFFF_FFFF


def legal_random_address(rng: random.Random) -> int:
    """Stay inside the DefaultConfig physical map (< 2**43)."""
    choice = rng.randrange(3)
    if choice == 0:
        return (rng.randrange(0, 1 << 40) * 2) & ~1
    if choice == 1:
        return BASE + ((rng.randrange(0, 0x1000)) & ~1)
    return ((rng.randrange(0, 1 << 30)) << 12) | 0xFFE


@pytest.mark.feature("INC-ENT-001")
@pytest.mark.feature("INC-ENT-008")
async def test_reset_enters_invalid_and_idle_outputs(instr_uncache_entry_agent):
    agent = instr_uncache_entry_agent
    assert agent.state == IDLE
    cycle = await agent.idle()
    assert cycle.before.req_ready == 1
    assert cycle.before.resp_valid == 0
    assert cycle.before.acquire_valid == 0
    assert cycle.before.wfi_safe == 1
    assert cycle.after.req_ready == 1
    assert cycle.after.resp_valid == 0


@pytest.mark.feature("INC-ENT-001")
@pytest.mark.feature("INC-ENT-002")
async def test_request_accept_acquire_stall_and_single_response(instr_uncache_entry_agent):
    agent = instr_uncache_entry_agent
    addr = BASE + 6
    accepted = await agent.request(addr, mem_back_mm=0, mem_page_nc=1)
    check_request_accepted(accepted)
    check_single_outstanding(accepted)
    assert agent.state == REFILL_REQ

    expected = aligned_bus_address(addr)
    stalled = await agent.acquire(ready=0, wfi_req=0)
    check_acquire_stalled(stalled, expected)
    stalled_again = await agent.acquire(ready=0)
    check_acquire_stalled(stalled_again, expected)
    issued = await agent.acquire(ready=1)
    check_acquire(issued, expected, mm=0, nc=1)
    assert issued.state_after == REFILL_RESP

    refill = await agent.grant(BEAT)
    assert refill.state_after == SEND_RESP
    response = await agent.idle()
    check_response(response, data=fetch_window(addr, BEAT), corrupt=0, denied=0,
                   need_resend=0)
    assert response.state_after == IDLE
    assert agent.snapshot()["completed"] == 1


@pytest.mark.feature("INC-ENT-002")
@pytest.mark.parametrize("addr, mm, nc", [
    (BASE + 0, 0, 0),
    (BASE + 2, 1, 0),
    (BASE + 4, 0, 1),
    (BASE + 6, 1, 1),
    (0x7FF_FFFF_F000, 1, 0),
])
async def test_acquire_address_is_eight_byte_aligned_with_user_attributes(
        instr_uncache_entry_agent, addr, mm, nc):
    agent = instr_uncache_entry_agent
    await agent.request(addr, mem_back_mm=mm, mem_page_nc=nc)
    acquire = await agent.acquire()
    check_acquire(acquire, aligned_bus_address(addr), mm=mm, nc=nc)
    assert acquire.before.acquire_addr % 8 == 0
    await agent.reset(cycles=1, reason="address scenario ends after the A issue")


@pytest.mark.feature("INC-ENT-003")
@pytest.mark.parametrize("selector", [0, 1, 2, 3])
async def test_four_byte_window_uses_addr_bits_2_1(instr_uncache_entry_agent, selector):
    agent = instr_uncache_entry_agent
    addr = BASE + selector * 2
    expected = fetch_window(addr, BEAT)
    await agent.request(addr)
    acquire = await agent.acquire()
    check_acquire(acquire, aligned_bus_address(addr), mm=1, nc=0)
    await agent.grant(BEAT)
    response = await agent.idle()
    check_response(response, data=expected, corrupt=0, denied=0, need_resend=0)


@pytest.mark.feature("INC-ENT-004")
@pytest.mark.feature("INC-ENT-002")
async def test_cross_bus_boundary_resends_and_merges_two_beats(instr_uncache_entry_agent):
    agent = instr_uncache_entry_agent
    addr = BASE + 6
    assert refill_needs_resend(addr, NON_RVC_HIGH, corrupt=0, resending=0)
    await agent.request(addr)
    first = await agent.acquire()
    check_acquire(first, aligned_bus_address(addr), mm=1, nc=0)
    refill = await agent.grant(NON_RVC_HIGH)
    assert refill.state_before == REFILL_RESP
    assert refill.state_after == REFILL_REQ
    assert agent.snapshot()["resends"] == 1

    second = await agent.acquire()
    check_acquire(second, aligned_bus_address(addr, 1), mm=1, nc=0)
    assert second.before.acquire_addr == aligned_bus_address(addr) + 8
    await agent.grant(SECOND_BEAT)
    response = await agent.idle()
    check_response(response, data=expected_resend_data(NON_RVC_HIGH, SECOND_BEAT),
                   corrupt=0, denied=0, need_resend=0)
    assert response.state_after == IDLE


@pytest.mark.feature("INC-ENT-004")
async def test_cross_bus_rvc_does_not_request_a_second_beat(instr_uncache_entry_agent):
    agent = instr_uncache_entry_agent
    addr = BASE + 6
    rvc_high = 0x0002_0000_0000_0000
    assert not refill_needs_resend(addr, rvc_high, corrupt=0, resending=0)
    await agent.request(addr)
    await agent.acquire()
    refill = await agent.grant(rvc_high)
    assert refill.state_after == SEND_RESP
    response = await agent.idle()
    check_response(response, data=fetch_window(addr, rvc_high), corrupt=0, denied=0,
                   need_resend=0)
    assert response.events.acquire_fire == 0


@pytest.mark.feature("INC-ENT-004")
@pytest.mark.feature("INC-ENT-006")
@pytest.mark.parametrize("corrupt, denied", [(1, 0), (1, 1)])
async def test_cross_bus_exception_suppresses_resend(
        instr_uncache_entry_agent, corrupt, denied):
    agent = instr_uncache_entry_agent
    addr = BASE + 6
    await agent.request(addr)
    await agent.acquire()
    refill = await agent.grant(NON_RVC_HIGH, corrupt=corrupt, denied=denied)
    assert refill.state_after == SEND_RESP
    response = await agent.idle()
    check_response(response, data=None, corrupt=corrupt, denied=denied,
                   need_resend=0)
    assert response.events.acquire_fire == 0


@pytest.mark.feature("INC-ENT-005")
@pytest.mark.parametrize("beat, corrupt, expected_need, expected_data", [
    (NON_RVC_HIGH, 0, 1, fetch_window(0x3A00_0FFE, NON_RVC_HIGH)),
    (0x0002_0000_0000_0000, 0, 0, fetch_window(0x3A00_0FFE, 0x0002_0000_0000_0000)),
    (NON_RVC_HIGH, 1, 0, None),
])
async def test_cross_page_boundary_sets_need_resend_only_for_clean_non_rvc(
        instr_uncache_entry_agent, beat, corrupt, expected_need, expected_data):
    agent = instr_uncache_entry_agent
    addr = BASE + 0xFFE
    await agent.request(addr)
    await agent.acquire()
    refill = await agent.grant(beat, corrupt=corrupt)
    assert refill.state_after == SEND_RESP
    response = await agent.idle()
    check_response(response, data=expected_data, corrupt=corrupt, denied=0,
                   need_resend=expected_need)
    assert response.events.acquire_fire == 0


@pytest.mark.feature("INC-ENT-006")
@pytest.mark.parametrize("corrupt, denied", [(0, 0), (1, 0), (1, 1)])
async def test_corrupt_and_denied_are_forwarded(instr_uncache_entry_agent, corrupt, denied):
    agent = instr_uncache_entry_agent
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


@pytest.mark.feature("INC-ENT-007")
async def test_wfi_blocks_new_acquire_and_reports_safe_by_state(instr_uncache_entry_agent):
    agent = instr_uncache_entry_agent
    await agent.request(BASE + 4)
    blocked = await agent.acquire(ready=1, wfi_req=1)
    check_wfi(blocked)
    assert blocked.before.acquire_valid == 0
    assert blocked.events.acquire_fire == 0
    assert blocked.state_after == REFILL_REQ

    still_blocked = await agent.acquire(ready=0, wfi_req=1)
    check_wfi(still_blocked)
    assert still_blocked.state_after == REFILL_REQ

    issued = await agent.acquire(ready=1, wfi_req=0)
    check_acquire(issued, aligned_bus_address(BASE + 4), mm=1, nc=0)
    assert issued.state_after == REFILL_RESP

    unsafe = await agent.idle(wfi_req=0)
    check_wfi(unsafe)
    assert unsafe.before.wfi_safe == 0 and unsafe.state_after == REFILL_RESP

    grant = await agent.grant(BEAT, wfi_req=1)
    check_wfi(grant)
    assert grant.state_after == SEND_RESP
    response = await agent.idle()
    check_response(response, data=fetch_window(BASE + 4, BEAT), corrupt=0, denied=0,
                   need_resend=0)


@pytest.mark.feature("INC-ENT-001")
@pytest.mark.feature("INC-ENT-008")
async def test_single_outstanding_rejects_second_request_until_completion(
        instr_uncache_entry_agent):
    agent = instr_uncache_entry_agent
    first_addr = BASE + 0
    second_addr = BASE + 0x20
    accepted = await agent.request(first_addr)
    check_request_accepted(accepted)
    for _ in range(3):
        rejected = await agent.cycle(EntryInputs(req_valid=1, req_addr=second_addr,
                                                 acquire_ready=0, wfi_req=0))
        assert rejected.events.req_fire == 0
        check_single_outstanding(rejected)
        assert rejected.state_after == REFILL_REQ

    await agent.acquire()
    await agent.grant(BEAT)
    response = await agent.idle()
    check_response(response, data=fetch_window(first_addr, BEAT), corrupt=0, denied=0,
                   need_resend=0)
    assert response.state_after == IDLE

    next_accepted = await agent.request(second_addr)
    check_request_accepted(next_accepted)
    await agent.reset(cycles=1, reason="finish the second outstanding request")


@pytest.mark.feature("INC-ENT-008")
async def test_response_loss_keeps_obligation_until_delivery(instr_uncache_entry_agent):
    agent = instr_uncache_entry_agent
    addr = BASE + 0x10
    await agent.request(addr)
    await agent.acquire()
    assert agent.state == REFILL_RESP
    for _ in range(3):
        missing = await agent.idle()
        check_no_response(missing)
        check_response_loss_persists(missing, REFILL_RESP)
    await agent.grant(BEAT)
    response = await agent.idle()
    check_response(response, data=fetch_window(addr, BEAT), corrupt=0, denied=0,
                   need_resend=0)


@pytest.mark.feature("INC-ENT-008")
async def test_reset_cancels_outstanding_and_discards_pending_response(
        instr_uncache_entry_agent):
    agent = instr_uncache_entry_agent
    await agent.request(BASE + 0x20)
    await agent.acquire()
    assert agent.state == REFILL_RESP
    await agent.reset(cycles=2, reason="directed cancellation of a lost response")
    assert agent.state == IDLE
    assert agent.snapshot()["aborted"] == 1

    addr = BASE + 0x40
    accepted = await agent.request(addr)
    check_request_accepted(accepted)
    await agent.acquire()
    await agent.grant(BEAT)
    pending = await agent.idle()
    assert pending.before.resp_valid == 1
    # The response-ready constant true means the observation cycle is also the
    # consuming cycle; an idle reset must not invent another abort.
    await agent.reset(cycles=1, reason="idle reset after the response pulse")
    assert agent.state == IDLE
    assert agent.snapshot()["aborted"] == 1


@pytest.mark.selftest
@pytest.mark.feature("INC-FLUSH-012")
async def test_flush_path_is_structurally_pruned(instr_uncache_entry_agent):
    check_flush_pruned(instr_uncache_entry_agent.audit())


@pytest.mark.feature("INC-ENT-001")
@pytest.mark.feature("INC-ENT-002")
@pytest.mark.feature("INC-ENT-003")
@pytest.mark.feature("INC-ENT-004")
@pytest.mark.feature("INC-ENT-005")
@pytest.mark.feature("INC-ENT-006")
@pytest.mark.feature("INC-ENT-007")
@pytest.mark.feature("INC-ENT-008")
async def test_entry_randomized_protocol_matches_model(instr_uncache_entry_agent):
    agent = instr_uncache_entry_agent
    seed = int(os.environ.get("UCV_SEED", "1"))
    rng = random.Random(seed ^ 0x51F0_0001)
    for _ in range(320):
        state = agent.state
        if state == IDLE:
            if rng.random() < 0.65:
                inputs = EntryInputs(
                    req_valid=1,
                    req_addr=legal_random_address(rng),
                    req_mem_back_mm=rng.randrange(2),
                    req_mem_page_nc=rng.randrange(2),
                    acquire_ready=rng.randrange(2),
                    wfi_req=rng.randrange(2),
                )
            else:
                inputs = EntryInputs(acquire_ready=rng.randrange(2),
                                     wfi_req=rng.randrange(2))
        elif state == REFILL_REQ:
            inputs = EntryInputs(acquire_ready=rng.randrange(2),
                                 wfi_req=rng.randrange(2))
        elif state == REFILL_RESP:
            if rng.random() < 0.85:
                corrupt = rng.randrange(2)
                denied = rng.randrange(2) if corrupt else 0
                inputs = EntryInputs(grant_valid=1, grant_data=rng.getrandbits(64),
                                     grant_corrupt=corrupt, grant_denied=denied,
                                     wfi_req=rng.randrange(2))
            else:
                inputs = EntryInputs(wfi_req=rng.randrange(2))
        else:
            inputs = EntryInputs(wfi_req=rng.randrange(2))
        if rng.random() < 0.008:
            inputs = replace_input(inputs, reset=1, req_valid=0, grant_valid=0)
        await agent.cycle(inputs)

    for _ in range(16):
        if agent.state == IDLE:
            break
        if agent.state == REFILL_REQ:
            await agent.acquire()
        elif agent.state == REFILL_RESP:
            await agent.grant(rng.getrandbits(64))
        else:
            await agent.idle()
    assert agent.state == IDLE, f"seed {seed}: entry did not drain"
    agent.snapshot()
