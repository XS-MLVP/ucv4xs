"""IFU top level: fetch-window reconstruction, enqueue backpressure and redirect."""

from __future__ import annotations

import pytest

from suites.frontend.ifu.testbenches.ifu.transactions import FetchRequest
from suites.frontend.ifu.testbenches.ifu.transactions import Frame
from suites.frontend.ifu.testbenches.uncache_unit.transactions import BusReply
from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi
from suites.frontend.ifu.testbenches.ifu.model.cenc import c_li
from suites.frontend.ifu.testbenches.ifu.model.cenc import c_lw
from suites.frontend.ifu.testbenches.ifu.model.cenc import c_sw
from suites.frontend.ifu.testbenches.ifu.model.fetch import Window
from suites.frontend.ifu.testbenches.ifu.model.fetch import aligned_lanes
from suites.frontend.ifu.testbenches.ifu.model.fetch import build_window
from suites.frontend.ifu.testbenches.rvc_expander.model.rvc import expand
from suites.frontend.ifu.testbenches.ifu.model.isa import add
from suites.frontend.ifu.testbenches.ifu.model.isa import addi
from suites.frontend.ifu.testbenches.ifu.model.isa import beq
from suites.frontend.ifu.testbenches.ifu.model.isa import ebreak
from suites.frontend.ifu.testbenches.ifu.model.isa import jal
from suites.frontend.ifu.testbenches.ifu.model.isa import jalr
from suites.frontend.ifu.testbenches.ifu.model.isa import lui
from suites.frontend.ifu.testbenches.ifu.model.isa import mul
from suites.frontend.ifu.testbenches.ifu.model.isa import load_bytes
from suites.frontend.ifu.testbenches.ifu.model.isa import nop
from suites.frontend.ifu.testbenches.ifu.model.isa import store_bytes
from suites.frontend.ifu.testbenches.ifu.model.isa import sub


# ---------------------------------------------------------------------------
# Clean fetch paths
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-TOP-001")
@pytest.mark.feature("IFU-TOP-002")
async def test_single_block_mixed_instructions(ifu_agent):
    program = [
        (addi(5, 0, 1), 0),
        (c_addi(10, 2), 1),
        (sub(7, 8, 9), 0),
        (c_li(11, -1), 1),
        (nop(), 0),
        (c_lw(12, 13, 4), 1),
        (c_addi(14, -4), 1),
        (addi(15, 0, 7), 0),
    ]
    window = build_window(program, 0x1000, ftq0=(0, 5))
    result = await ifu_agent.fetch(FetchRequest(window))
    assert result.redirect is None
    assert result.beat is not None  # The agent checks the complete independent answer.


@pytest.mark.feature("IFU-TOP-002")
async def test_two_blocks_and_cross_block_full_width_instruction(ifu_agent):
    program = [
        (c_addi(10, 1), 1),     # slot 0
        (addi(5, 0, 7), 0),     # slots 1-2
        (c_li(6, 3), 1),        # slot 3
        (sub(7, 8, 9), 0),      # slots 4-5, crosses at split=5
        (c_addi(12, 4), 1),     # slot 6
        (addi(13, 0, 9), 0),    # slots 7-8
    ]
    window = build_window(program, 0x2000, split=5, ftq0=(0, 7), ftq1=(0, 8))
    result = await ifu_agent.fetch(FetchRequest(window))
    assert result.redirect is None and result.beat is not None


@pytest.mark.feature("IFU-TOP-004")
async def test_second_fetch_is_aligned_to_the_write_bank_pointer(ifu_agent):
    first = build_window([
        (addi(5, 0, 1), 0),
        (c_addi(6, 2), 1),
        (c_addi(7, 3), 1),
    ], 0x3000, ftq0=(0, 1))
    result = await ifu_agent.fetch(FetchRequest(first))
    assert result.redirect is None and result.beat is not None
    await ifu_agent.idle(3)
    second = build_window([
        (addi(8, 0, 4), 0),
        (c_addi(9, 5), 1),
        (sub(10, 11, 12), 0),
        (c_li(13, 6), 1),
    ], 0x3100, ftq0=(0, 2))
    result = await ifu_agent.fetch(FetchRequest(second))
    assert result.redirect is None and result.beat is not None
    assert ifu_agent.records[-1].shift == 3


@pytest.mark.feature("IFU-TOP-005")
async def test_unpredicted_jump_truncates_enqueue_and_redirects(ifu_agent):
    program = [
        (addi(5, 0, 1), 0),
        (jal(1, 0x40), 0),
        (c_addi(6, 2), 1),
        (addi(7, 0, 3), 0),
    ]
    window = build_window(program, 0x4000, ftq0=(0, 9))
    result = await ifu_agent.fetch(FetchRequest(window))
    beat, redirect = result.beat, result.redirect
    assert beat is not None and redirect is not None, "missing beat or redirect"
    expected, prediction, *_ = aligned_lanes(window, 0)
    model_redirect = prediction.redirect
    assert model_redirect.valid
    assert redirect.ftq == (0, 9)
    assert redirect.pc == 0x4000
    assert redirect.target == model_redirect.target
    assert redirect.taken == model_redirect.taken == 1
    assert redirect.branch_type == model_redirect.branch_type
    assert redirect.ras_action == model_redirect.ras_action
    assert redirect.offset == model_redirect.end_offset
    assert redirect.is_rvc == model_redirect.is_rvc
    assert redirect.can_train == 1


@pytest.mark.feature("IFU-TOP-006")
async def test_ibuffer_backpressure_holds_the_beat(ifu_agent):
    window = build_window([(addi(5, 0, 1), 0), (c_addi(6, 2), 1)], 0x5000)
    checked = await ifu_agent.cycle(Frame(request=FetchRequest(window), ibuffer_ready=0))
    assert checked.accepted_uid is not None
    first = None
    for _ in range(20):
        checked = await ifu_agent.cycle(Frame(ibuffer_ready=0))
        if checked.before.beat is not None:
            first = checked.before.beat
            break
    assert first is not None, "no beat appeared"
    for _ in range(3):
        again = (await ifu_agent.cycle(Frame(ibuffer_ready=0))).before.beat
        assert again == first
        assert ifu_agent.beat_fires == 0
    # Releasing ready consumes exactly one beat.
    assert (await ifu_agent.cycle()).beat_uid is not None
    for _ in range(3):
        assert (await ifu_agent.cycle()).before.beat is None
    assert ifu_agent.beat_fires == 1


@pytest.mark.feature("IFU-TOP-007")
async def test_backend_redirect_discards_the_inflight_fetch(ifu_agent):
    window = build_window([(addi(5, 0, 1), 0), (c_addi(6, 2), 1)], 0x6000)
    checked = await ifu_agent.cycle(Frame(request=FetchRequest(window)))
    assert checked.accepted_uid is not None
    # Flush immediately after acceptance, while the fetch is in s0/s1.
    await ifu_agent.cycle(Frame(backend_redirect=1))
    for _ in range(8):
        assert (await ifu_agent.cycle()).before.beat is None, "flushed fetch reached IBuffer"
    assert ifu_agent.records[-1].state == 'cancelled'


