"""IFU top level: fetch-window reconstruction, enqueue backpressure and redirect."""

from __future__ import annotations

import pytest

from suites.frontend.ifu.legacy_pins import P
from suites.frontend.ifu.model.cenc import c_addi
from suites.frontend.ifu.model.cenc import c_li
from suites.frontend.ifu.model.cenc import c_lw
from suites.frontend.ifu.model.cenc import c_sw
from suites.frontend.ifu.model.fetch import LANES
from suites.frontend.ifu.model.fetch import Window
from suites.frontend.ifu.model.fetch import aligned_lanes
from suites.frontend.ifu.model.fetch import build_window
from suites.frontend.ifu.model.rvc import expand
from suites.frontend.ifu.model.isa import addi
from suites.frontend.ifu.model.isa import jal
from suites.frontend.ifu.model.isa import nop
from suites.frontend.ifu.model.isa import sub


def line_bits(line) -> int:
    return sum((half & 0xFFFF) << (16 * index) for index, half in enumerate(line))


def apply_window(harness, window: Window, *, request_valid: int = 1,
                 ibuffer_ready: int = 1, trigger=None) -> None:
    start0 = window.start0_pc
    start1 = window.start1_pc
    trigger = trigger or {}
    harness.set(
        io_fromFtq_redirect_valid=0,
        io_fromFtq_flushFromBpu_s3_valid=0,
        io_fromFtq_flushFromBpu_s3_bits_flag=0,
        io_fromFtq_flushFromBpu_s3_bits_value=0,
        io_fromICache_req_valid=request_valid,
        io_fromICache_req_bits_maybeRvcMap=window.map,
        io_fromICache_req_bits_firstRange=(1 << window.size0) - 1,
        io_fromICache_req_bits_totalRange=(1 << (window.size0 + window.size1)) - 1,
        io_fromICache_req_bits_info_0_startVAddr_addr=start0 >> 1,
        io_fromICache_req_bits_info_0_ftqIdx_flag=window.ftq0[0],
        io_fromICache_req_bits_info_0_ftqIdx_value=window.ftq0[1],
        io_fromICache_req_bits_info_0_takenCfiOffset_valid=window.taken0_valid,
        io_fromICache_req_bits_info_0_takenCfiOffset_bits=window.size0 - 1,
        io_fromICache_req_bits_info_0_size=window.size0,
        io_fromICache_req_bits_info_0_data=line_bits(window.line0),
        io_fromICache_req_bits_info_0_icacheMeta_exception_value=window.exc0,
        io_fromICache_req_bits_info_0_icacheMeta_pmpMmio=window.pmp0,
        io_fromICache_req_bits_info_0_icacheMeta_hasSatpFlush=window.satp0,
        io_fromICache_req_bits_info_0_icacheMeta_isBackendException=window.backend_exc0,
        io_fromICache_req_bits_info_0_icacheMeta_isForVSnonLeafPTE=window.vs0,
        io_fromICache_req_bits_info_0_icacheMeta_itlbPbmt=window.pbmt0,
        io_fromICache_req_bits_info_0_icacheMeta_pAddr_addr=window.paddr0,
        io_fromICache_req_bits_info_0_icacheMeta_gpAddr_addr=window.gp0 >> 1,
        io_fromICache_req_bits_info_1_valid=window.block1_valid,
        io_fromICache_req_bits_info_1_startVAddr_addr=start1 >> 1,
        io_fromICache_req_bits_info_1_ftqIdx_flag=window.ftq1[0],
        io_fromICache_req_bits_info_1_ftqIdx_value=window.ftq1[1],
        io_fromICache_req_bits_info_1_takenCfiOffset_valid=window.taken1_valid,
        io_fromICache_req_bits_info_1_takenCfiOffset_bits=max(0, window.size1 - 1),
        io_fromICache_req_bits_info_1_size=window.size1,
        io_fromICache_req_bits_info_1_data=line_bits(window.line1),
        io_fromICache_req_bits_info_1_icacheMeta_exception_value=window.exc1,
        io_fromICache_req_bits_info_1_icacheMeta_isForVSnonLeafPTE=window.vs1,
        io_fromICache_req_bits_info_1_icacheMeta_gpAddr_addr=window.gp1 >> 1,
        io_fromICache_corrupt_0_0=0,
        io_fromICache_corrupt_0_1=0,
        io_fromICache_corrupt_1_0=0,
        io_fromICache_corrupt_1_1=0,
        io_fromICache_topdown_iCacheMissBubble=0,
        io_fromICache_topdown_itlbMissBubble=0,
        io_fromICache_perf_hits_0=0,
        io_fromICache_perf_hits_1=0,
        io_fromICache_perf_isDoubleLine=0,
        io_toUncache_req_ready=0,
        io_fromUncache_resp_valid=0,
        io_fromUncache_resp_bits_data=0,
        io_fromUncache_resp_bits_corrupt=0,
        io_fromUncache_resp_bits_denied=0,
        io_fromUncache_resp_bits_needResend=0,
        io_toIBuffer_ready=ibuffer_ready,
        io_ibufferEmpty=1,
        io_backendEmpty=1,
        io_frontendTrigger_tUpdate_valid=0,
        io_frontendTrigger_tUpdate_bits_addr=0,
        io_frontendTrigger_tUpdate_bits_tdata_matchType=0,
        io_frontendTrigger_tUpdate_bits_tdata_select=0,
        io_frontendTrigger_tUpdate_bits_tdata_action=15,
        io_frontendTrigger_tUpdate_bits_tdata_chain=0,
        io_frontendTrigger_tUpdate_bits_tdata_tdata2=0,
        io_frontendTrigger_tEnableVec_0=trigger.get("enable", 0),
        io_frontendTrigger_tEnableVec_1=0,
        io_frontendTrigger_tEnableVec_2=0,
        io_frontendTrigger_tEnableVec_3=0,
        io_frontendTrigger_debugMode=0,
        io_frontendTrigger_triggerCanRaiseBpExp=trigger.get("can_raise", 0),
        io_csrFsIsOff=0,
    )


def read_beat(harness) -> dict:
    """Snapshot one IBuffer beat.

    Lane 35 is the aligned padding lane; the IFU ties its instruction vector
    to zero, so the generator removes its ``predTaken`` leaf.  Every other
    lane leaf exists and is read directly, which keeps a missing port from
    silently reading as zero.
    """

    def lane(prefix: str, index: int, *, pruned: int | None = None) -> int:
        name = prefix.format(index)
        return harness.read(name) if pruned is None else harness.read_pruned(name, pruned)

    return {
        "valid": harness.read(P.p_toIBuffer_bits_valid),
        "enq": harness.read(P.p_toIBuffer_bits_enqEnable),
        "instrs": [lane(P.io("toIBuffer_bits_instrs_{}"), index) for index in range(LANES)],
        "is_rvc": [lane(P.io("toIBuffer_bits_isRvc_{}"), index) for index in range(LANES)],
        "foldpc": [lane(P.io("toIBuffer_bits_foldpc_{}"), index) for index in range(LANES)],
        "ftq": [(lane(P.io("toIBuffer_bits_ftqPtr_{}_flag"), index),
                 lane(P.io("toIBuffer_bits_ftqPtr_{}_value"), index))
                for index in range(LANES)],
        "end_off": [lane(P.io("toIBuffer_bits_instrEndOffset_{}_offset"), index)
                    for index in range(LANES)],
        "pred": [lane(P.io("toIBuffer_bits_instrEndOffset_{}_predTaken"), index,
                      pruned=0 if index == LANES - 1 else None)
                 for index in range(LANES)],
        "prev_count": harness.read(P.p_toIBuffer_bits_prevInstrCount),
        "exception_type": harness.read(P.p_toIBuffer_bits_exceptionType_value),
        "exception_mask": harness.read(P.p_toIBuffer_bits_exceptionMask),
        "exception_cross": harness.read(P.p_toIBuffer_bits_exceptionCrossPage),
        "is_backend_exception": harness.read(P.p_toIBuffer_bits_isBackendException),
        "has_satp_flush": harness.read(P.p_toIBuffer_bits_hasSatpFlush),
        "triggered": [lane(P.io("toIBuffer_bits_triggered_{}"), index) for index in range(LANES)],
        "gp_wen": harness.read(P.p_toBackend_gpAddrMem_wen),
        "gp_addr": harness.read(P.p_toBackend_gpAddrMem_wdata_gpaddr),
        "gp_ftq": harness.read(P.p_toBackend_gpAddrMem_waddr),
        "gp_for_vs": harness.read(P.p_toBackend_gpAddrMem_wdata_isForVSnonLeafPTE),
    }


