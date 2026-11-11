"""Original leaf-port scenarios plus strict producer-owned complete read histories.

The old address constants were raw halfword coordinates; explicit <<1 keeps the
same physical inputs while the transaction API now consistently uses bytes.
Original scenarios use characterize_cycle: reserved PBMT, cacheable requests and
arbitrary reply/resend combinations are not claimed as normal IFU peer traffic.
"""
import random

import pytest

from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import EXC_AF
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import EXC_HWE
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import EXC_NONE
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import IDLE
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import IO
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import Inputs
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import NC
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import PMA
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import SEND
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import WAIT_COMMIT
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import WAIT_RESP
from suites.frontend.ifu.testbenches.uncache_unit.env.stimulus import random_port_inputs
from suites.frontend.ifu.testbenches.uncache_unit.transactions import BusReply
from suites.frontend.ifu.testbenches.uncache_unit.transactions import ReadRequest

IDLE_INPUTS = Inputs(to_ready=1)


@pytest.mark.feature('IFU-UC-001')
@pytest.mark.feature('IFU-UC-003')
@pytest.mark.feature('IFU-UC-004')
async def test_idle_accept_then_send_non_idempotent_type_attributes(uncache_unit):
    address = 0x123456789ABC << 1
    await uncache_unit.characterize_cycle(Inputs(req_valid=1, req_paddr=address, req_pbmt=NC))
    assert uncache_unit.status.phase == SEND
    out = (await uncache_unit.characterize_cycle(IDLE_INPUTS)).before
    assert out.req_ready == 0 and out.to_valid == 1
    assert out.to_paddr == address and out.to_mem_back_mm == 1 and out.to_mem_page_nc == 1
    assert uncache_unit.status.phase == WAIT_RESP
    await uncache_unit.cancel_pending('scenario verifies capture/issue, not a supplied response')


@pytest.mark.feature('IFU-UC-002')
async def test_non_idempotent_accesses_wait_for_commit(uncache_unit):
    for is_mmio, pbmt in ((1, PMA), (0, IO), (1, IO)):
        await uncache_unit.reset(reason='next independent memory-type wait scenario')
        await uncache_unit.characterize_cycle(Inputs(req_valid=1, req_paddr=0x1000 << 1,
                                                       req_is_mmio=is_mmio, req_pbmt=pbmt))
        assert uncache_unit.status.phase == WAIT_COMMIT
        for _ in range(3):
            out = (await uncache_unit.characterize_cycle(Inputs(is_first_instr=0, empty_after=0))).before
            assert out.to_valid == 0 and uncache_unit.status.phase == WAIT_COMMIT
        if is_mmio:
            await uncache_unit.characterize_cycle(Inputs(is_first_instr=1))
        else:
            await uncache_unit.characterize_cycle(Inputs(empty_after=1))
        assert uncache_unit.status.phase == SEND
    await uncache_unit.cancel_pending('wait-release scenario ends before supplying bus data')


@pytest.mark.feature('IFU-UC-002')
async def test_ordinary_non_cacheable_pages_do_not_wait(uncache_unit):
    for is_mmio, pbmt in ((0, PMA), (0, NC)):
        await uncache_unit.reset(reason='next independent immediate-issue port scenario')
        await uncache_unit.characterize_cycle(Inputs(req_valid=1, req_is_mmio=is_mmio, req_pbmt=pbmt))
        assert uncache_unit.status.phase == SEND
    await uncache_unit.cancel_pending('immediate phase scenario does not supply a response')