# ---------------------------------------------------------------------------
# Exceptions and triggers
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-TOP-003")
async def test_illegal_compressed_instruction_is_localized(ifu_agent):
    program = [
        (addi(5, 0, 1), 0),
        (0x0000, 1),           # reserved all-zero compressed encoding
        (c_addi(6, 2), 1),
        (addi(7, 0, 3), 0),
    ]
    window = build_window(program, 0x7000)
    result = await ifu_agent.fetch(FetchRequest(window))
    assert result.redirect is None and result.beat is not None
    assert result.beat.exception_type == 4  # illegal instruction
    assert result.beat.exception_mask == 1 << 1


@pytest.mark.feature("IFU-TOP-008")
async def test_page_fault_and_gpf_metadata(ifu_agent):
    program = [(addi(5, 0, 1), 0), (c_addi(6, 2), 1), (addi(7, 0, 3), 0)]
    for exception, gpaddr, expect_gp in ((1, 0, False), (2, 0x123456789ABC, True), (3, 0, False)):
        await ifu_agent.reset()
        window = build_window(program, 0x8000, exc0=exception, gp0=gpaddr,
                              vs0=1 if exception == 2 else 0)
        result = await ifu_agent.fetch(FetchRequest(window))
        assert result.redirect is None and result.beat is not None
        assert result.beat.exception_type == exception
        assert result.beat.exception_mask == 1
        assert (result.gpa is not None) == expect_gp
        if expect_gp:
            assert result.gpa.address == gpaddr
            assert result.gpa.ftq_index == 0
            assert result.gpa.for_vs == 1


@pytest.mark.feature("IFU-TOP-008")
async def test_backend_exception_and_satp_flush_markers_reach_the_first_instruction(ifu_agent):
    """The two ICache block-0 markers are attached to the enqueued instruction.

    ``isBackendException`` and ``hasSatpFlush`` tell the backend how to handle
    the trap (backend-raised exception / fault caused by a satp change).  They
    are only defined for the first instruction, so the IFU must forward them
    without dropping, duplicating, or moving them to another lane.  The
    semantic consumption (``satpFlushFirstFetchFault``) is IBuffer/backend
    responsibility and is out of this DUT.
    """

    program = [(addi(5, 0, 1), 0), (c_addi(6, 2), 1), (addi(7, 0, 3), 0)]
    for backend_exc, satp in ((1, 0), (0, 1), (1, 1)):
        await ifu_agent.reset()
        window = build_window(program, 0xA000 + 0x100 * (backend_exc + 2 * satp),
                              exc0=1, backend_exc0=backend_exc, satp0=satp)
        result = await ifu_agent.fetch(FetchRequest(window))
        beat = result.beat
        assert result.redirect is None and beat is not None
        assert beat.exception_type == 1 and beat.exception_mask == 1
        assert beat.is_backend_exception == backend_exc
        assert beat.has_satp_flush == satp


@pytest.mark.feature("IFU-TOP-008")
async def test_second_block_exception_moves_to_its_first_instruction(ifu_agent):
    program = [
        (c_addi(5, 1), 1),
        (addi(6, 0, 2), 0),
        (c_addi(7, 3), 1),
        (addi(8, 0, 4), 0),
    ]
    window = build_window(program, 0x9000, split=3, exc1=1, gp1=0x456)
    result = await ifu_agent.fetch(FetchRequest(window))
    beat = result.beat
    assert result.redirect is None and beat is not None
    assert beat.exception_type == 1
    # The first block has two instructions; the block-1 exception lands on
    # the first instruction of the second block.
    assert beat.exception_mask == 1 << 2


@pytest.mark.feature("IFU-TOP-010")
async def test_frontend_trigger_marks_the_matching_instruction(ifu_agent):
    from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import Inputs
    from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import Trigger
    from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import Update
    program = [
        (addi(5, 0, 1), 0),
        (c_addi(6, 2), 1),
        (sub(7, 8, 9), 0),
        (c_li(10, 3), 1),
    ]
    window = build_window(program, 0xA000)
    target = 0xA004  # the compressed instruction at slot 2 (after the 32-bit addi)
    inputs = Inputs(update=Update(1, 0, Trigger(action=1, tdata2=target)), enable=(1, 0, 0, 0))
    await ifu_agent.idle(2, frame=Frame(trigger=inputs))
    result = await ifu_agent.fetch(FetchRequest(window),
        frame=Frame(trigger=Inputs(enable=(1, 0, 0, 0), can_raise_breakpoint=0)))
    assert result.redirect is None and result.beat is not None
    assert result.beat.triggered[1] == 1
    assert all(action == 15 for index, action in enumerate(result.beat.triggered) if index != 1)