def read_redirect(harness) -> dict:
    return {
        "valid": harness.read(P.p_toFtq_wbRedirect_valid),
        "ftq": (harness.read(P.p_toFtq_wbRedirect_bits_ftqIdx_flag),
                harness.read(P.p_toFtq_wbRedirect_bits_ftqIdx_value)),
        "can_train": harness.read(P.p_toFtq_wbRedirect_bits_canTrain),
        "pc": harness.read(P.p_toFtq_wbRedirect_bits_pc),
        "taken": harness.read(P.p_toFtq_wbRedirect_bits_taken),
        "offset": harness.read(P.p_toFtq_wbRedirect_bits_ftqOffset),
        "is_rvc": harness.read(P.p_toFtq_wbRedirect_bits_isRVC),
        "branch_type": harness.read(P.p_toFtq_wbRedirect_bits_attribute_branchType),
        "ras_action": harness.read(P.p_toFtq_wbRedirect_bits_attribute_rasAction),
        "target": harness.read(P.p_toFtq_wbRedirect_bits_target),
    }


def fetch(harness, window: Window, *, ibuffer_ready: int = 1,
          trigger=None, corrupt_after_accept: int = 0) -> tuple[dict | None, dict | None]:
    apply_window(harness, window, request_valid=1, ibuffer_ready=ibuffer_ready, trigger=trigger)
    accepted = False
    for _ in range(16):
        harness.refresh()
        if harness.read(P.p_fromICache_req_ready):
            accepted = True
            harness.step(1)
            break
        harness.step(1)
    assert accepted, "IFU never accepted the fetch request"
    apply_window(harness, window, request_valid=0, ibuffer_ready=ibuffer_ready, trigger=trigger)
    if corrupt_after_accept:
        harness.set(io_fromICache_corrupt_0_0=1)
        harness.step(1)
        harness.set(io_fromICache_corrupt_0_0=0)
    beat = None
    redirect = None
    beat_cycle = None
    for cycle in range(30):
        harness.refresh()
        if beat is None and harness.read(P.p_toIBuffer_valid):
            beat = read_beat(harness)
            beat_cycle = cycle
        if redirect is None and harness.read(P.p_toFtq_wbRedirect_valid):
            redirect = read_redirect(harness)
        if beat is not None and cycle >= beat_cycle + 2:
            break
        harness.step(1)
    return beat, redirect


def check_beat(observed: dict, window: Window, shift: int = 0,
               trigger_actions: dict[int, int] | None = None) -> None:
    expected, prediction, mapping, enq, lanes = aligned_lanes(window, shift)
    assert observed["valid"] == expected.valid_mask, (
        f"valid mask {observed['valid']:#x} != {expected.valid_mask:#x}")
    assert observed["enq"] == expected.enq, (
        f"enq {observed['enq']:#x} != {expected.enq:#x} fault={prediction.fault_class}")
    assert observed["prev_count"] == expected.prev_count
    for lane in mapping:
        assert observed["instrs"][lane] == expected.instrs[lane], (
            f"lane {lane} instr {observed['instrs'][lane]:#x} != {expected.instrs[lane]:#x}")
        assert observed["is_rvc"][lane] == expected.is_rvc[lane]
        assert observed["foldpc"][lane] == expected.foldpc[lane], (
            f"lane {lane} foldpc {observed['foldpc'][lane]:#x} != {expected.foldpc[lane]:#x}")
        assert observed["ftq"][lane] == expected.ftq[lane]
        assert observed["end_off"][lane] == expected.end_offsets[lane]
        assert observed["pred"][lane] == expected.pred_taken[lane]
    assert observed["exception_type"] == expected.exception_type
    assert observed["exception_mask"] == expected.exception_mask
    assert observed["exception_cross"] == expected.exception_cross_page
    assert observed["is_backend_exception"] == expected.is_backend_exception
    assert observed["has_satp_flush"] == expected.has_satp_flush
    expected_triggered = [15] * LANES
    for lane, action in (trigger_actions or {}).items():
        expected_triggered[lane] = action
    assert observed["triggered"] == expected_triggered
    assert observed["gp_wen"] == expected.gp_addr_wen
    if expected.gp_addr_wen:
        assert observed["gp_addr"] == expected.gp_addr
        assert observed["gp_ftq"] == expected.gp_ftq
        assert observed["gp_for_vs"] == expected.gp_for_vs


# ---------------------------------------------------------------------------
# Clean fetch paths
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-TOP-001")
@pytest.mark.feature("IFU-TOP-002")
def test_single_block_mixed_instructions(ifu):
    ifu.reset_once()
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
    beat, redirect = fetch(ifu, window)
    assert redirect is None
    assert beat is not None
    check_beat(beat, window)


@pytest.mark.feature("IFU-TOP-002")
def test_two_blocks_and_cross_block_full_width_instruction(ifu):
    ifu.reset_once()
    program = [
        (c_addi(10, 1), 1),     # slot 0
        (addi(5, 0, 7), 0),     # slots 1-2
        (c_li(6, 3), 1),        # slot 3
        (sub(7, 8, 9), 0),      # slots 4-5, crosses at split=5
        (c_addi(12, 4), 1),     # slot 6
        (addi(13, 0, 9), 0),    # slots 7-8
    ]
    window = build_window(program, 0x2000, split=5, ftq0=(0, 7), ftq1=(0, 8))
    beat, redirect = fetch(ifu, window)
    assert redirect is None
    assert beat is not None
    check_beat(beat, window)


@pytest.mark.feature("IFU-TOP-004")
def test_second_fetch_is_aligned_to_the_write_bank_pointer(ifu):
    ifu.reset_once()
    first = build_window([
        (addi(5, 0, 1), 0),
        (c_addi(6, 2), 1),
        (c_addi(7, 3), 1),
    ], 0x3000, ftq0=(0, 1))
    beat, redirect = fetch(ifu, first)
    assert redirect is None and beat is not None
    for _ in range(3):
        ifu.step(1)
    second = build_window([
        (addi(8, 0, 4), 0),
        (c_addi(9, 5), 1),
        (sub(10, 11, 12), 0),
        (c_li(13, 6), 1),
    ], 0x3100, ftq0=(0, 2))
    beat2, redirect2 = fetch(ifu, second)
    assert redirect2 is None and beat2 is not None
    check_beat(beat2, second, shift=3)


@pytest.mark.feature("IFU-TOP-005")
def test_unpredicted_jump_truncates_enqueue_and_redirects(ifu):
    ifu.reset_once()
    program = [
        (addi(5, 0, 1), 0),
        (jal(1, 0x40), 0),
        (c_addi(6, 2), 1),
        (addi(7, 0, 3), 0),
    ]
    window = build_window(program, 0x4000, ftq0=(0, 9))
    beat, redirect = fetch(ifu, window)
    assert beat is not None and redirect is not None, "missing beat or redirect"
    check_beat(beat, window)
    expected, prediction, *_ = aligned_lanes(window, 0)
    model_redirect = prediction.redirect
    assert model_redirect.valid
    assert redirect["ftq"] == (0, 9)
    assert redirect["pc"] == 0x4000
    assert redirect["target"] == model_redirect.target
    assert redirect["taken"] == model_redirect.taken == 1
    assert redirect["branch_type"] == model_redirect.branch_type
    assert redirect["ras_action"] == model_redirect.ras_action
    assert redirect["offset"] == model_redirect.end_offset
    assert redirect["is_rvc"] == model_redirect.is_rvc
    assert redirect["can_train"] == 1
    assert redirect["valid"] == 1