@pytest.mark.feature('IFU-UC-003')
async def test_request_is_held_until_the_bus_accepts(uncache_unit):
    address = 0x0BADF00D << 1
    await uncache_unit.characterize_cycle(Inputs(req_valid=1, req_paddr=address, req_pbmt=NC))
    for _ in range(3):
        out = (await uncache_unit.characterize_cycle(Inputs(to_ready=0))).before
        assert out.to_valid == 1 and out.to_paddr == address
        assert uncache_unit.status.phase == SEND
    out = (await uncache_unit.characterize_cycle(Inputs(ifu_stall=1, to_ready=1))).before
    assert out.to_valid == 0 and uncache_unit.status.phase == SEND
    # Payload has no bus contract while valid0. It is checked again when valid1.
    await uncache_unit.characterize_cycle(Inputs(ifu_stall=1, to_ready=0))
    assert uncache_unit.status.phase == SEND
    out = (await uncache_unit.characterize_cycle(Inputs(to_ready=1))).before
    assert out.to_valid == 1 and out.to_paddr == address
    assert uncache_unit.status.phase == WAIT_RESP
    await uncache_unit.cancel_pending('hold/issue-only scenario has no peer response')


@pytest.mark.feature('IFU-UC-001')
@pytest.mark.feature('IFU-UC-008')
async def test_requests_are_ignored_while_busy(uncache_unit):
    await uncache_unit.characterize_cycle(Inputs(req_valid=1, req_paddr=0x1111 << 1, req_pbmt=NC))
    for _ in range(3):
        out = (await uncache_unit.characterize_cycle(Inputs(req_valid=1, req_paddr=0x2222 << 1,
                                                           req_pbmt=PMA, to_ready=0))).before
        assert out.req_ready == 0 and out.to_paddr == 0x1111 << 1
    assert uncache_unit.status.accepted == 1 and uncache_unit.status.req_fires == 1
    await uncache_unit.cancel_pending('busy-port pressure does not promise a completed read')


@pytest.mark.feature('IFU-UC-005')
@pytest.mark.feature('IFU-UC-006')
async def test_bus_status_becomes_instruction_exception_and_one_pulse(uncache_unit):
    for corrupt, denied, exception in ((0, 0, EXC_NONE), (1, 0, EXC_HWE), (1, 1, EXC_AF)):
        await uncache_unit.reset(reason='next independent exception propagation port scenario')
        await uncache_unit.characterize_cycle(Inputs(req_valid=1, req_paddr=0x2000 << 1, req_pbmt=NC))
        await uncache_unit.characterize_cycle(Inputs(to_ready=1))
        assert uncache_unit.status.phase == WAIT_RESP
        out = (await uncache_unit.characterize_cycle(Inputs(from_valid=1, from_data=0xCAFEBABE,
                    from_corrupt=corrupt, from_denied=denied, from_need_resend=1))).before
        assert out.resp_valid == 0 and uncache_unit.status.phase == IDLE
        pulse = (await uncache_unit.characterize_cycle(IDLE_INPUTS)).before
        assert pulse.resp_valid == 1 and pulse.resp_data == 0xCAFEBABE
        assert pulse.resp_exception == exception and pulse.resp_need_resend == 1
        assert (await uncache_unit.characterize_cycle(IDLE_INPUTS)).before.resp_valid == 0


@pytest.mark.feature('IFU-UC-006')
@pytest.mark.feature('IFU-UC-008')
async def test_completion_is_back_to_back_usable(uncache_unit):
    await uncache_unit.characterize_cycle(Inputs(req_valid=1, req_paddr=0x3000 << 1, req_pbmt=NC))
    await uncache_unit.characterize_cycle(Inputs(to_ready=1))
    await uncache_unit.characterize_cycle(Inputs(from_valid=1, from_data=0x11))
    pulse = (await uncache_unit.characterize_cycle(Inputs(req_valid=1, req_paddr=0x4000 << 1, req_pbmt=PMA))).before
    assert pulse.resp_valid == 1 and pulse.req_ready == 1 and uncache_unit.status.phase == SEND
    out = (await uncache_unit.characterize_cycle(IDLE_INPUTS)).before
    assert out.to_valid == 1 and out.to_paddr == 0x4000 << 1
    await uncache_unit.cancel_pending('back-to-back readiness scenario ends after second issue')