# ---------------------------------------------------------------------------
# Uncache fetch path
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-TOP-009")
async def test_uncache_fetch_issues_request_and_enqueues_one_instruction(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi as enc_addi
    returned = enc_addi(10, 5)
    window = build_window([(addi(5, 0, 1), 0)], 0xB000, pbmt0=1)
    # Explicit bytes preserve the old halfword coordinate0x123456789ABC.
    request = FetchRequest(window, physical_address=0x2468ACF13578)
    uid = await ifu_agent.send_uncached(request)
    issued = ifu_agent.records[-1].bus
    assert issued.address == 0x2468ACF13578
    assert issued.main_memory == issued.noncacheable == 1
    await ifu_agent.reply(uid, BusReply(returned))
    result = await ifu_agent.collect(uid)
    beat, redirect = result.beat, result.redirect
    assert beat is not None and redirect is not None
    expanded = expand(returned)
    assert beat.enq == beat.valid == 1  # shift zero, one instruction
    assert beat.instrs[0] == expanded.bits
    assert beat.is_rvc[0] == 1 and beat.exception_type == 0
    assert redirect.target == 0xB000 + 2
    assert redirect.offset == 0 and redirect.is_rvc == 1
    assert redirect.taken == redirect.can_train == 0


def dense_compressed(count: int = 32) -> list[tuple[int, int]]:
    program = []
    for index in range(count):
        kind = index % 8
        register = 8 + (index % 8)
        if kind == 0:
            program.append((c_addi(8 + (index % 8), (index % 7) - 3), 1))
        elif kind == 1:
            program.append((c_li(8 + (index % 8), (index % 5) + 1), 1))
        elif kind == 2:
            program.append((c_lw(register, 8 + ((index + 1) % 8), (index % 4) * 4), 1))
        elif kind == 3:
            program.append((c_sw(register, 8 + ((index + 1) % 8), (index % 4) * 4), 1))
        elif kind == 4:
            program.append((c_addi(register, -1), 1))
        elif kind == 5:
            program.append((c_li(register, -2), 1))
        elif kind == 6:
            program.append((c_addi(register, 2), 1))
        else:
            program.append((c_addi(register, 3), 1))
    return program


@pytest.mark.feature("IFU-TOP-002")
async def test_full_32_instruction_compressed_window(ifu_agent):
    window = build_window(dense_compressed(32), 0x10000, ftq0=(1, 33))
    result = await ifu_agent.fetch(FetchRequest(window))
    assert result.redirect is None and result.beat is not None
    assert result.beat.valid == (1 << 32) - 1
    assert result.beat.enq == (1 << 32) - 1


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-004")
async def test_full_window_after_a_three_bank_shift(ifu_agent):
    # Old flag=2 was outside the 1-bit RTL domain; use its explicit low bit.
    first = build_window(dense_compressed(3), 0x11000, ftq0=(0, 1))
    result = await ifu_agent.fetch(FetchRequest(first))
    assert result.redirect is None and result.beat is not None
    await ifu_agent.idle(3)
    second = build_window(dense_compressed(32), 0x1A00, ftq0=(0, 2))
    result = await ifu_agent.fetch(FetchRequest(second))
    assert result.redirect is None and result.beat is not None
    assert ifu_agent.records[-1].shift == 3
    assert result.beat.valid == (((1 << 32) - 1) << 3) & ((1 << 36) - 1)


@pytest.mark.feature("IFU-TOP-002")
async def test_conditional_branches_do_not_fault(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_beqz
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_bnez
    program = [
        (addi(5, 0, 1), 0),
        (c_beqz(8, 4), 1),
        (c_addi(9, 2), 1),
        (c_bnez(10, -4), 1),
        (c_addi(11, 3), 1),
        (c_addi(12, 4), 1),
    ]
    window = build_window(program, 0x12000)
    result = await ifu_agent.fetch(FetchRequest(window))
    assert result.redirect is None and result.beat is not None


@pytest.mark.feature("IFU-TOP-005")
async def test_jump_fault_classes_at_many_lanes(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_beqz
    for kind in ("jal", "jalr", "ret"):
        for lane in (0, 1, 3, 5, 7, 9):
            program = [(c_addi(8 + (index % 8), index % 5 + 1), 1)
                       for index in range(10)]
            if kind == "jal":
                program[lane] = (jal(1, 0x20), 0)
            elif kind == "jalr":
                program[lane] = (0x000080E7, 0)  # jalr x1, 0(x1)
            else:
                program[lane] = (0x00008067, 0)  # ret (jalr x0, 0(x1))
            window = build_window(program, 0x13000 + lane * 0x100, ftq0=(1, lane))
            await ifu_agent.reset()
            result = await ifu_agent.fetch(FetchRequest(window))
            assert result.beat is not None and result.redirect is not None


@pytest.mark.feature("IFU-TOP-005")
async def test_not_cfi_taken_redirects_sequentially(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_beqz
    program = [(c_beqz(8, 4), 1), (c_addi(9, 2), 1), (c_addi(10, 3), 1)]
    window = build_window(program, 0x14000, taken0=1)
    result = await ifu_agent.fetch(FetchRequest(window))
    assert result.beat is not None and result.redirect is not None
    assert result.redirect.target == 0x14000 + 4 + 2  # taken lane is the RVC at +4
    assert result.redirect.taken == 0
    assert result.redirect.branch_type == 0


@pytest.mark.feature("IFU-TOP-008")
async def test_icache_ecc_corruption_raises_hardware_error(ifu_agent):
    program = [(addi(5, 0, 1), 0), (c_addi(6, 2), 1), (addi(7, 0, 3), 0)]
    window = build_window(program, 0x15000)
    result = await ifu_agent.fetch(FetchRequest(window), corruption=(1, 0, 0, 0))
    assert result.beat is not None and result.redirect is None
    # The ECC error is merged into the first block's exception metadata and
    # therefore ends the window after the first instruction.
    assert result.beat.exception_type == 5
    assert result.beat.exception_mask == 1


@pytest.mark.feature("IFU-TOP-007")
async def test_bpu_stage3_flush_drops_the_window(ifu_agent):
    window = build_window([(addi(5, 0, 1), 0), (c_addi(6, 2), 1)], 0x16000, ftq0=(0, 21))
    # The stage-3 flush must drop the block in s0 before it is captured.
    for _ in range(6):
        checked = await ifu_agent.cycle(Frame(request=FetchRequest(window), bpu_flush=(0, 21)))
        assert checked.before.beat is None and checked.accepted_uid is None
        assert checked.req_fire_uid is not None
    # Releasing the flush lets the still-asserted request enter normally.
    result = await ifu_agent.fetch(FetchRequest(window))
    assert result.beat is not None and result.redirect is None
    assert ifu_agent.cancelled_on_fire == 6 and ifu_agent.beat_fires == 1


@pytest.mark.feature("IFU-TOP-002")
async def test_compressed_control_transfer_families_across_all_lanes(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_beqz
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_bnez
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_j
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_jalr
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_jr
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_mv
    program = []
    for index in range(32):
        kind = index % 8
        if kind == 0:
            program.append((c_j(4), 1))
        elif kind == 1:
            program.append((c_beqz(8 + (index % 8), 4), 1))
        elif kind == 2:
            program.append((c_bnez(8 + (index % 8), -4), 1))
        elif kind == 3:
            program.append((c_jalr(1), 1))
        elif kind == 4:
            program.append((c_jr(1), 1))
        elif kind == 5:
            program.append((c_mv(10, 11), 1))
        elif kind == 6:
            program.append((c_addi(10, 1), 1))
        else:
            program.append((c_li(11, 2), 1))
    window = build_window(program, 0x17000)
    result = await ifu_agent.fetch(FetchRequest(window))
    assert result.beat is not None
    expected, prediction, *_ = aligned_lanes(window, 0)
    assert (result.redirect is not None) == bool(prediction.redirect.valid)


@pytest.mark.feature("IFU-TOP-002")
async def test_full_width_control_flow_families(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.isa import beq
    from suites.frontend.ifu.testbenches.ifu.model.isa import jalr
    from suites.frontend.ifu.testbenches.ifu.model.isa import load_bytes
    from suites.frontend.ifu.testbenches.ifu.model.isa import store_bytes
    program = [
        (jal(1, 0x40), 0),
        (jalr(1, 5, 0), 0),
        (0x00008067, 0),  # ret
        (beq(5, 6, 8), 0),
        (addi(5, 0, 1), 0),
        (load_bytes(2, 6, 7, 4), 0),
        (store_bytes(2, 7, 8, 4), 0),
        (jal(0, -4), 0),
    ]
    window = build_window(program, 0x18000)
    result = await ifu_agent.fetch(FetchRequest(window))
    assert result.beat is not None
    expected, prediction, *_ = aligned_lanes(window, 0)
    assert (result.redirect is not None) == bool(prediction.redirect.valid)


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-004")
async def test_high_aligned_lane_owned_by_the_second_block(ifu_agent):
    first = build_window(dense_compressed(3), 0x19000, ftq0=(0, 3))
    result = await ifu_agent.fetch(FetchRequest(first))
    assert result.beat is not None and result.redirect is None
    await ifu_agent.idle(3)
    second = build_window(dense_compressed(32), 0x19100, split=16, ftq0=(0, 4), ftq1=(0, 5))
    result = await ifu_agent.fetch(FetchRequest(second))
    assert result.beat is not None and result.redirect is None
    assert ifu_agent.records[-1].shift == 3


@pytest.mark.feature("IFU-TOP-009")
async def test_uncache_bus_error_is_attached_to_the_instruction(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi as enc_addi
    returned = enc_addi(10, 5)
    window = build_window([(addi(5, 0, 1), 0)], 0xC800, pbmt0=1)
    result = await ifu_agent.read_uncached(FetchRequest(window, physical_address=0x2468), BusReply(returned, corrupt=1))
    beat, redirect = result.beat, result.redirect
    assert beat is not None
    assert beat.exception_type == 5  # corrupted transfer -> hardware error
    assert beat.exception_mask == beat.enq == 1


@pytest.mark.feature("IFU-TOP-009")
async def test_uncache_cross_page_resend_reassembles_the_instruction(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi as enc_addi
    full = addi(5, 0, 1)
    low = full & 0xFFFF
    high = (full >> 16) & 0xFFFF
    first = build_window([(addi(9, 0, 9), 0)], 0xC000, pbmt0=1)
    uid = await ifu_agent.send_uncached(FetchRequest(first, physical_address=0x8000))
    # Retain the original non-page-final stimulus as explicit peer-port stress.
    # It is not a reachable InstrUncache needResend history; legal peers are
    # covered separately, without weakening UID/schema/checker/tail checks.
    await ifu_agent.characterize_reply(uid, BusReply(low, need_resend=1))
    # The resend must not enqueue a half instruction; it only records the
    # continuation and asks the FTQ to refetch from the next page.
    result = await ifu_agent.collect(uid, max_cycles=10)
    assert result.beat is None and result.resend == 1
    redirect = result.redirect
    assert redirect is not None and redirect.target == 0xC000 + 2
    assert redirect.offset == redirect.taken == 0
    await ifu_agent.idle(3)
    second = build_window([(addi(9, 0, 8), 0)], 0xC002, pbmt0=1)
    result = await ifu_agent.read_uncached(FetchRequest(second, physical_address=0x8000), BusReply(high))
    beat, redirect = result.beat, result.redirect
    assert beat is not None, "assembled instruction was not enqueued"
    assert beat.enq == beat.valid == 1
    assert beat.instrs[0] == full and beat.is_rvc[0] == 0
    assert redirect is not None
    assert redirect.target == 0xC002 + 2
    assert redirect.is_rvc == redirect.offset == 0


def random_compressed(rng) -> int:
    from suites.frontend.ifu.testbenches.ifu.model import cenc
    kind = rng.randrange(12)
    if kind == 0:
        return cenc.c_addi(rng.randrange(1, 32), rng.randrange(-32, 32))
    if kind == 1:
        return cenc.c_li(rng.randrange(0, 32), rng.randrange(-32, 32))
    if kind == 2:
        return cenc.c_lui(rng.choice([rd for rd in range(1, 32) if rd != 2]),
                           rng.choice([imm for imm in range(-32, 32) if imm != 0]))
    if kind == 3:
        return cenc.c_addi4spn(8 + rng.randrange(8), 4 * rng.randrange(1, 256))
    if kind == 4:
        return cenc.c_srli(8 + rng.randrange(8), rng.randrange(64))
    if kind == 5:
        return cenc.c_srai(8 + rng.randrange(8), rng.randrange(64))
    if kind == 6:
        return cenc.c_andi(8 + rng.randrange(8), rng.randrange(-32, 32))
    if kind == 7:
        return rng.choice([cenc.c_sub, cenc.c_xor, cenc.c_or, cenc.c_and])(
            8 + rng.randrange(8), 8 + rng.randrange(8))
    if kind == 8:
        return rng.choice([cenc.c_lw, cenc.c_sw])(
            8 + rng.randrange(8), 8 + rng.randrange(8), 4 * rng.randrange(32))
    if kind == 9:
        return rng.choice([cenc.c_ld, cenc.c_sd, cenc.c_fld, cenc.c_fsd])(
            8 + rng.randrange(8), 8 + rng.randrange(8), 8 * rng.randrange(32))
    if kind == 10:
        return rng.choice([cenc.c_lwsp, cenc.c_swsp])(
            rng.randrange(1, 32), 4 * rng.randrange(64))
    if rng.random() < 0.5:
        return cenc.c_addi16sp(16 * rng.choice(
            [value for value in range(-31, 32) if value != 0]))
    return cenc.c_mv(rng.randrange(1, 32), rng.randrange(1, 32))


@pytest.mark.feature("IFU-TOP-002")
async def test_randomized_full_window_covers_address_and_data_bits(ifu_agent):
    import random
    rng = random.Random(0xF3C4)
    for _ in range(5):
        await ifu_agent.reset()
        program = [(random_compressed(rng), 1) for _ in range(32)]
        base = rng.getrandbits(50) & ~0x3F
        window = build_window(program, base, ftq0=(rng.randrange(2), rng.randrange(64)))
        result = await ifu_agent.fetch(FetchRequest(window))
        assert result.redirect is None and result.beat is not None


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-005")
async def test_full_width_instructions_at_high_instruction_indices(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_beqz
    from suites.frontend.ifu.testbenches.ifu.model.isa import beq
    for count in (24, 28, 30):
        for word, label in ((jal(1, 0x20), "jal"),
                            (0x000080E7, "jalr"),
                            (0x00008067, "ret"),
                            (beq(5, 6, 8), "branch")):
            program = [(c_addi(8 + (index % 8), index % 5 + 1), 1)
                       for index in range(count)]
            program.append((word, 0))
            window = build_window(program, 0x1C000 + count * 0x100)
            if word == beq(5, 6, 8):
                # A conditional branch not taken is legal, so the window can
                # be checked as a clean fetch at the high lane.
                await ifu_agent.reset()
                result = await ifu_agent.fetch(FetchRequest(window))
                assert result.beat is not None and result.redirect is None
                continue
            await ifu_agent.reset()
            result = await ifu_agent.fetch(FetchRequest(window))
            assert result.beat is not None and result.redirect is not None


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-004")
async def test_block_one_instruction_at_the_highest_lane_with_pc_carry(ifu_agent):
    """A second-block instruction can land on lane 34 after a 3-bank shift.

    Its PC lower part is formed from the block start plus the instruction
    offset; when that sum carries into bit 11 of the halfword coordinate, the
    upper PC bits must be incremented rather than reused.  This is the only
    way to reach that high-lane carry path in the generated PC assembly.
    """

    first = build_window(dense_compressed(3), 0x1D000, ftq0=(1, 9))
    result = await ifu_agent.fetch(FetchRequest(first))
    assert result.beat is not None and result.redirect is None
    await ifu_agent.idle(3)
    # Block 1 starts at halfword 0x3E2; its last instruction (lane 34 after
    # the shift) has block offset 30, so start + offset carries past 0x3FF
    # into bit 11 of the halfword PC coordinate.
    base = 0x1D7C2
    second = build_window(dense_compressed(32), base, split=1,
                          ftq0=(1, 10), ftq1=(1, 11))
    result = await ifu_agent.fetch(FetchRequest(second))
    assert result.beat is not None and result.redirect is None
    assert ifu_agent.records[-1].shift == 3
    assert result.beat.ftq[34] == (1, 11)


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-004")
async def test_first_block_instruction_at_the_highest_lane_with_pc_carry(ifu_agent):
    """The symmetric high-lane carry for an instruction owned by block 0."""

    first = build_window(dense_compressed(3), 0x1E000, ftq0=(1, 19))
    result = await ifu_agent.fetch(FetchRequest(first))
    assert result.beat is not None and result.redirect is None
    await ifu_agent.idle(3)
    # Block 0 spans all 32 slots: start halfword 0x3E2 + last offset 31
    # carries past 0x3FF while the instruction still belongs to block 0.
    base = 0x1E7C2
    second = build_window(dense_compressed(32), base, ftq0=(1, 20))
    result = await ifu_agent.fetch(FetchRequest(second))
    assert result.beat is not None and result.redirect is None
    assert ifu_agent.records[-1].shift == 3
    assert result.beat.ftq[34] == (1, 20)


def build_cfi_window(base: int, lane: int, kind: str) -> Window:
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_beqz
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_j
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_jalr
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_jr
    from suites.frontend.ifu.testbenches.ifu.model.isa import beq
    rvi_kinds = {
        "direct": jal(1, 0x20),
        "conditional": beq(5, 6, 8),
        "indirect": 0x000080E7,  # jalr x1, 0(x1)
    }
    rvc_kinds = {
        "rvc_direct": c_j(4),
        "rvc_conditional": c_beqz(8, 4),
        "rvc_jalr": c_jalr(1),
        "rvc_jr": c_jr(1),
    }
    if kind in rvi_kinds:
        # A 32-bit instruction needs two slots; 31 compressed instructions
        # plus one replaced by the RVI still fit exactly.
        program = [(c_addi(8 + (index % 8), index % 5 + 1), 1) for index in range(31)]
        program[lane] = (rvi_kinds[kind], 0)
    else:
        count = 32 if lane == 31 else 31
        program = [(c_addi(8 + (index % 8), index % 5 + 1), 1) for index in range(count)]
        program[lane] = (rvc_kinds[kind], 1)
    return build_window(program, base)


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-005")
async def test_control_flow_classification_at_every_instruction_index(ifu_agent):
    """Every instruction lane decodes its own branch class and operands.

    Branches, jumps, returns and non-CFI instructions are classified by the
    predecoder in stage 1 for every lane.  This sweep places each class at
    each instruction index so that the per-lane attribute decoders and their
    RVC/RVI operand selection are all exercised.
    """

    kinds = ("direct", "conditional", "indirect", "rvc_direct", "rvc_conditional",
             "rvc_jalr", "rvc_jr")
    for lane in range(31):
        for kind in kinds:
            await ifu_agent.reset()
            window = build_cfi_window(0x20000 + lane * 0x200, lane, kind)
            result = await ifu_agent.fetch(FetchRequest(window))
            assert result.beat is not None, (lane, kind)
            _, prediction, *_ = aligned_lanes(window, 0)
            assert (result.redirect is not None) == bool(prediction.redirect.valid), (lane, kind)


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-005")
async def test_cross_block_split_position_sweep(ifu_agent):
    """Sweep the split point so every lane can own a cross-block instruction."""

    for split in range(1, 31):
        await ifu_agent.reset()
        # 31 compressed instructions with one replaced by a 32-bit one still
        # fill exactly 32 halfword slots.
        program = [(c_addi(8 + (index % 8), index % 5 + 1), 1) for index in range(31)]
        program[split - 1] = (addi(5, 0, 1), 0)
        window = build_window(program, 0x30000 + split * 0x200, split=split,
                              ftq0=(1, split), ftq1=(1, split + 1))
        result = await ifu_agent.fetch(FetchRequest(window))
        assert result.beat is not None
        assert result.beat.ftq[split] == (1, split + 1)


@pytest.mark.feature("IFU-TOP-011")
async def test_instruction_split_across_two_fetch_windows_is_assembled(ifu_agent):
    """A 32-bit instruction may straddle the 64-byte block boundary.

    The first window ends after its low half and cannot enqueue it; the IFU
    records the PC and low half.  The following window starts with the high
    half and must enqueue the single assembled instruction (not two halves),
    with the PC of the original instruction.

    This is the full-window-end position (slot 31); the other reachable carry
    positions and the non-control-flow instruction classes are swept by
    ``test_carry_position_and_instruction_class_sweep``.
    """

    word = addi(5, 0, 1)
    program = [(c_addi(8 + (index % 8), index % 5 + 1), 1) for index in range(31)]
    program.append((word, 0))
    first = build_window(program, 0x40000, truncate=1, ftq0=(0, 7))
    result = await ifu_agent.fetch(FetchRequest(first))
    assert result.redirect is None and result.beat is not None
    assert result.beat.enq == (1 << 31) - 1  # the incomplete instruction is not enqueued
    second = build_window([(c_addi(9, 1), 1), (addi(6, 0, 2), 0)],
                          0x40040, carry_word=word, ftq0=(0, 8))
    result = await ifu_agent.fetch(FetchRequest(second))
    assert result.redirect is None and result.beat is not None
    assert ifu_agent.records[-1].shift == 3
    assert result.beat.instrs[3] == word
    assert result.beat.is_rvc[3] == 0
    assert result.beat.end_off[3] == 0


@pytest.mark.feature("IFU-TOP-011")
@pytest.mark.parametrize('size0,lead_rvi', [
    (size0, lead_rvi)
    for size0 in range(1, 32, 2)
    for lead_rvi in (0, 1)
    if not (size0 == 1 and lead_rvi == 1)
], ids=lambda value: str(value))
@pytest.mark.parametrize('word', [
    addi(5, 0, 1),            # ALU immediate
    add(5, 0, 1),             # ALU register-register
    lui(5, 1),                # upper immediate
    mul(5, 0, 1),             # M extension
    load_bytes(2, 5, 4, 0),   # load
    store_bytes(2, 0, 5, 0),  # store
    ebreak(),                 # system
], ids=['alu_i', 'alu_r', 'lui', 'mul', 'load', 'store', 'system'])
async def test_carry_position_and_instruction_class_sweep(ifu_agent, size0, lead_rvi, word):
    """Every position where a window can end inside a full-width instruction.

    Only a misprediction can end a fetch before the 32-slot window end: an
    invalid-taken prediction reports the low half of a 32-bit instruction as
    the taken position, so the block stops there and the recovery fetch starts
    at the high half.  Sweeping the odd block sizes ``1..31`` therefore covers
    every reachable carry position.  ``lead_rvi`` puts one 4-byte instruction in
    front so the number of enqueued instructions is odd and the assembled word
    also lands on write-bank lanes 1/3 (all-RVC prefixes only reach lanes 0/2).

    The carried word must survive unchanged with its original PC, so the seven
    non-control-flow classes below cover the ISA families that reach the
    assembler.  Control-flow classes are excluded on purpose: predicting a
    branch/jump taken at its own start is a *legal* prediction, and a producer
    would then deliver the whole instruction, so "truncated CFI" is not a legal
    input.  Those classes are covered by IFU-TOP-002/005/009 where the
    prediction and the redirect are defined.  Classes whose upper halfword has
    low bits ``11`` (for example ``addi x5, x6, 1``) are also excluded: they
    trip the open R-14 defect, whose leaf and top-level cases already assert
    that family and remain FAIL.
    """

    if lead_rvi and size0 < 3:
        pytest.skip("a 4-byte lead needs at least two prefix halfword slots")

    base = 0x50000 + 0x200 * size0 + (0x100 if lead_rvi else 0)
    if lead_rvi:
        program = [(addi(7, 0, 3), 0)]
        program += [(c_addi(8 + (index % 8), index % 5 + 1), 1)
                    for index in range(size0 - 3)]
    else:
        program = [(c_addi(8 + (index % 8), index % 5 + 1), 1)
                   for index in range(size0 - 1)]
    program.append((word, 0))
    first = build_window(program, base, truncate=1, truncate_at=size0,
                         taken0=1, ftq0=(0, 7))
    result = await ifu_agent.fetch(FetchRequest(first))
    assert result.beat is not None and result.redirect is not None
    # The half instruction stays out of the enqueue and the recovery starts at
    # its high half, one halfword past its own PC.
    assert result.beat.valid & (1 << (size0 - 1)) == 0
    assert result.redirect.target == base + 2 * size0
    await ifu_agent.idle(4)

    carry_pc = base + 2 * (size0 - 1)
    second = build_window([(c_addi(9, 1), 1), (addi(6, 0, 2), 0)],
                          base + 2 * size0, carry_word=word, ftq0=(0, 8))
    result = await ifu_agent.fetch(FetchRequest(second))
    assert result.beat is not None and result.redirect is None
    # The write-bank shift is set by the instructions the first window
    # enqueued; the two prefix shapes together cover all four lanes.
    prefix_instructions = size0 - 2 if lead_rvi else size0 - 1
    lane = prefix_instructions & 3
    assert ifu_agent.records[-1].shift == lane
    assert result.beat.instrs[lane] == word
    assert result.beat.is_rvc[lane] == 0
    assert result.beat.end_off[lane] == 0
    from suites.frontend.ifu.testbenches.ifu.model.fetch import xor_fold
    assert result.beat.foldpc[lane] == xor_fold((carry_pc & ((1 << 50) - 1)) >> 1, 10)


@pytest.mark.feature("IFU-TOP-011")
async def test_split_instruction_reaches_ibuffer_with_its_own_pc(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi
    word = 0x00100293
    first = build_window([(c_addi(8 + (index % 8), 1), 1) for index in range(31)]
                         + [(word, 0)], 0x41000, truncate=1, ftq0=(0, 9))
    assert (await ifu_agent.fetch(FetchRequest(first))).beat is not None
    second = build_window([(c_addi(9, 1), 1)], 0x41040, carry_word=word, ftq0=(0, 10))
    result = await ifu_agent.fetch(FetchRequest(second))
    assert result.beat is not None and result.redirect is None
    assert ifu_agent.records[-1].shift == 3
    # The assembled instruction's PC is one halfword before the new block and
    # is folded into the predictor PC field.
    from suites.frontend.ifu.testbenches.ifu.model.fetch import xor_fold
    assert result.beat.foldpc[3] == xor_fold((0x41040 - 2) >> 1, 10)


@pytest.mark.feature("IFU-TOP-008")
async def test_second_block_ecc_corruption_is_attached_there(ifu_agent):
    program = [(c_addi(8 + (index % 8), 1), 1) for index in range(8)]
    window = build_window(program, 0x42000, split=4, ftq0=(0, 11), ftq1=(0, 12))
    result = await ifu_agent.fetch(FetchRequest(window), corruption=(0, 0, 1, 0))
    assert result.beat is not None and result.redirect is None
    assert result.beat.exception_type == 5
    # The exception lands on the first instruction of the second block.
    assert result.beat.exception_mask == 1 << 4


@pytest.mark.feature("IFU-TOP-005")
async def test_block_one_jump_fault_redirects_with_block_one_identity(ifu_agent):
    program = [(c_addi(8 + (index % 8), 1), 1) for index in range(8)]
    program[5] = (0x000080E7, 0)  # jalr x1, 0(x1) in the second block
    window = build_window(program, 0x43000, split=4, ftq0=(0, 13), ftq1=(0, 14))
    result = await ifu_agent.fetch(FetchRequest(window))
    assert result.beat is not None and result.redirect is not None
    # The redirect is attributed to the second fetch block.
    assert result.redirect.ftq == (0, 14)
    assert result.redirect.pc == 0x43000 + 2 * 4  # start PC of the owning block


@pytest.mark.feature("IFU-TOP-004")
async def test_ibuf_write_pointer_wraps_across_many_fetches(ifu_agent):
    for round_index in range(12):
        window = build_window(dense_compressed(5), 0x44000 + round_index * 0x100,
                              ftq0=(0, round_index))
        result = await ifu_agent.fetch(FetchRequest(window))
        assert result.beat is not None and result.redirect is None, round_index
        assert ifu_agent.records[-1].shift == (round_index * 5) & 3
        await ifu_agent.idle(4)


@pytest.mark.feature("IFU-TOP-009")
async def test_uncache_fetch_after_an_alignment_shift(ifu_agent):
    """The uncache lane follows the same write-bank alignment as cached fetches."""

    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi as enc_addi
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_li as enc_li
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_sw as enc_sw
    for pre_count in (1, 2, 3):
        await ifu_agent.reset()
        pre = build_window(dense_compressed(pre_count), 0x45000, ftq0=(1, 20))
        result = await ifu_agent.fetch(FetchRequest(pre))
        assert result.beat is not None and result.redirect is None
        await ifu_agent.idle(3)
        window = build_window([(addi(5, 0, 1), 0)], 0x45100,
                              pbmt0=1, ftq0=(1, 21))
        uid = await ifu_agent.send_uncached(FetchRequest(window, physical_address=0x12000))
        returned = (enc_addi, enc_li, enc_sw)[pre_count - 1](
            *({1: (10, 5), 2: (11, -2), 3: (10, 11, 4)}[pre_count]))
        await ifu_agent.reply(uid, BusReply(returned))
        result = await ifu_agent.collect(uid)
        beat, redirect = result.beat, result.redirect
        assert beat is not None, pre_count
        assert beat.enq == 1 << pre_count, (pre_count, bin(beat.enq))
        assert beat.valid == 1 << pre_count
        assert beat.instrs[pre_count] == expand(returned).bits
        assert beat.is_rvc[pre_count] == 1
        assert redirect is not None and redirect.target == 0x45100 + 2


@pytest.mark.feature("IFU-TOP-009")
async def test_uncache_fetch_of_a_jump_redirects_with_its_attribute(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_j
    from suites.frontend.ifu.testbenches.ifu.model.isa import beq
    returned = c_j(8)
    window = build_window([(addi(5, 0, 1), 0)], 0x46000, pbmt0=1)
    result = await ifu_agent.read_uncached(FetchRequest(window, physical_address=0x14000), BusReply(returned))
    beat, redirect = result.beat, result.redirect
    assert beat is not None and redirect is not None
    assert beat.instrs[0] == expand(returned).bits
    assert redirect.branch_type == 2  # direct
    assert redirect.is_rvc == 1
    assert redirect.target == 0x46000 + 2
    assert redirect.taken == 0


@pytest.mark.feature("IFU-TOP-009")
async def test_uncache_fetch_of_a_full_width_branch(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.isa import beq
    returned = beq(5, 6, 8)
    window = build_window([(addi(9, 0, 1), 0)], 0x47000, pbmt0=1)
    result = await ifu_agent.read_uncached(FetchRequest(window, physical_address=0x16000), BusReply(returned))
    beat, redirect = result.beat, result.redirect
    assert beat is not None and redirect is not None
    assert beat.instrs[0] == returned
    assert beat.is_rvc[0] == 0
    assert redirect.branch_type == 1  # conditional
    assert redirect.offset == 1
    # The uncached instruction is the first (unshifted) lane; the sequential
    # target is the next 4-byte PC after the fetched block start.
    assert redirect.target == 0x47000 + 4


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-004")
async def test_cross_block_instruction_shifted_to_high_lanes(ifu_agent):
    """A 3-bank shift moves the block-crossing instruction to lanes 30..33."""

    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi as enc_addi
    for split in (28, 29, 30, 31):
        await ifu_agent.reset()
        first = build_window(dense_compressed(3), 0x48000 + split * 0x100, ftq0=(0, 30))
        result = await ifu_agent.fetch(FetchRequest(first))
        assert result.beat is not None and result.redirect is None
        await ifu_agent.idle(3)
        program = [(enc_addi(8 + (index % 8), index % 5 + 1), 1) for index in range(31)]
        program[split - 1] = (addi(5, 0, 1), 0)
        window = build_window(program, 0x49000 + split * 0x100, split=split,
                              ftq0=(0, 31), ftq1=(0, 32))
        result = await ifu_agent.fetch(FetchRequest(window))
        assert result.beat is not None and result.redirect is None
        assert ifu_agent.records[-1].shift == 3
        lane = split - 1 + 3
        assert result.beat.ftq[lane] == (0, 32)


@pytest.mark.feature("IFU-TOP-002")
async def test_sparse_encodings_at_the_highest_lanes(ifu_agent):
    """Reserved/hint encodings still reach the decoders at high lanes."""

    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi as enc_addi
    encodings = (0x9002, 0x8002, 0x6081)  # c.ebreak, reserved c.jr x0, c.mop hint
    for encoding in encodings:
        await ifu_agent.reset()
        first = build_window(dense_compressed(3), 0x4A000, ftq0=(1, 1))
        result = await ifu_agent.fetch(FetchRequest(first))
        assert result.beat is not None and result.redirect is None
        await ifu_agent.idle(3)
        program = [(enc_addi(8 + (index % 8), index % 5 + 1), 1) for index in range(32)]
        program[30] = (encoding, 1)
        window = build_window(program, 0x4A100, ftq0=(1, 2))
        result = await ifu_agent.fetch(FetchRequest(window))
        assert result.beat is not None
        assert ifu_agent.records[-1].shift == 3


@pytest.mark.feature("IFU-TOP-009")
async def test_uncache_fetch_of_indirect_control_transfers(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_bnez
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_jalr
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_jr
    from suites.frontend.ifu.testbenches.ifu.model.isa import jal as isa_jal
    from suites.frontend.ifu.testbenches.ifu.model.isa import jalr as isa_jalr
    for returned in (c_jalr(1), c_jr(1), 0x8002, c_bnez(8, 4), isa_jal(1, 0x40),
                     isa_jalr(1, 5, 0)):
        await ifu_agent.reset()
        window = build_window([(addi(5, 0, 1), 0)], 0x4B000, pbmt0=1)
        result = await ifu_agent.read_uncached(FetchRequest(window, physical_address=0x18000), BusReply(returned))
        beat, redirect = result.beat, result.redirect
        assert beat is not None and redirect is not None
        expected = expand(returned)
        assert beat.instrs[0] == (returned if expected.ill else expected.bits)
        if returned == 0x8002:
            assert beat.exception_type == 4  # reserved encoding stays illegal
        else:
            from suites.frontend.ifu.testbenches.ifu.model.fetch import branch_info
            from suites.frontend.ifu.testbenches.ifu.model.isa import is_compressed
            expected_class, expected_ras, _ = branch_info(returned, int(is_compressed(returned)))
            assert redirect.branch_type == expected_class
            assert redirect.ras_action == expected_ras


@pytest.mark.feature("IFU-TOP-002")
async def test_sparse_encodings_at_every_lane(ifu_agent):
    """The fast non-CFI decode path must work at every aligned lane."""

    for encoding in (0x9002, 0x8002):
        await ifu_agent.reset()
        window = build_window([(encoding, 1) for _ in range(32)], 0x4C000)
        result = await ifu_agent.fetch(FetchRequest(window))
        assert result.beat is not None and result.redirect is None
        # A shifted window also places the encoding on the high lanes 32..34.
        await ifu_agent.idle(3)
        first = build_window(dense_compressed(3), 0x4C100, ftq0=(1, 3))
        result = await ifu_agent.fetch(FetchRequest(first))
        assert result.beat is not None and result.redirect is None
        await ifu_agent.idle(3)
        window2 = build_window([(encoding, 1) for _ in range(32)], 0x4C200)
        result = await ifu_agent.fetch(FetchRequest(window2))
        assert result.beat is not None and result.redirect is None
        assert ifu_agent.records[-1].shift == 3


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-005")
async def test_conditional_branch_at_the_highest_aligned_lanes(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_beqz
    await ifu_agent.reset()
    first = build_window(dense_compressed(3), 0x4D000, ftq0=(1, 5))
    result = await ifu_agent.fetch(FetchRequest(first))
    assert result.beat is not None and result.redirect is None
    await ifu_agent.idle(3)
    program = [(c_addi(8 + (index % 8), 1), 1) for index in range(32)]
    for index in (28, 29, 30, 31):
        program[index] = (c_beqz(8, 4), 1)
    window = build_window(program, 0x4D100)
    result = await ifu_agent.fetch(FetchRequest(window))
    assert result.beat is not None and result.redirect is None
    assert ifu_agent.records[-1].shift == 3


@pytest.mark.feature("IFU-TOP-005")
@pytest.mark.feature("IFU-TOP-004")
async def test_redirect_updates_the_ibuf_pointer_across_the_wrap(ifu_agent):
    for round_index in range(11):
        window = build_window(dense_compressed(5), 0x4E000 + round_index * 0x100,
                              ftq0=(0, round_index))
        result = await ifu_agent.fetch(FetchRequest(window))
        assert result.beat is not None and result.redirect is None, round_index
        assert ifu_agent.records[-1].shift == (round_index * 5) & 3
        await ifu_agent.idle(4)
    # 55 instructions are enqueued; a faulting jump now performs the wrapped
    # pointer update (previous + count crosses the 48-instruction window).
    fault = build_window([(c_addi(8, 1), 1), (jal(1, 0x40), 0)], 0x4F000)
    result = await ifu_agent.fetch(FetchRequest(fault))
    assert result.beat is not None and result.redirect is not None
    assert ifu_agent.records[-1].shift == 55 & 3
    _, prediction, *_ = aligned_lanes(fault, 55 & 3)
    # The redirect carries the same instruction count the pointer adopts.
    next_shift = (55 + sum(prediction.fixed_instr_valid)) & 3
    await ifu_agent.idle(4)
    after = build_window(dense_compressed(2), 0x4F100, ftq0=(0, 40))
    result = await ifu_agent.fetch(FetchRequest(after))
    assert result.beat is not None and result.redirect is None
    assert ifu_agent.records[-1].shift == next_shift


@pytest.mark.feature("IFU-TOP-009")
async def test_uncache_redirect_after_many_enqueues(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi as enc_addi
    for round_index in range(12):
        window = build_window(dense_compressed(5), 0x50000 + round_index * 0x100,
                              ftq0=(0, round_index))
        result = await ifu_agent.fetch(FetchRequest(window))
        assert result.beat is not None and result.redirect is None
        assert ifu_agent.records[-1].shift == (round_index * 5) & 3
        await ifu_agent.idle(4)
    # 60 instructions are resident; the uncache redirect adds one more and
    # crosses the pointer's wrap window.
    window = build_window([(addi(5, 0, 1), 0)], 0x50100, pbmt0=1)
    uid = await ifu_agent.send_uncached(FetchRequest(window, physical_address=0x1A000))
    returned = enc_addi(10, 5)
    await ifu_agent.reply(uid, BusReply(returned))
    result = await ifu_agent.collect(uid)
    beat, redirect = result.beat, result.redirect
    assert beat is not None and redirect is not None
    assert redirect.target == 0x50100 + 2


@pytest.mark.feature("IFU-TOP-005")
async def test_prediction_into_the_middle_of_an_instruction_is_invalid_taken(ifu_agent):
    """The predictor may point at the low half of a 32-bit instruction.

    When the taken position starts a 32-bit instruction but the fetched block
    ends after that low half, the prediction is invalid.  The IFU must discard
    the speculative instructions, report invalid-taken with the instruction's
    PC, and let the next fetch resume at that PC to assemble the full word.
    """

    program = [(addi(5, 0, 1), 0)] + [(c_addi(8 + (index % 8), 1), 1) for index in range(30)]
    window = build_window(program, 0x51000, split=1, taken0=1, ftq0=(0, 31))
    result = await ifu_agent.fetch(FetchRequest(window))
    assert result.beat is not None and result.beat.valid == 0  # nothing from the bad fetch is enqueued
    redirect = result.redirect
    assert redirect is not None
    _, prediction, *_ = aligned_lanes(window, 0)
    assert prediction.redirect.invalid_taken == 1
    assert redirect.taken == 0
    assert redirect.branch_type == 0
    assert redirect.can_train == 1  # invalid-taken is trainable
    assert redirect.target == 0x51000 + 2  # resume at the real half-instruction PC
    # The recorded half-RVI carries the low half of that instruction.
    await ifu_agent.idle(4)
    word = program[0][0]
    resume = build_window([(c_addi(9, 1), 1), (addi(6, 0, 2), 0)],
                          0x51002, carry_word=word, ftq0=(0, 32))
    result = await ifu_agent.fetch(FetchRequest(resume))
    assert result.redirect is None and result.beat is not None
    assert result.beat.instrs[0] == word
    assert result.beat.is_rvc[0] == 0


@pytest.mark.feature("IFU-TOP-005")
@pytest.mark.feature("IFU-TOP-011")
@pytest.mark.parametrize('rs1', [0, 6], ids=['normal-upper-half', 'upper-half-low11'])
async def test_recovered_half_instruction_keeps_its_completing_ftq_block(ifu_agent, rs1):
    """Retained interface recovery pressure; not a proven full-FTQ producer history.

    Non-taken short blocks below violate the producer fall-through extent. Keep
    their original bytes/FAIL, and use test_ifu_producer_transactions.py for the
    independently constrained upstream controls instead of promoting this case.
    """
    from suites.frontend.ifu.testbenches.ifu.model.isa import beq
    word = addi(5, rs1, 1)
    # Both fit the maximum extent, but the non-taken second block is too short
    # for the real fall-through rule. InvalidTaken discards both at this port.
    program = [(word, 0)]
    first = build_window(program, 0x103C, split=1, taken0=1, ftq0=(0, 31), ftq1=(0, 32))
    result = await ifu_agent.fetch(FetchRequest(first))
    assert result.beat is not None and result.beat.valid == 0
    assert result.redirect is not None and result.redirect.target == 0x103E
    await ifu_agent.idle(4)
    # The second block has a legal taken extent. The first non-taken block is
    # still synthetic; only fixing the second was insufficient reachability proof.
    resume = build_window([(c_addi(9, 1), 1), (beq(0, 0, 8), 0)], 0x103E,
                          carry_word=word, split=1, taken1=1, ftq0=(0, 32), ftq1=(0, 33))
    result = await ifu_agent.fetch(FetchRequest(resume))
    completed = result.beat
    assert completed is not None and result.redirect is None
    assert completed.instrs[0] == word and completed.end_off[0] == 0
    assert completed.ftq[0] == (0, 32), 'carry ends in block0, never block1'


@pytest.mark.feature("IFU-TOP-005")
async def test_prediction_on_the_second_half_belongs_to_the_enclosing_instruction(ifu_agent):
    """A taken position inside an instruction's high half is not invalid-taken.

    The fetch block ends after the instruction's second half, so the whole
    instruction is present; the prediction is attached to the last valid
    instruction start (the enclosing RVI), which is a non-CFI taken fault.
    """

    program = [(c_addi(8 + (index % 8), 1), 1) for index in range(30)]
    program.append((addi(5, 0, 1), 0))
    window = build_window(program, 0x52000, taken0=1, ftq0=(0, 32))
    result = await ifu_agent.fetch(FetchRequest(window))
    assert result.beat is not None and result.redirect is not None
    _, prediction, *_ = aligned_lanes(window, 0)
    assert prediction.redirect.invalid_taken == 0
    assert prediction.redirect.not_cfi_taken == 1
    assert result.redirect.target == 0x52000 + 2 * 30 + 4


@pytest.mark.feature("IFU-TOP-009")
async def test_uncache_pointer_wrap_after_forty_seven_instructions(ifu_agent):
    from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi as enc_addi
    for count in (47, 48):
        await ifu_agent.reset()
        remaining = count
        round_index = 0
        while remaining:
            take = min(5, remaining)
            window = build_window(dense_compressed(take),
                                  0x53000 + round_index * 0x100, ftq0=(0, round_index))
            result = await ifu_agent.fetch(FetchRequest(window))
            assert result.beat is not None and result.redirect is None
            assert ifu_agent.records[-1].shift == (count - remaining) & 3
            remaining -= take
            round_index += 1
            await ifu_agent.idle(4)
        window = build_window([(addi(5, 0, 1), 0)], 0x53100, pbmt0=1)
        result = await ifu_agent.read_uncached(FetchRequest(window, physical_address=0x1C000), BusReply(enc_addi(10, 5)))
        beat, redirect = result.beat, result.redirect
        assert beat is not None and redirect is not None
        assert redirect.target == 0x53100 + 2