@pytest.mark.feature("IFU-TOP-006")
def test_ibuffer_backpressure_holds_the_beat(ifu):
    ifu.reset_once()
    window = build_window([(addi(5, 0, 1), 0), (c_addi(6, 2), 1)], 0x5000)
    apply_window(ifu, window, request_valid=1, ibuffer_ready=0)
    for _ in range(16):
        ifu.refresh()
        if ifu.read(P.p_fromICache_req_ready):
            ifu.step(1)
            break
        ifu.step(1)
    apply_window(ifu, window, request_valid=0, ibuffer_ready=0)
    first = None
    for _ in range(20):
        ifu.refresh()
        if ifu.read(P.p_toIBuffer_valid):
            first = read_beat(ifu)
            break
        ifu.step(1)
    assert first is not None, "no beat appeared"
    for _ in range(3):
        ifu.refresh()
        assert ifu.read(P.p_toIBuffer_valid) == 1
        again = read_beat(ifu)
        for key in ("valid", "enq", "instrs", "is_rvc", "foldpc", "ftq", "end_off", "pred"):
            assert again[key] == first[key]
        ifu.step(1)
    # Releasing ready consumes exactly one beat.
    ifu.set(io_toIBuffer_ready=1)
    ifu.step(1)
    for _ in range(3):
        ifu.refresh()
        assert ifu.read(P.p_toIBuffer_valid) == 0
        ifu.step(1)


@pytest.mark.feature("IFU-TOP-007")
def test_backend_redirect_discards_the_inflight_fetch(ifu):
    ifu.reset_once()
    window = build_window([(addi(5, 0, 1), 0), (c_addi(6, 2), 1)], 0x6000)
    apply_window(ifu, window, request_valid=1)
    for _ in range(16):
        ifu.refresh()
        if ifu.read(P.p_fromICache_req_ready):
            ifu.step(1)
            break
        ifu.step(1)
    # Flush immediately after acceptance, while the fetch is in s0/s1.
    apply_window(ifu, window, request_valid=0)
    ifu.set(io_fromFtq_redirect_valid=1)
    ifu.step(1)
    ifu.set(io_fromFtq_redirect_valid=0)
    for _ in range(8):
        ifu.refresh()
        assert ifu.read(P.p_toIBuffer_valid) == 0, "flushed fetch reached IBuffer"
        ifu.step(1)


# ---------------------------------------------------------------------------
# Exceptions and triggers
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-TOP-003")
def test_illegal_compressed_instruction_is_localized(ifu):
    ifu.reset_once()
    program = [
        (addi(5, 0, 1), 0),
        (0x0000, 1),           # reserved all-zero compressed encoding
        (c_addi(6, 2), 1),
        (addi(7, 0, 3), 0),
    ]
    window = build_window(program, 0x7000)
    beat, redirect = fetch(ifu, window)
    assert redirect is None and beat is not None
    check_beat(beat, window)
    assert beat["exception_type"] == 4  # illegal instruction
    assert beat["exception_mask"] == 1 << 1


@pytest.mark.feature("IFU-TOP-008")
def test_page_fault_and_gpf_metadata(ifu):
    program = [(addi(5, 0, 1), 0), (c_addi(6, 2), 1), (addi(7, 0, 3), 0)]
    for exception, gpaddr, expect_gp in ((1, 0, False), (2, 0x123456789ABC, True), (3, 0, False)):
        ifu.reset()
        window = build_window(program, 0x8000, exc0=exception, gp0=gpaddr,
                              vs0=1 if exception == 2 else 0)
        beat, redirect = fetch(ifu, window)
        assert redirect is None and beat is not None
        check_beat(beat, window)
        assert beat["exception_type"] == exception
        assert beat["exception_mask"] == 1
        assert beat["gp_wen"] == int(expect_gp)
        if expect_gp:
            assert beat["gp_addr"] == gpaddr
            assert beat["gp_ftq"] == 0
            assert beat["gp_for_vs"] == 1


@pytest.mark.feature("IFU-TOP-008")
def test_backend_exception_and_satp_flush_markers_reach_the_first_instruction(ifu):
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
        ifu.reset()
        window = build_window(program, 0xA000 + 0x100 * (backend_exc + 2 * satp),
                              exc0=1, backend_exc0=backend_exc, satp0=satp)
        beat, redirect = fetch(ifu, window)
        assert redirect is None and beat is not None
        check_beat(beat, window)
        assert beat["exception_type"] == 1 and beat["exception_mask"] == 1
        assert beat["is_backend_exception"] == backend_exc
        assert beat["has_satp_flush"] == satp


@pytest.mark.feature("IFU-TOP-008")
def test_second_block_exception_moves_to_its_first_instruction(ifu):
    ifu.reset_once()
    program = [
        (c_addi(5, 1), 1),
        (addi(6, 0, 2), 0),
        (c_addi(7, 3), 1),
        (addi(8, 0, 4), 0),
    ]
    window = build_window(program, 0x9000, split=3, exc1=1, gp1=0x456)
    beat, redirect = fetch(ifu, window)
    assert redirect is None and beat is not None
    check_beat(beat, window)
    assert beat["exception_type"] == 1
    # The first block has two instructions; the block-1 exception lands on
    # the first instruction of the second block.
    assert beat["exception_mask"] == 1 << 2


@pytest.mark.feature("IFU-TOP-010")
def test_frontend_trigger_marks_the_matching_instruction(ifu):
    ifu.reset_once()
    program = [
        (addi(5, 0, 1), 0),
        (c_addi(6, 2), 1),
        (sub(7, 8, 9), 0),
        (c_li(10, 3), 1),
    ]
    window = build_window(program, 0xA000)
    target = 0xA004  # the compressed instruction at slot 2 (after the 32-bit addi)
    ifu.set(io_frontendTrigger_tUpdate_valid=1,
            io_frontendTrigger_tUpdate_bits_addr=0,
            io_frontendTrigger_tUpdate_bits_tdata_matchType=0,
            io_frontendTrigger_tUpdate_bits_tdata_select=0,
            io_frontendTrigger_tUpdate_bits_tdata_action=1,
            io_frontendTrigger_tUpdate_bits_tdata_chain=0,
            io_frontendTrigger_tUpdate_bits_tdata_tdata2=target,
            io_frontendTrigger_tEnableVec_0=1)
    ifu.step(2)
    ifu.set(io_frontendTrigger_tUpdate_valid=0, io_frontendTrigger_tEnableVec_0=1)
    beat, redirect = fetch(ifu, window, trigger={"enable": 1})
    assert redirect is None and beat is not None
    check_beat(beat, window, trigger_actions={1: 1})
    assert beat["triggered"][1] == 1
    assert all(action == 15 for index, action in enumerate(beat["triggered"]) if index != 1)


# ---------------------------------------------------------------------------
# Uncache fetch path
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-TOP-009")
def test_uncache_fetch_issues_request_and_enqueues_one_instruction(ifu):
    ifu.reset_once()
    from suites.frontend.ifu.model.cenc import c_addi as enc_addi
    returned = enc_addi(10, 5)
    window = build_window([(addi(5, 0, 1), 0)], 0xB000, pbmt0=1, paddr0=0x123456789ABC)
    apply_window(ifu, window, request_valid=1)
    ifu.set(io_toUncache_req_ready=1)
    accepted = False
    for _ in range(16):
        ifu.refresh()
        if ifu.read(P.p_fromICache_req_ready):
            ifu.step(1)
            accepted = True
            break
        ifu.step(1)
    assert accepted
    apply_window(ifu, window, request_valid=0)
    ifu.set(io_toUncache_req_ready=1, io_fromUncache_resp_valid=0)
    request = None
    for _ in range(20):
        ifu.refresh()
        if ifu.read(P.p_toUncache_req_valid):
            request = {
                "addr": ifu.read(P.p_toUncache_req_bits_addr_addr),
                "mem_back_mm": ifu.read(P.p_toUncache_req_bits_memBackTypeMM),
                "nc": ifu.read(P.p_toUncache_req_bits_memPageTypeNC),
            }
            ifu.step(1)
            break
        ifu.step(1)
    assert request is not None, "uncache request was not issued"
    assert request["addr"] == 0x123456789ABC
    assert request["mem_back_mm"] == 1
    assert request["nc"] == 1
    # Complete the bus read with a compressed instruction.
    ifu.set(io_fromUncache_resp_valid=1, io_fromUncache_resp_bits_data=returned,
            io_fromUncache_resp_bits_corrupt=0, io_fromUncache_resp_bits_denied=0,
            io_fromUncache_resp_bits_needResend=0)
    ifu.step(1)
    ifu.set(io_fromUncache_resp_valid=0)
    beat = None
    redirect = None
    for _ in range(16):
        ifu.refresh()
        if beat is None and ifu.read(P.p_toIBuffer_valid):
            beat = read_beat(ifu)
        if redirect is None and ifu.read(P.p_toFtq_wbRedirect_valid):
            redirect = read_redirect(ifu)
        if beat is not None and redirect is not None:
            break
        ifu.step(1)
    assert beat is not None and redirect is not None
    expanded = expand(returned)
    assert beat["enq"] == 1  # shift zero, one instruction
    assert beat["valid"] == 1
    assert beat["instrs"][0] == expanded.bits
    assert beat["is_rvc"][0] == 1
    assert beat["exception_type"] == 0
    assert redirect["valid"] == 1
    assert redirect["target"] == 0xB000 + 2
    assert redirect["offset"] == 0
    assert redirect["is_rvc"] == 1
    assert redirect["taken"] == 0
    assert redirect["can_train"] == 0