@pytest.mark.feature('IFU-UC-007')
async def test_flush_aborts_every_phase_and_discards_late_response(uncache_unit):
    phases = []
    await uncache_unit.characterize_cycle(Inputs(flush=1))
    assert uncache_unit.status.phase == IDLE
    phases.append(uncache_unit.status.phase)
    await uncache_unit.reset()
    await uncache_unit.characterize_cycle(Inputs(req_valid=1, req_is_mmio=1, req_pbmt=PMA))
    await uncache_unit.characterize_cycle(Inputs(flush=1))
    assert uncache_unit.status.phase == IDLE
    phases.append(uncache_unit.status.phase)
    await uncache_unit.reset()
    await uncache_unit.characterize_cycle(Inputs(req_valid=1, req_pbmt=NC))
    await uncache_unit.characterize_cycle(Inputs(flush=1, to_ready=0))
    assert uncache_unit.status.phase == IDLE
    phases.append(uncache_unit.status.phase)
    await uncache_unit.reset()
    await uncache_unit.characterize_cycle(Inputs(req_valid=1, req_pbmt=NC))
    await uncache_unit.characterize_cycle(Inputs(to_ready=1))
    assert uncache_unit.status.phase == WAIT_RESP
    await uncache_unit.characterize_cycle(Inputs(flush=1))
    assert uncache_unit.status.phase == IDLE
    for _ in range(2):
        out = (await uncache_unit.characterize_cycle(Inputs(from_valid=1, from_data=0xDEAD))).before
        assert out.resp_valid == 0
    phases.append(uncache_unit.status.phase)
    assert phases == [IDLE, IDLE, IDLE, IDLE]


@pytest.mark.feature('IFU-UC-007')
async def test_flush_clears_a_completion_pulse(uncache_unit):
    await uncache_unit.characterize_cycle(Inputs(req_valid=1, req_pbmt=NC))
    await uncache_unit.characterize_cycle(Inputs(to_ready=1))
    await uncache_unit.characterize_cycle(Inputs(from_valid=1, from_data=0x55))
    out = (await uncache_unit.characterize_cycle(Inputs(flush=1))).before
    assert out.resp_valid == 1
    after = (await uncache_unit.characterize_cycle(IDLE_INPUTS)).before
    assert after.resp_valid == 0 and after.resp_data == 0  # Explicit zero-on-flush characterization.


@pytest.mark.feature('IFU-UC-007')
async def test_response_in_idle_is_ignored(uncache_unit):
    out = (await uncache_unit.characterize_cycle(Inputs(from_valid=1, from_data=0x7777, from_corrupt=1))).before
    assert out.resp_valid == 0
    after = (await uncache_unit.characterize_cycle(IDLE_INPUTS)).before
    assert after.resp_valid == 0 and uncache_unit.status.phase == IDLE


@pytest.mark.feature('IFU-UC-001')
@pytest.mark.feature('IFU-UC-002')
@pytest.mark.feature('IFU-UC-003')
@pytest.mark.feature('IFU-UC-004')
@pytest.mark.feature('IFU-UC-005')
@pytest.mark.feature('IFU-UC-006')
@pytest.mark.feature('IFU-UC-007')
@pytest.mark.feature('IFU-UC-008')
async def test_random_sequences_match_the_model(uncache_unit):
    rng = random.Random(0x0CACE)
    for _ in range(700):
        await uncache_unit.characterize_cycle(random_port_inputs(rng))
    state = uncache_unit.status
    assert state.phase in (IDLE, WAIT_COMMIT, SEND, WAIT_RESP)
    assert state.accepted - state.completed - state.cancelled == int(state.active_uid is not None)
    assert state.req_fires == state.accepted + state.flushed_on_accept
    # These are now measured sampled fires/validated pulses, not only shadow counters.
    assert (state.req_fires, state.accepted, state.completed, state.cancelled, state.flushed_on_accept) == (94, 89, 75, 13, 5)
    await uncache_unit.cancel_pending('finite700 port-pressure run explicitly abandons its final request')