def check_redirect(observed: dict, prediction, window: Window) -> None:
    redirect = prediction.redirect
    assert redirect.valid
    assert observed is not None, "missing FTQ redirect"
    assert observed["valid"] == 1
    # The redirect identifies the fetch block that owns the faulting
    # instruction, so a fault in the second block must carry its FTQ pointer
    # and start PC rather than the first block's.
    if redirect.block_sel or redirect.is_cross_block:
        assert observed["ftq"] == window.ftq1
        assert observed["pc"] == window.start1_pc
    else:
        assert observed["ftq"] == window.ftq0
        assert observed["pc"] == window.start0_pc
    assert observed["target"] == redirect.target
    assert observed["taken"] == redirect.taken
    assert observed["branch_type"] == redirect.branch_type
    assert observed["ras_action"] == redirect.ras_action
    assert observed["offset"] == redirect.end_offset
    assert observed["is_rvc"] == redirect.is_rvc
    can_train = int(redirect.branch_type == 2 or bool(redirect.ras_action & 1)
                    or bool(redirect.invalid_taken) or bool(redirect.not_cfi_taken))
    assert observed["can_train"] == can_train


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
def test_full_32_instruction_compressed_window(ifu):
    ifu.reset_once()
    window = build_window(dense_compressed(32), 0x10000, ftq0=(1, 33))
    beat, redirect = fetch(ifu, window)
    assert redirect is None and beat is not None
    check_beat(beat, window)
    assert beat["valid"] == (1 << 32) - 1
    assert beat["enq"] == (1 << 32) - 1


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-004")
def test_full_window_after_a_three_bank_shift(ifu):
    ifu.reset_once()
    first = build_window(dense_compressed(3), 0x11000, ftq0=(2, 1))
    beat, redirect = fetch(ifu, first)
    assert redirect is None and beat is not None
    for _ in range(3):
        ifu.step(1)
    second = build_window(dense_compressed(32), 0x1A00, ftq0=(2, 2))
    beat2, redirect2 = fetch(ifu, second)
    assert redirect2 is None and beat2 is not None
    check_beat(beat2, second, shift=3)
    assert beat2["valid"] == (((1 << 32) - 1) << 3) & ((1 << 36) - 1)


@pytest.mark.feature("IFU-TOP-002")
def test_conditional_branches_do_not_fault(ifu):
    ifu.reset_once()
    from suites.frontend.ifu.model.cenc import c_beqz
    from suites.frontend.ifu.model.cenc import c_bnez
    program = [
        (addi(5, 0, 1), 0),
        (c_beqz(8, 4), 1),
        (c_addi(9, 2), 1),
        (c_bnez(10, -4), 1),
        (c_addi(11, 3), 1),
        (c_addi(12, 4), 1),
    ]
    window = build_window(program, 0x12000)
    beat, redirect = fetch(ifu, window)
    assert redirect is None and beat is not None
    check_beat(beat, window)


@pytest.mark.feature("IFU-TOP-005")
def test_jump_fault_classes_at_many_lanes(ifu):
    from suites.frontend.ifu.model.cenc import c_beqz
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
            window = build_window(program, 0x13000 + lane * 0x100, ftq0=(3, lane))
            ifu.reset()
            beat, redirect = fetch(ifu, window)
            assert beat is not None and redirect is not None
            check_beat(beat, window)
            expected, prediction, *_ = aligned_lanes(window, 0)
            check_redirect(redirect, prediction, window)


@pytest.mark.feature("IFU-TOP-005")
def test_not_cfi_taken_redirects_sequentially(ifu):
    ifu.reset_once()
    from suites.frontend.ifu.model.cenc import c_beqz
    program = [(c_beqz(8, 4), 1), (c_addi(9, 2), 1), (c_addi(10, 3), 1)]
    window = build_window(program, 0x14000, taken0=1)
    beat, redirect = fetch(ifu, window)
    assert beat is not None and redirect is not None
    check_beat(beat, window)
    expected, prediction, *_ = aligned_lanes(window, 0)
    check_redirect(redirect, prediction, window)
    assert redirect["target"] == 0x14000 + 4 + 2  # taken lane is the RVC at +4
    assert redirect["taken"] == 0
    assert redirect["branch_type"] == 0


@pytest.mark.feature("IFU-TOP-008")
def test_icache_ecc_corruption_raises_hardware_error(ifu):
    from dataclasses import replace
    ifu.reset_once()
    program = [(addi(5, 0, 1), 0), (c_addi(6, 2), 1), (addi(7, 0, 3), 0)]
    window = build_window(program, 0x15000)
    beat, redirect = fetch(ifu, window, corrupt_after_accept=1)
    assert beat is not None and redirect is None
    # The ECC error is merged into the first block's exception metadata and
    # therefore ends the window after the first instruction.
    expected_window = replace(window, exc0=5)
    check_beat(beat, expected_window)
    assert beat["exception_type"] == 5
    assert beat["exception_mask"] == 1


@pytest.mark.feature("IFU-TOP-007")
def test_bpu_stage3_flush_drops_the_window(ifu):
    ifu.reset_once()
    window = build_window([(addi(5, 0, 1), 0), (c_addi(6, 2), 1)], 0x16000, ftq0=(0, 21))
    apply_window(ifu, window, request_valid=1)
    # The stage-3 flush must drop the block in s0 before it is captured.
    ifu.set(io_fromFtq_flushFromBpu_s3_valid=1,
            io_fromFtq_flushFromBpu_s3_bits_flag=0,
            io_fromFtq_flushFromBpu_s3_bits_value=21)
    for _ in range(6):
        ifu.refresh()
        assert ifu.read(P.p_toIBuffer_valid) == 0
        ifu.step(1)
    # Releasing the flush lets the still-asserted request enter normally.
    ifu.set(io_fromFtq_flushFromBpu_s3_valid=0)
    beat, redirect = fetch(ifu, window)
    assert beat is not None and redirect is None
    check_beat(beat, window)


@pytest.mark.feature("IFU-TOP-002")
def test_compressed_control_transfer_families_across_all_lanes(ifu):
    ifu.reset_once()
    from suites.frontend.ifu.model.cenc import c_beqz
    from suites.frontend.ifu.model.cenc import c_bnez
    from suites.frontend.ifu.model.cenc import c_j
    from suites.frontend.ifu.model.cenc import c_jalr
    from suites.frontend.ifu.model.cenc import c_jr
    from suites.frontend.ifu.model.cenc import c_mv
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
    beat, redirect = fetch(ifu, window)
    assert beat is not None
    check_beat(beat, window)
    expected, prediction, *_ = aligned_lanes(window, 0)
    if prediction.redirect.valid:
        check_redirect(redirect, prediction, window)
    else:
        assert redirect is None


@pytest.mark.feature("IFU-TOP-002")
def test_full_width_control_flow_families(ifu):
    ifu.reset_once()
    from suites.frontend.ifu.model.isa import beq
    from suites.frontend.ifu.model.isa import jalr
    from suites.frontend.ifu.model.isa import load_bytes
    from suites.frontend.ifu.model.isa import store_bytes
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
    beat, redirect = fetch(ifu, window)
    assert beat is not None
    check_beat(beat, window)
    expected, prediction, *_ = aligned_lanes(window, 0)
    if prediction.redirect.valid:
        check_redirect(redirect, prediction, window)
    else:
        assert redirect is None


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-004")
def test_high_aligned_lane_owned_by_the_second_block(ifu):
    ifu.reset_once()
    first = build_window(dense_compressed(3), 0x19000, ftq0=(2, 3))
    beat, redirect = fetch(ifu, first)
    assert beat is not None and redirect is None
    for _ in range(3):
        ifu.step(1)
    second = build_window(dense_compressed(32), 0x19100, split=16, ftq0=(2, 4), ftq1=(2, 5))
    beat2, redirect2 = fetch(ifu, second)
    assert beat2 is not None and redirect2 is None
    check_beat(beat2, second, shift=3)


def uncache_accept_and_send(ifu, window):
    apply_window(ifu, window, request_valid=1)
    ifu.set(io_toUncache_req_ready=1)
    for _ in range(16):
        ifu.refresh()
        if ifu.read(P.p_fromICache_req_ready):
            ifu.step(1)
            break
        ifu.step(1)
    else:
        raise AssertionError("uncache fetch was not accepted")
    apply_window(ifu, window, request_valid=0)
    ifu.set(io_toUncache_req_ready=1)
    for _ in range(20):
        ifu.refresh()
        if ifu.read(P.p_toUncache_req_valid):
            ifu.step(1)
            return
        ifu.step(1)
    raise AssertionError("uncache request was not issued")


def uncache_collect(ifu, cycles=20):
    beat = None
    redirect = None
    for _ in range(cycles):
        ifu.refresh()
        if beat is None and ifu.read(P.p_toIBuffer_valid):
            beat = read_beat(ifu)
        if redirect is None and ifu.read(P.p_toFtq_wbRedirect_valid):
            redirect = read_redirect(ifu)
        if beat is not None and redirect is not None:
            break
        ifu.step(1)
    return beat, redirect


@pytest.mark.feature("IFU-TOP-009")
def test_uncache_bus_error_is_attached_to_the_instruction(ifu):
    from suites.frontend.ifu.model.cenc import c_addi as enc_addi
    ifu.reset_once()
    returned = enc_addi(10, 5)
    window = build_window([(addi(5, 0, 1), 0)], 0xC800, pbmt0=1, paddr0=0x1234)
    uncache_accept_and_send(ifu, window)
    ifu.set(io_fromUncache_resp_valid=1, io_fromUncache_resp_bits_data=returned,
            io_fromUncache_resp_bits_corrupt=1, io_fromUncache_resp_bits_denied=0,
            io_fromUncache_resp_bits_needResend=0)
    ifu.step(1)
    ifu.set(io_fromUncache_resp_valid=0)
    beat, redirect = uncache_collect(ifu)
    assert beat is not None
    assert beat["exception_type"] == 5  # corrupted transfer -> hardware error
    assert beat["exception_mask"] == 1
    assert beat["enq"] == 1


@pytest.mark.feature("IFU-TOP-009")
def test_uncache_cross_page_resend_reassembles_the_instruction(ifu):
    from suites.frontend.ifu.model.cenc import c_addi as enc_addi
    ifu.reset_once()
    full = addi(5, 0, 1)
    low = full & 0xFFFF
    high = (full >> 16) & 0xFFFF
    first = build_window([(addi(9, 0, 9), 0)], 0xC000, pbmt0=1, paddr0=0x4000)
    uncache_accept_and_send(ifu, first)
    ifu.set(io_fromUncache_resp_valid=1, io_fromUncache_resp_bits_data=low,
            io_fromUncache_resp_bits_corrupt=0, io_fromUncache_resp_bits_denied=0,
            io_fromUncache_resp_bits_needResend=1)
    ifu.step(1)
    ifu.set(io_fromUncache_resp_valid=0)
    # The resend must not enqueue a half instruction; it only records the
    # continuation and asks the FTQ to refetch from the next page.
    beat, redirect = uncache_collect(ifu, cycles=10)
    assert beat is None
    assert redirect is not None and redirect["valid"] == 1
    assert redirect["target"] == 0xC000 + 2
    assert redirect["offset"] == 0
    assert redirect["taken"] == 0
    for _ in range(3):
        ifu.step(1)
    second = build_window([(addi(9, 0, 8), 0)], 0xC002, pbmt0=1, paddr0=0x4000)
    uncache_accept_and_send(ifu, second)
    ifu.set(io_fromUncache_resp_valid=1, io_fromUncache_resp_bits_data=high,
            io_fromUncache_resp_bits_corrupt=0, io_fromUncache_resp_bits_denied=0,
            io_fromUncache_resp_bits_needResend=0)
    ifu.step(1)
    ifu.set(io_fromUncache_resp_valid=0)
    beat, redirect = uncache_collect(ifu)
    assert beat is not None, "assembled instruction was not enqueued"
    assert beat["enq"] == 1
    assert beat["valid"] == 1
    assert beat["instrs"][0] == full
    assert beat["is_rvc"][0] == 0
    assert redirect is not None
    assert redirect["target"] == 0xC002 + 2
    assert redirect["is_rvc"] == 0
    assert redirect["offset"] == 0


def random_compressed(rng) -> int:
    from suites.frontend.ifu.model import cenc
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
def test_randomized_full_window_covers_address_and_data_bits(ifu):
    import random
    rng = random.Random(0xF3C4)
    for _ in range(5):
        ifu.reset()
        program = [(random_compressed(rng), 1) for _ in range(32)]
        base = rng.getrandbits(50) & ~0x3F
        window = build_window(program, base, ftq0=(rng.randrange(2), rng.randrange(64)))
        beat, redirect = fetch(ifu, window)
        assert redirect is None and beat is not None
        check_beat(beat, window)


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-005")
def test_full_width_instructions_at_high_instruction_indices(ifu):
    from suites.frontend.ifu.model.cenc import c_beqz
    from suites.frontend.ifu.model.isa import beq
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
                ifu.reset()
                beat, redirect = fetch(ifu, window)
                assert beat is not None and redirect is None
                check_beat(beat, window)
                continue
            ifu.reset()
            beat, redirect = fetch(ifu, window)
            assert beat is not None and redirect is not None
            check_beat(beat, window)
            expected, prediction, *_ = aligned_lanes(window, 0)
            check_redirect(redirect, prediction, window)


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-004")
def test_block_one_instruction_at_the_highest_lane_with_pc_carry(ifu):
    """A second-block instruction can land on lane 34 after a 3-bank shift.

    Its PC lower part is formed from the block start plus the instruction
    offset; when that sum carries into bit 11 of the halfword coordinate, the
    upper PC bits must be incremented rather than reused.  This is the only
    way to reach that high-lane carry path in the generated PC assembly.
    """

    ifu.reset_once()
    first = build_window(dense_compressed(3), 0x1D000, ftq0=(3, 9))
    beat, redirect = fetch(ifu, first)
    assert beat is not None and redirect is None
    for _ in range(3):
        ifu.step(1)
    # Block 1 starts at halfword 0x3E2; its last instruction (lane 34 after
    # the shift) has block offset 30, so start + offset carries past 0x3FF
    # into bit 11 of the halfword PC coordinate.
    base = 0x1D7C2
    second = build_window(dense_compressed(32), base, split=1,
                          ftq0=(3, 10), ftq1=(3, 11))
    beat2, redirect2 = fetch(ifu, second)
    assert beat2 is not None and redirect2 is None
    check_beat(beat2, second, shift=3)
    assert beat2["ftq"][34] == (3, 11)


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-004")
def test_first_block_instruction_at_the_highest_lane_with_pc_carry(ifu):
    """The symmetric high-lane carry for an instruction owned by block 0."""

    ifu.reset_once()
    first = build_window(dense_compressed(3), 0x1E000, ftq0=(3, 19))
    beat, redirect = fetch(ifu, first)
    assert beat is not None and redirect is None
    for _ in range(3):
        ifu.step(1)
    # Block 0 spans all 32 slots: start halfword 0x3E2 + last offset 31
    # carries past 0x3FF while the instruction still belongs to block 0.
    base = 0x1E7C2
    second = build_window(dense_compressed(32), base, ftq0=(3, 20))
    beat2, redirect2 = fetch(ifu, second)
    assert beat2 is not None and redirect2 is None
    check_beat(beat2, second, shift=3)
    assert beat2["ftq"][34] == (3, 20)