@pytest.mark.feature('IFU-UC-001')
@pytest.mark.feature('IFU-UC-002')
@pytest.mark.feature('IFU-UC-004')
@pytest.mark.feature('IFU-UC-006')
@pytest.mark.parametrize('is_mmio,pbmt', [(0, NC), (0, IO), (1, PMA), (1, NC), (1, IO)])
async def test_complete_producer_reads_match_identity_address_and_type(uncache_unit, is_mmio, pbmt):
    read = await uncache_unit.read(ReadRequest(0x123456789ABC, is_mmio, pbmt), BusReply(0x00010001))
    assert read.cycle.events.completed_uid == read.uid and read.cycle.after.resp_data == 0x00010001
    record = next(record for record in uncache_unit.records if record.uid == read.uid)
    assert record.request.paddr == 0x123456789ABC and record.state == 'completed'
    assert record.fire_tick < record.issued_tick < record.terminal_tick
    assert uncache_unit.status.accepted == uncache_unit.status.issued == uncache_unit.status.completed == 1


@pytest.mark.feature('IFU-UC-005')
@pytest.mark.parametrize('reply,exception', [(BusReply(0x113), EXC_NONE),
    (BusReply(0x113, corrupt=1), EXC_HWE), (BusReply(0x113, corrupt=1, denied=1), EXC_AF)])
async def test_legal_peer_error_replies_complete_once(uncache_unit, reply, exception):
    read = await uncache_unit.read(ReadRequest(0x2200), reply)
    assert read.cycle.after.resp_exception == exception and read.cycle.after.resp_need_resend == 0
    quiet = await uncache_unit.cycle()
    assert quiet.before.resp_valid == 1 and quiet.after.resp_valid == 0
    assert quiet.events.previous_completion_uid == read.uid and quiet.events.completed_uid is None
    assert uncache_unit.status.completed == 1


@pytest.mark.feature('IFU-UC-005')
@pytest.mark.feature('IFU-UC-006')
@pytest.mark.parametrize('address,data,resend', [(0x2FFE, 0x113, 1), (0x2FFE, 0x0001, 0),
                                             (0x2FFC, 0x113, 0), ((1 << 48) - 2, 0x113, 1)])
async def test_real_cross_page_reply_rule_and_highest_physical_address(uncache_unit, address, data, resend):
    read = await uncache_unit.read(ReadRequest(address), BusReply(data, need_resend=resend))
    assert read.cycle.after.resp_need_resend == resend
    assert next(r for r in uncache_unit.records if r.uid == read.uid).request.paddr == address


@pytest.mark.feature('IFU-UC-006')
@pytest.mark.feature('IFU-UC-008')
async def test_completion_pulse_and_next_acceptance_have_distinct_uids(uncache_unit):
    first = await uncache_unit.read(ReadRequest(0x4000), BusReply(0x0001))
    second = await uncache_unit.cycle(Inputs(req_valid=1, req_paddr=0x4000, req_pbmt=NC, to_ready=0))
    uid = second.events.accepted_uid
    assert uid != first.uid and second.events.previous_completion_uid == first.uid
    assert second.before.resp_valid == 1 and second.after.resp_valid == 0
    issued = await uncache_unit.cycle(Inputs(to_ready=1))
    assert issued.events.bus_fire_uid == uid
    completed = await uncache_unit.reply(uid, BusReply(0x0001))
    assert completed.events.completed_uid == uid
    assert uncache_unit.status.accepted == uncache_unit.status.completed == 2


@pytest.mark.feature('IFU-UC-007')
async def test_cancelled_issued_uid_can_arrive_late_without_completing_a_new_unissued_read(uncache_unit):
    accepted = await uncache_unit.cycle(Inputs(req_valid=1, req_paddr=0x5000, req_pbmt=NC, to_ready=0))
    old = accepted.events.accepted_uid
    await uncache_unit.cycle(Inputs(to_ready=1))
    await uncache_unit.cancel_pending('old read cancelled before its peer reply')
    new = await uncache_unit.cycle(Inputs(req_valid=1, req_paddr=0x5000, req_pbmt=NC, to_ready=0))
    uid = new.events.accepted_uid
    late = await uncache_unit.reply(old, BusReply(0x0001))
    assert late.events.completed_uid is None and late.after.resp_valid == 0
    assert uncache_unit.status.active_uid == uid and uid != old
    await uncache_unit.cycle(Inputs(to_ready=1))
    assert (await uncache_unit.reply(uid, BusReply(0x0001))).events.completed_uid == uid
    assert uncache_unit.status.cancelled == uncache_unit.status.completed == 1