def build_cfi_window(base: int, lane: int, kind: str) -> Window:
    from suites.frontend.ifu.model.cenc import c_beqz
    from suites.frontend.ifu.model.cenc import c_j
    from suites.frontend.ifu.model.cenc import c_jalr
    from suites.frontend.ifu.model.cenc import c_jr
    from suites.frontend.ifu.model.isa import beq
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
def test_control_flow_classification_at_every_instruction_index(ifu):
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
            ifu.reset()
            window = build_cfi_window(0x20000 + lane * 0x200, lane, kind)
            beat, redirect = fetch(ifu, window)
            assert beat is not None, (lane, kind)
            check_beat(beat, window)
            _, prediction, *_ = aligned_lanes(window, 0)
            if prediction.redirect.valid:
                check_redirect(redirect, prediction, window)
            else:
                assert redirect is None, (lane, kind)


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-005")
def test_cross_block_split_position_sweep(ifu):
    """Sweep the split point so every lane can own a cross-block instruction."""

    for split in range(1, 31):
        ifu.reset()
        # 31 compressed instructions with one replaced by a 32-bit one still
        # fill exactly 32 halfword slots.
        program = [(c_addi(8 + (index % 8), index % 5 + 1), 1) for index in range(31)]
        program[split - 1] = (addi(5, 0, 1), 0)
        window = build_window(program, 0x30000 + split * 0x200, split=split,
                              ftq0=(1, split), ftq1=(1, split + 1))
        beat, redirect = fetch(ifu, window)
        assert beat is not None
        check_beat(beat, window)
        assert beat["ftq"][split] == (1, split + 1)


@pytest.mark.feature("IFU-TOP-011")
@pytest.mark.uncertain(
    reason="covers one carry position (window ends after its low half at slot 31); "
           "other split/carry positions and instruction classes are untested",
    reference="R-09")
def test_instruction_split_across_two_fetch_windows_is_assembled(ifu):
    """A 32-bit instruction may straddle the 64-byte block boundary.

    The first window ends after its low half and cannot enqueue it; the IFU
    records the PC and low half.  The following window starts with the high
    half and must enqueue the single assembled instruction (not two halves),
    with the PC of the original instruction.
    """

    ifu.reset_once()
    word = addi(5, 0, 1)
    program = [(c_addi(8 + (index % 8), index % 5 + 1), 1) for index in range(31)]
    program.append((word, 0))
    first = build_window(program, 0x40000, truncate=1, ftq0=(0, 7))
    beat, redirect = fetch(ifu, first)
    assert redirect is None and beat is not None
    check_beat(beat, first)
    assert beat["enq"] == (1 << 31) - 1  # the incomplete instruction is not enqueued
    second = build_window([(c_addi(9, 1), 1), (addi(6, 0, 2), 0)],
                          0x40040, carry_word=word, ftq0=(0, 8))
    beat2, redirect2 = fetch(ifu, second)
    assert redirect2 is None and beat2 is not None
    check_beat(beat2, second, shift=3)
    assert beat2["instrs"][3] == word
    assert beat2["is_rvc"][3] == 0
    assert beat2["end_off"][3] == 0


@pytest.mark.feature("IFU-TOP-011")
def test_split_instruction_reaches_ibuffer_with_its_own_pc(ifu):
    ifu.reset_once()
    from suites.frontend.ifu.model.cenc import c_addi
    word = 0x00100293
    first = build_window([(c_addi(8 + (index % 8), 1), 1) for index in range(31)]
                         + [(word, 0)], 0x41000, truncate=1, ftq0=(0, 9))
    beat, _ = fetch(ifu, first)
    assert beat is not None
    second = build_window([(c_addi(9, 1), 1)], 0x41040, carry_word=word, ftq0=(0, 10))
    before = ifu.read(P.p_toIBuffer_bits_foldpc_0)
    beat2, redirect2 = fetch(ifu, second)
    assert beat2 is not None and redirect2 is None
    check_beat(beat2, second, shift=3)
    # The assembled instruction's PC is one halfword before the new block and
    # is folded into the predictor PC field.
    from suites.frontend.ifu.model.fetch import xor_fold
    assert beat2["foldpc"][3] == xor_fold((0x41040 - 2) >> 1, 10)
    del before


@pytest.mark.feature("IFU-TOP-008")
def test_second_block_ecc_corruption_is_attached_there(ifu):
    from dataclasses import replace
    ifu.reset_once()
    program = [(c_addi(8 + (index % 8), 1), 1) for index in range(8)]
    window = build_window(program, 0x42000, split=4, ftq0=(0, 11), ftq1=(0, 12))
    apply_window(ifu, window, request_valid=1)
    for _ in range(16):
        ifu.refresh()
        if ifu.read(P.p_fromICache_req_ready):
            ifu.step(1)
            break
        ifu.step(1)
    apply_window(ifu, window, request_valid=0)
    ifu.set(io_fromICache_corrupt_1_0=1)
    ifu.step(1)
    ifu.set(io_fromICache_corrupt_1_0=0)
    beat = None
    redirect = None
    for _ in range(20):
        ifu.refresh()
        if beat is None and ifu.read(P.p_toIBuffer_valid):
            beat = read_beat(ifu)
        if redirect is None and ifu.read(P.p_toFtq_wbRedirect_valid):
            redirect = read_beat and read_redirect(ifu)
        if beat is not None:
            break
        ifu.step(1)
    assert beat is not None and redirect is None
    expected_window = replace(window, exc1=5)
    check_beat(beat, expected_window)
    assert beat["exception_type"] == 5
    # The exception lands on the first instruction of the second block.
    assert beat["exception_mask"] == 1 << 4


@pytest.mark.feature("IFU-TOP-005")
def test_block_one_jump_fault_redirects_with_block_one_identity(ifu):
    ifu.reset_once()
    program = [(c_addi(8 + (index % 8), 1), 1) for index in range(8)]
    program[5] = (0x000080E7, 0)  # jalr x1, 0(x1) in the second block
    window = build_window(program, 0x43000, split=4, ftq0=(0, 13), ftq1=(0, 14))
    beat, redirect = fetch(ifu, window)
    assert beat is not None and redirect is not None
    check_beat(beat, window)
    _, prediction, *_ = aligned_lanes(window, 0)
    check_redirect(redirect, prediction, window)
    # The redirect is attributed to the second fetch block.
    assert redirect["ftq"] == (0, 14)
    assert redirect["pc"] == 0x43000 + 2 * 4  # start PC of the owning block


@pytest.mark.feature("IFU-TOP-004")
def test_ibuf_write_pointer_wraps_across_many_fetches(ifu):
    ifu.reset_once()
    for round_index in range(12):
        window = build_window(dense_compressed(5), 0x44000 + round_index * 0x100,
                              ftq0=(0, round_index))
        beat, redirect = fetch(ifu, window)
        assert beat is not None and redirect is None, round_index
        check_beat(beat, window, shift=(round_index * 5) & 3)
        for _ in range(4):
            ifu.step(1)


@pytest.mark.feature("IFU-TOP-009")
def test_uncache_fetch_after_an_alignment_shift(ifu):
    """The uncache lane follows the same write-bank alignment as cached fetches."""

    from suites.frontend.ifu.model.cenc import c_addi as enc_addi
    from suites.frontend.ifu.model.cenc import c_li as enc_li
    from suites.frontend.ifu.model.cenc import c_sw as enc_sw
    for pre_count in (1, 2, 3):
        ifu.reset()
        pre = build_window(dense_compressed(pre_count), 0x45000, ftq0=(1, 20))
        beat, redirect = fetch(ifu, pre)
        assert beat is not None and redirect is None
        for _ in range(3):
            ifu.step(1)
        window = build_window([(addi(5, 0, 1), 0)], 0x45100,
                              pbmt0=1, paddr0=0x9000, ftq0=(1, 21))
        uncache_accept_and_send(ifu, window)
        returned = (enc_addi, enc_li, enc_sw)[pre_count - 1](
            *({1: (10, 5), 2: (11, -2), 3: (10, 11, 4)}[pre_count]))
        ifu.set(io_fromUncache_resp_valid=1, io_fromUncache_resp_bits_data=returned,
                io_fromUncache_resp_bits_corrupt=0, io_fromUncache_resp_bits_denied=0,
                io_fromUncache_resp_bits_needResend=0)
        ifu.step(1)
        ifu.set(io_fromUncache_resp_valid=0)
        beat, redirect = uncache_collect(ifu)
        assert beat is not None, pre_count
        assert beat["enq"] == 1 << pre_count, (pre_count, bin(beat["enq"]))
        assert beat["valid"] == 1 << pre_count
        assert beat["instrs"][pre_count] == expand(returned).bits
        assert beat["is_rvc"][pre_count] == 1
        assert redirect is not None and redirect["target"] == 0x45100 + 2


@pytest.mark.feature("IFU-TOP-009")
def test_uncache_fetch_of_a_jump_redirects_with_its_attribute(ifu):
    from suites.frontend.ifu.model.cenc import c_j
    from suites.frontend.ifu.model.isa import beq
    ifu.reset_once()
    returned = c_j(8)
    window = build_window([(addi(5, 0, 1), 0)], 0x46000, pbmt0=1, paddr0=0xA000)
    uncache_accept_and_send(ifu, window)
    ifu.set(io_fromUncache_resp_valid=1, io_fromUncache_resp_bits_data=returned,
            io_fromUncache_resp_bits_corrupt=0, io_fromUncache_resp_bits_denied=0,
            io_fromUncache_resp_bits_needResend=0)
    ifu.step(1)
    ifu.set(io_fromUncache_resp_valid=0)
    beat, redirect = uncache_collect(ifu)
    assert beat is not None and redirect is not None
    assert beat["instrs"][0] == expand(returned).bits
    assert redirect["branch_type"] == 2  # direct
    assert redirect["is_rvc"] == 1
    assert redirect["target"] == 0x46000 + 2
    assert redirect["taken"] == 0


@pytest.mark.feature("IFU-TOP-009")
def test_uncache_fetch_of_a_full_width_branch(ifu):
    from suites.frontend.ifu.model.isa import beq
    ifu.reset_once()
    returned = beq(5, 6, 8)
    window = build_window([(addi(9, 0, 1), 0)], 0x47000, pbmt0=1, paddr0=0xB000)
    uncache_accept_and_send(ifu, window)
    ifu.set(io_fromUncache_resp_valid=1, io_fromUncache_resp_bits_data=returned,
            io_fromUncache_resp_bits_corrupt=0, io_fromUncache_resp_bits_denied=0,
            io_fromUncache_resp_bits_needResend=0)
    ifu.step(1)
    ifu.set(io_fromUncache_resp_valid=0)
    beat, redirect = uncache_collect(ifu)
    assert beat is not None and redirect is not None
    assert beat["instrs"][0] == returned
    assert beat["is_rvc"][0] == 0
    assert redirect["branch_type"] == 1  # conditional
    assert redirect["offset"] == 1
    # The uncached instruction is the first (unshifted) lane; the sequential
    # target is the next 4-byte PC after the fetched block start.
    assert redirect["target"] == 0x47000 + 4


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-004")
def test_cross_block_instruction_shifted_to_high_lanes(ifu):
    """A 3-bank shift moves the block-crossing instruction to lanes 30..33."""

    from suites.frontend.ifu.model.cenc import c_addi as enc_addi
    for split in (28, 29, 30, 31):
        ifu.reset()
        first = build_window(dense_compressed(3), 0x48000 + split * 0x100, ftq0=(2, 30))
        beat, redirect = fetch(ifu, first)
        assert beat is not None and redirect is None
        for _ in range(3):
            ifu.step(1)
        program = [(enc_addi(8 + (index % 8), index % 5 + 1), 1) for index in range(31)]
        program[split - 1] = (addi(5, 0, 1), 0)
        window = build_window(program, 0x49000 + split * 0x100, split=split,
                              ftq0=(2, 31), ftq1=(2, 32))
        beat2, redirect2 = fetch(ifu, window)
        assert beat2 is not None and redirect2 is None
        check_beat(beat2, window, shift=3)
        lane = split - 1 + 3
        assert beat2["ftq"][lane] == (2, 32)


@pytest.mark.feature("IFU-TOP-002")
def test_sparse_encodings_at_the_highest_lanes(ifu):
    """Reserved/hint encodings still reach the decoders at high lanes."""

    from suites.frontend.ifu.model.cenc import c_addi as enc_addi
    encodings = (0x9002, 0x8002, 0x6081)  # c.ebreak, reserved c.jr x0, c.mop hint
    for encoding in encodings:
        ifu.reset()
        first = build_window(dense_compressed(3), 0x4A000, ftq0=(1, 1))
        beat, redirect = fetch(ifu, first)
        assert beat is not None and redirect is None
        for _ in range(3):
            ifu.step(1)
        program = [(enc_addi(8 + (index % 8), index % 5 + 1), 1) for index in range(32)]
        program[30] = (encoding, 1)
        window = build_window(program, 0x4A100, ftq0=(1, 2))
        beat2, redirect2 = fetch(ifu, window)
        assert beat2 is not None
        check_beat(beat2, window, shift=3)
        if redirect2 is not None:
            _, prediction, *_ = aligned_lanes(window, 3)
            check_redirect(redirect2, prediction, window)


@pytest.mark.feature("IFU-TOP-009")
def test_uncache_fetch_of_indirect_control_transfers(ifu):
    from suites.frontend.ifu.model.cenc import c_bnez
    from suites.frontend.ifu.model.cenc import c_jalr
    from suites.frontend.ifu.model.cenc import c_jr
    from suites.frontend.ifu.model.isa import jal as isa_jal
    from suites.frontend.ifu.model.isa import jalr as isa_jalr
    for returned in (c_jalr(1), c_jr(1), 0x8002, c_bnez(8, 4), isa_jal(1, 0x40),
                     isa_jalr(1, 5, 0)):
        ifu.reset()
        window = build_window([(addi(5, 0, 1), 0)], 0x4B000, pbmt0=1, paddr0=0xC000)
        uncache_accept_and_send(ifu, window)
        ifu.set(io_fromUncache_resp_valid=1, io_fromUncache_resp_bits_data=returned,
                io_fromUncache_resp_bits_corrupt=0, io_fromUncache_resp_bits_denied=0,
                io_fromUncache_resp_bits_needResend=0)
        ifu.step(1)
        ifu.set(io_fromUncache_resp_valid=0)
        beat, redirect = uncache_collect(ifu)
        assert beat is not None and redirect is not None
        expected = expand(returned)
        assert beat["instrs"][0] == (returned if expected.ill else expected.bits)
        if returned == 0x8002:
            assert beat["exception_type"] == 4  # reserved encoding stays illegal
        else:
            from suites.frontend.ifu.model.fetch import branch_info
            from suites.frontend.ifu.model.isa import is_compressed
            expected_class, expected_ras, _ = branch_info(returned, int(is_compressed(returned)))
            assert redirect["branch_type"] == expected_class
            assert redirect["ras_action"] == expected_ras


@pytest.mark.feature("IFU-TOP-002")
def test_sparse_encodings_at_every_lane(ifu):
    """The fast non-CFI decode path must work at every aligned lane."""

    for encoding in (0x9002, 0x8002):
        ifu.reset()
        window = build_window([(encoding, 1) for _ in range(32)], 0x4C000)
        beat, redirect = fetch(ifu, window)
        assert beat is not None and redirect is None
        check_beat(beat, window)
        # A shifted window also places the encoding on the high lanes 32..34.
        for _ in range(3):
            ifu.step(1)
        first = build_window(dense_compressed(3), 0x4C100, ftq0=(1, 3))
        beat0, redirect0 = fetch(ifu, first)
        assert beat0 is not None and redirect0 is None
        for _ in range(3):
            ifu.step(1)
        window2 = build_window([(encoding, 1) for _ in range(32)], 0x4C200)
        beat2, redirect2 = fetch(ifu, window2)
        assert beat2 is not None and redirect2 is None
        check_beat(beat2, window2, shift=3)