@pytest.mark.feature('IFU-UC-001')
@pytest.mark.feature('IFU-UC-007')
async def test_same_edge_flush_fire_is_recorded_but_does_not_create_a_live_request(uncache_unit):
    checked = await uncache_unit.cycle(Inputs(req_valid=1, req_paddr=0x6000, req_pbmt=NC,
                                            flush=1, to_ready=0))
    assert checked.events.req_fire_uid is not None and checked.events.accepted_uid is None
    assert checked.events.req_fire_uid in checked.events.cancelled_uids
    assert checked.after.req_ready == 1 and checked.after.to_valid == checked.after.resp_valid == 0
    status = uncache_unit.status
    assert (status.req_fires, status.accepted, status.flushed_on_accept, status.active_uid) == (1, 0, 1, None)
    completed = await uncache_unit.read(ReadRequest(0x6000), BusReply(1))
    assert completed.uid != checked.events.req_fire_uid and uncache_unit.status.completed == 1


@pytest.mark.feature('IFU-UC-002')
@pytest.mark.feature('IFU-UC-003')
async def test_legal_mmio_waits_then_issues_exactly_once_after_backpressure_and_ifu_stall(uncache_unit):
    accepted = await uncache_unit.cycle(Inputs(req_valid=1, req_paddr=0x7000, req_is_mmio=1, req_pbmt=PMA, to_ready=0))
    uid = accepted.events.accepted_uid
    for _ in range(3):
        waiting = await uncache_unit.cycle(Inputs(to_ready=1))
        assert waiting.before.to_valid == waiting.after.to_valid == 0 and waiting.events.bus_fire_uid is None
    await uncache_unit.cycle(Inputs(empty_after=1, to_ready=0))
    for controls in (Inputs(to_ready=0), Inputs(ifu_stall=1, to_ready=1), Inputs(to_ready=0)):
        held = await uncache_unit.cycle(controls)
        assert held.events.bus_fire_uid is None
    fired = await uncache_unit.cycle(Inputs(to_ready=1))
    assert fired.events.bus_fire_uid == uid and fired.before.to_paddr == 0x7000
    assert fired.before.to_mem_back_mm == fired.before.to_mem_page_nc == 0
    completed = await uncache_unit.reply(uid, BusReply(1))
    assert completed.events.completed_uid == uid
    assert uncache_unit.status.accepted == uncache_unit.status.issued == uncache_unit.status.completed == 1


@pytest.mark.feature('IFU-UC-007')
@pytest.mark.parametrize('phase', ['waiting', 'send', 'issued'])
async def test_explicit_cancel_then_same_address_new_uid_has_no_old_completion(uncache_unit, phase):
    checked = await uncache_unit.cycle(Inputs(req_valid=1, req_paddr=0x8000,
        req_is_mmio=int(phase == 'waiting'), req_pbmt=PMA if phase == 'waiting' else NC, to_ready=0))
    old = checked.events.accepted_uid
    if phase == 'issued':
        await uncache_unit.cycle(Inputs(to_ready=1))
    cancelled = await uncache_unit.cancel_pending(f'explicit {phase} cancellation; peer flush filters this generation')
    assert old in cancelled.events.cancelled_uids and cancelled.after.resp_valid == 0
    new = await uncache_unit.read(ReadRequest(0x8000), BusReply(1))
    assert new.uid != old and new.cycle.events.completed_uid == new.uid
    assert uncache_unit.status.completed == uncache_unit.status.cancelled == 1