@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.feature("IFU-TOP-005")
def test_conditional_branch_at_the_highest_aligned_lanes(ifu):
    from suites.frontend.ifu.model.cenc import c_beqz
    ifu.reset()
    first = build_window(dense_compressed(3), 0x4D000, ftq0=(1, 5))
    beat, redirect = fetch(ifu, first)
    assert beat is not None and redirect is None
    for _ in range(3):
        ifu.step(1)
    program = [(c_addi(8 + (index % 8), 1), 1) for index in range(32)]
    for index in (28, 29, 30, 31):
        program[index] = (c_beqz(8, 4), 1)
    window = build_window(program, 0x4D100)
    beat2, redirect2 = fetch(ifu, window)
    assert beat2 is not None and redirect2 is None
    check_beat(beat2, window, shift=3)


@pytest.mark.feature("IFU-TOP-005")
@pytest.mark.feature("IFU-TOP-004")
def test_redirect_updates_the_ibuf_pointer_across_the_wrap(ifu):
    for round_index in range(11):
        window = build_window(dense_compressed(5), 0x4E000 + round_index * 0x100,
                              ftq0=(0, round_index))
        beat, redirect = fetch(ifu, window)
        assert beat is not None and redirect is None, round_index
        check_beat(beat, window, shift=(round_index * 5) & 3)
        for _ in range(4):
            ifu.step(1)
    # 55 instructions are enqueued; a faulting jump now performs the wrapped
    # pointer update (previous + count crosses the 48-instruction window).
    fault = build_window([(c_addi(8, 1), 1), (jal(1, 0x40), 0)], 0x4F000)
    beat, redirect = fetch(ifu, fault)
    assert beat is not None and redirect is not None
    check_beat(beat, fault, shift=55 & 3)
    _, prediction, *_ = aligned_lanes(fault, 55 & 3)
    check_redirect(redirect, prediction, fault)
    # The redirect carries the same instruction count the pointer adopts.
    next_shift = (55 + sum(prediction.fixed_instr_valid)) & 3
    for _ in range(4):
        ifu.step(1)
    after = build_window(dense_compressed(2), 0x4F100, ftq0=(0, 40))
    beat2, redirect2 = fetch(ifu, after)
    assert beat2 is not None and redirect2 is None
    check_beat(beat2, after, shift=next_shift)


@pytest.mark.feature("IFU-TOP-009")
def test_uncache_redirect_after_many_enqueues(ifu):
    from suites.frontend.ifu.model.cenc import c_addi as enc_addi
    for round_index in range(12):
        window = build_window(dense_compressed(5), 0x50000 + round_index * 0x100,
                              ftq0=(0, round_index))
        beat, redirect = fetch(ifu, window)
        assert beat is not None and redirect is None
        check_beat(beat, window, shift=(round_index * 5) & 3)
        for _ in range(4):
            ifu.step(1)
    # 60 instructions are resident; the uncache redirect adds one more and
    # crosses the pointer's wrap window.
    window = build_window([(addi(5, 0, 1), 0)], 0x50100, pbmt0=1, paddr0=0xD000)
    uncache_accept_and_send(ifu, window)
    returned = enc_addi(10, 5)
    ifu.set(io_fromUncache_resp_valid=1, io_fromUncache_resp_bits_data=returned,
            io_fromUncache_resp_bits_corrupt=0, io_fromUncache_resp_bits_denied=0,
            io_fromUncache_resp_bits_needResend=0)
    ifu.step(1)
    ifu.set(io_fromUncache_resp_valid=0)
    beat, redirect = uncache_collect(ifu)
    assert beat is not None and redirect is not None
    assert redirect["target"] == 0x50100 + 2


@pytest.mark.feature("IFU-TOP-005")
def test_prediction_into_the_middle_of_an_instruction_is_invalid_taken(ifu):
    """The predictor may point at the low half of a 32-bit instruction.

    When the taken position starts a 32-bit instruction but the fetched block
    ends after that low half, the prediction is invalid.  The IFU must discard
    the speculative instructions, report invalid-taken with the instruction's
    PC, and let the next fetch resume at that PC to assemble the full word.
    """

    ifu.reset_once()
    program = [(addi(5, 0, 1), 0)] + [(c_addi(8 + (index % 8), 1), 1) for index in range(30)]
    window = build_window(program, 0x51000, split=1, taken0=1, ftq0=(0, 31))
    beat, redirect = fetch(ifu, window)
    assert beat is not None and beat["valid"] == 0  # nothing from the bad fetch is enqueued
    assert redirect is not None
    _, prediction, *_ = aligned_lanes(window, 0)
    assert prediction.redirect.invalid_taken == 1
    check_redirect(redirect, prediction, window)
    assert redirect["taken"] == 0
    assert redirect["branch_type"] == 0
    assert redirect["can_train"] == 1  # invalid-taken is trainable
    assert redirect["target"] == 0x51000 + 2  # resume at the real half-instruction PC
    # The recorded half-RVI carries the low half of that instruction.
    for _ in range(4):
        ifu.step(1)
    word = program[0][0]
    resume = build_window([(c_addi(9, 1), 1), (addi(6, 0, 2), 0)],
                          0x51002, carry_word=word, ftq0=(0, 32))
    beat2, redirect2 = fetch(ifu, resume)
    assert redirect2 is None and beat2 is not None
    check_beat(beat2, resume)
    assert beat2["instrs"][0] == word
    assert beat2["is_rvc"][0] == 0


@pytest.mark.feature("IFU-TOP-005")
def test_prediction_on_the_second_half_belongs_to_the_enclosing_instruction(ifu):
    """A taken position inside an instruction's high half is not invalid-taken.

    The fetch block ends after the instruction's second half, so the whole
    instruction is present; the prediction is attached to the last valid
    instruction start (the enclosing RVI), which is a non-CFI taken fault.
    """

    ifu.reset_once()
    program = [(c_addi(8 + (index % 8), 1), 1) for index in range(30)]
    program.append((addi(5, 0, 1), 0))
    window = build_window(program, 0x52000, taken0=1, ftq0=(0, 32))
    beat, redirect = fetch(ifu, window)
    assert beat is not None and redirect is not None
    check_beat(beat, window)
    _, prediction, *_ = aligned_lanes(window, 0)
    assert prediction.redirect.invalid_taken == 0
    assert prediction.redirect.not_cfi_taken == 1
    check_redirect(redirect, prediction, window)
    assert redirect["target"] == 0x52000 + 2 * 30 + 4


@pytest.mark.feature("IFU-TOP-009")
def test_uncache_pointer_wrap_after_forty_seven_instructions(ifu):
    from suites.frontend.ifu.model.cenc import c_addi as enc_addi
    for count in (47, 48):
        ifu.reset()
        remaining = count
        round_index = 0
        while remaining:
            take = min(5, remaining)
            window = build_window(dense_compressed(take),
                                  0x53000 + round_index * 0x100, ftq0=(0, round_index))
            beat, redirect = fetch(ifu, window)
            assert beat is not None and redirect is None
            check_beat(beat, window, shift=(count - remaining) & 3)
            remaining -= take
            round_index += 1
            for _ in range(4):
                ifu.step(1)
        window = build_window([(addi(5, 0, 1), 0)], 0x53100, pbmt0=1, paddr0=0xE000)
        uncache_accept_and_send(ifu, window)
        ifu.set(io_fromUncache_resp_valid=1, io_fromUncache_resp_bits_data=enc_addi(10, 5),
                io_fromUncache_resp_bits_corrupt=0, io_fromUncache_resp_bits_denied=0,
                io_fromUncache_resp_bits_needResend=0)
        ifu.step(1)
        ifu.set(io_fromUncache_resp_valid=0)
        beat, redirect = uncache_collect(ifu)
        assert beat is not None and redirect is not None
        assert redirect["target"] == 0x53100 + 2
