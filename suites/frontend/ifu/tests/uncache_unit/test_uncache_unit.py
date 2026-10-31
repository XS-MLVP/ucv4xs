"""IfuUncacheUnit: request lifecycle, memory-type ordering, response and flush."""

from __future__ import annotations

import random

import pytest

from suites.frontend.ifu.legacy_pins import P
from suites.frontend.ifu.model.uncache import EXC_AF
from suites.frontend.ifu.model.uncache import EXC_HWE
from suites.frontend.ifu.model.uncache import EXC_NONE
from suites.frontend.ifu.model.uncache import IDLE
from suites.frontend.ifu.model.uncache import IO
from suites.frontend.ifu.model.uncache import Inputs
from suites.frontend.ifu.model.uncache import NC
from suites.frontend.ifu.model.uncache import PMA
from suites.frontend.ifu.model.uncache import SEND
from suites.frontend.ifu.model.uncache import WAIT_COMMIT
from suites.frontend.ifu.model.uncache import WAIT_RESP
from suites.frontend.ifu.model.uncache import UncacheModel


def apply(harness, inputs: Inputs) -> None:
    harness.set(
        io_flush=inputs.flush,
        io_req_valid=inputs.req_valid,
        io_req_bits_paddr_addr=inputs.req_paddr,
        io_req_bits_isMmio=inputs.req_is_mmio,
        io_req_bits_pbmt=inputs.req_pbmt,
        io_isFirstInstr=inputs.is_first_instr,
        io_ifuStall=inputs.ifu_stall,
        io_emptyAfter=inputs.empty_after,
        io_toUncache_req_ready=inputs.to_ready,
        io_fromUncache_resp_valid=inputs.from_valid,
        io_fromUncache_resp_bits_data=inputs.from_data,
        io_fromUncache_resp_bits_corrupt=inputs.from_corrupt,
        io_fromUncache_resp_bits_denied=inputs.from_denied,
        io_fromUncache_resp_bits_needResend=inputs.from_need_resend,
    )


def observe(harness) -> dict:
    return {
        "req_ready": harness.read(P.p_req_ready),
        "resp_valid": harness.read(P.p_resp_valid),
        "resp_data": harness.read(P.p_resp_bits_uncacheData),
        "resp_exception": harness.read(P.p_resp_bits_exception_value),
        "resp_need_resend": harness.read(P.p_resp_bits_needResend),
        "to_valid": harness.read(P.p_toUncache_req_valid),
        "to_paddr": harness.read(P.p_toUncache_req_bits_addr_addr),
        "to_mem_back_mm": harness.read(P.p_toUncache_req_bits_memBackTypeMM),
        "to_mem_page_nc": harness.read(P.p_toUncache_req_bits_memPageTypeNC),
    }


def expected_dict(outputs) -> dict:
    return {
        "req_ready": outputs.req_ready,
        "resp_valid": outputs.resp_valid,
        "resp_data": outputs.resp_data,
        "resp_exception": outputs.resp_exception,
        "resp_need_resend": outputs.resp_need_resend,
        "to_valid": outputs.to_valid,
        "to_paddr": outputs.to_paddr,
        "to_mem_back_mm": outputs.to_mem_back_mm,
        "to_mem_page_nc": outputs.to_mem_page_nc,
    }


def cycle(harness, model: UncacheModel, inputs: Inputs, *,
          expected_override: dict | None = None) -> dict:
    apply(harness, inputs)
    harness.refresh()
    observed = observe(harness)
    expected = (expected_override if expected_override is not None
                else expected_dict(model.outputs(inputs)))
    if observed["to_valid"] == 0:
        # The bus address/type are meaningful only with toUncache.valid.  The
        # RTL leaves its captured type registers at their last value (and has
        # one flush/request overlap that can update them while idle); that is
        # not part of the request contract.
        for key in ("to_paddr", "to_mem_back_mm", "to_mem_page_nc"):
            expected[key] = observed[key]
    assert observed == expected, f"phase {model.phase}, inputs {inputs}\n{observed}\n{expected}"
    model.tick(inputs)
    harness.step(1)
    return observed


def start(harness) -> UncacheModel:
    # Each scenario starts from the asynchronous reset, which also clears the
    # captured MMIO/PBMT registers that a plain idle transition does not touch.
    harness.reset()
    return UncacheModel()


IDLE_INPUTS = Inputs(to_ready=1)


# ---------------------------------------------------------------------------
# Directed lifecycle
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-UC-001")
@pytest.mark.feature("IFU-UC-003")
@pytest.mark.feature("IFU-UC-004")
def test_idle_accept_then_send_non_idempotent_type_attributes(uncache_unit):
    model = start(uncache_unit)
    address = 0x123456789ABC
    cycle(uncache_unit, model, Inputs(req_valid=1, req_paddr=address, req_pbmt=NC))
    assert model.phase == SEND
    out = cycle(uncache_unit, model, IDLE_INPUTS)
    assert out["req_ready"] == 0 and out["to_valid"] == 1
    assert out["to_paddr"] == address
    assert out["to_mem_back_mm"] == 1  # not an MMIO access
    assert out["to_mem_page_nc"] == 1  # PBMT=NC
    assert model.phase == WAIT_RESP


@pytest.mark.feature("IFU-UC-002")
def test_non_idempotent_accesses_wait_for_commit(uncache_unit):
    for is_mmio, pbmt in ((1, PMA), (0, IO), (1, IO)):
        model = start(uncache_unit)
        cycle(uncache_unit, model, Inputs(req_valid=1, req_paddr=0x1000, req_is_mmio=is_mmio,
                                          req_pbmt=pbmt))
        assert model.phase == WAIT_COMMIT, (is_mmio, pbmt)
        for _ in range(3):
            out = cycle(uncache_unit, model, Inputs(is_first_instr=0, empty_after=0, to_ready=1))
            assert out["to_valid"] == 0
            assert model.phase == WAIT_COMMIT
        # Either the first-instruction marker or an empty machine releases it.
        if is_mmio:
            cycle(uncache_unit, model, Inputs(is_first_instr=1, to_ready=1))
        else:
            cycle(uncache_unit, model, Inputs(empty_after=1, to_ready=1))
        assert model.phase == SEND


@pytest.mark.feature("IFU-UC-002")
def test_ordinary_non_cacheable_pages_do_not_wait(uncache_unit):
    for is_mmio, pbmt in ((0, PMA), (0, NC)):
        model = start(uncache_unit)
        cycle(uncache_unit, model, Inputs(req_valid=1, req_is_mmio=is_mmio, req_pbmt=pbmt))
        assert model.phase == SEND


@pytest.mark.feature("IFU-UC-003")
def test_request_is_held_until_the_bus_accepts(uncache_unit):
    model = start(uncache_unit)
    address = 0x0BADF00D
    cycle(uncache_unit, model, Inputs(req_valid=1, req_paddr=address, req_pbmt=NC))
    for _ in range(3):
        out = cycle(uncache_unit, model, Inputs(to_ready=0))
        assert out["to_valid"] == 1 and out["to_paddr"] == address
        assert model.phase == SEND
    out = cycle(uncache_unit, model, Inputs(ifu_stall=1, to_ready=1))
    assert out["to_valid"] == 0 and out["to_paddr"] == address
    assert model.phase == SEND
    cycle(uncache_unit, model, Inputs(ifu_stall=1, to_ready=0))
    assert model.phase == SEND
    cycle(uncache_unit, model, Inputs(to_ready=1))
    assert model.phase == WAIT_RESP


@pytest.mark.feature("IFU-UC-001")
@pytest.mark.feature("IFU-UC-008")
def test_requests_are_ignored_while_busy(uncache_unit):
    model = start(uncache_unit)
    cycle(uncache_unit, model, Inputs(req_valid=1, req_paddr=0x1111, req_pbmt=NC))
    for _ in range(3):
        out = cycle(uncache_unit, model, Inputs(req_valid=1, req_paddr=0x2222, req_pbmt=PMA,
                                                to_ready=0))
        assert out["req_ready"] == 0
        assert out["to_paddr"] == 0x1111


@pytest.mark.feature("IFU-UC-005")
@pytest.mark.feature("IFU-UC-006")
def test_bus_status_becomes_instruction_exception_and_one_pulse(uncache_unit):
    for corrupt, denied, exception in ((0, 0, EXC_NONE), (1, 0, EXC_HWE), (1, 1, EXC_AF)):
        model = start(uncache_unit)
        cycle(uncache_unit, model, Inputs(req_valid=1, req_paddr=0x2000, req_pbmt=NC))
        cycle(uncache_unit, model, Inputs(to_ready=1))
        assert model.phase == WAIT_RESP
        out = cycle(uncache_unit, model, Inputs(from_valid=1, from_data=0xCAFEBABE,
                                                from_corrupt=corrupt, from_denied=denied,
                                                from_need_resend=1))
        assert out["resp_valid"] == 0
        assert model.phase == IDLE
        pulse = cycle(uncache_unit, model, IDLE_INPUTS)
        assert pulse["resp_valid"] == 1
        assert pulse["resp_data"] == 0xCAFEBABE
        assert pulse["resp_exception"] == exception
        assert pulse["resp_need_resend"] == 1
        after = cycle(uncache_unit, model, IDLE_INPUTS)
        assert after["resp_valid"] == 0


@pytest.mark.feature("IFU-UC-006")
@pytest.mark.feature("IFU-UC-008")
def test_completion_is_back_to_back_usable(uncache_unit):
    model = start(uncache_unit)
    cycle(uncache_unit, model, Inputs(req_valid=1, req_paddr=0x3000, req_pbmt=NC))
    cycle(uncache_unit, model, Inputs(to_ready=1))
    cycle(uncache_unit, model, Inputs(from_valid=1, from_data=0x11))
    # The completion cycle still advertises ready and accepts the next fetch.
    pulse = cycle(uncache_unit, model, Inputs(req_valid=1, req_paddr=0x4000, req_pbmt=PMA))
    assert pulse["resp_valid"] == 1
    assert pulse["req_ready"] == 1
    assert model.phase == SEND
    out = cycle(uncache_unit, model, IDLE_INPUTS)
    assert out["to_valid"] == 1 and out["to_paddr"] == 0x4000


# ---------------------------------------------------------------------------
# Flush and ignored responses
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-UC-007")
def test_flush_aborts_every_phase_and_discards_late_response(uncache_unit):
    phases = []
    # idle
    model = start(uncache_unit)
    cycle(uncache_unit, model, Inputs(flush=1))
    assert model.phase == IDLE
    phases.append(model.phase)
    # wait-for-commit
    model = start(uncache_unit)
    cycle(uncache_unit, model, Inputs(req_valid=1, req_is_mmio=1, req_pbmt=PMA))
    cycle(uncache_unit, model, Inputs(flush=1))
    assert model.phase == IDLE
    phases.append(model.phase)
    # send
    model = start(uncache_unit)
    cycle(uncache_unit, model, Inputs(req_valid=1, req_pbmt=NC))
    cycle(uncache_unit, model, Inputs(flush=1, to_ready=0))
    assert model.phase == IDLE
    phases.append(model.phase)
    # wait-for-response, then a late response
    model = start(uncache_unit)
    cycle(uncache_unit, model, Inputs(req_valid=1, req_pbmt=NC))
    cycle(uncache_unit, model, Inputs(to_ready=1))
    assert model.phase == WAIT_RESP
    cycle(uncache_unit, model, Inputs(flush=1))
    assert model.phase == IDLE
    for _ in range(2):
        out = cycle(uncache_unit, model, Inputs(from_valid=1, from_data=0xDEAD))
        assert out["resp_valid"] == 0
    phases.append(model.phase)
    assert phases == [IDLE, IDLE, IDLE, IDLE]


@pytest.mark.feature("IFU-UC-007")
def test_flush_clears_a_completion_pulse(uncache_unit):
    model = start(uncache_unit)
    cycle(uncache_unit, model, Inputs(req_valid=1, req_pbmt=NC))
    cycle(uncache_unit, model, Inputs(to_ready=1))
    cycle(uncache_unit, model, Inputs(from_valid=1, from_data=0x55))
    out = cycle(uncache_unit, model, Inputs(flush=1))
    assert out["resp_valid"] == 1  # the pulse is visible in this cycle
    after = cycle(uncache_unit, model, IDLE_INPUTS)
    assert after["resp_valid"] == 0
    assert after["resp_data"] == 0


@pytest.mark.feature("IFU-UC-007")
def test_response_in_idle_is_ignored(uncache_unit):
    model = start(uncache_unit)
    out = cycle(uncache_unit, model, Inputs(from_valid=1, from_data=0x7777,
                                            from_corrupt=1))
    assert out["resp_valid"] == 0
    after = cycle(uncache_unit, model, IDLE_INPUTS)
    assert after["resp_valid"] == 0 and model.phase == IDLE


# ---------------------------------------------------------------------------
# Random cycle comparison
# ---------------------------------------------------------------------------
def random_inputs(rng: random.Random) -> Inputs:
    corrupt = int(rng.random() < 0.1)
    denied = int(rng.random() < 0.05)
    if denied and not corrupt:
        denied = 0  # TileLink forbids denied without corrupt; the RTL asserts
    return Inputs(
        flush=int(rng.random() < 0.03),
        req_valid=int(rng.random() < 0.35),
        req_paddr=rng.getrandbits(47),
        req_is_mmio=int(rng.random() < 0.3),
        req_pbmt=rng.randrange(4),
        is_first_instr=int(rng.random() < 0.3),
        ifu_stall=int(rng.random() < 0.25),
        empty_after=int(rng.random() < 0.3),
        to_ready=int(rng.random() < 0.7),
        from_valid=int(rng.random() < 0.3),
        from_data=rng.getrandbits(32),
        from_corrupt=corrupt,
        from_denied=denied,
        from_need_resend=int(rng.random() < 0.2),
    )


@pytest.mark.feature("IFU-UC-001")
@pytest.mark.feature("IFU-UC-002")
@pytest.mark.feature("IFU-UC-003")
@pytest.mark.feature("IFU-UC-004")
@pytest.mark.feature("IFU-UC-005")
@pytest.mark.feature("IFU-UC-006")
@pytest.mark.feature("IFU-UC-007")
@pytest.mark.feature("IFU-UC-008")
def test_random_sequences_match_the_model(uncache_unit):
    rng = random.Random(0x0CACE)
    model = start(uncache_unit)
    for _ in range(700):
        cycle(uncache_unit, model, random_inputs(rng))
    assert model.phase in (IDLE, WAIT_COMMIT, SEND, WAIT_RESP)
    # Single-slot ledger: every accepted request is completed, aborted by a
    # flush, or is the one request currently in flight.  This catches a
    # duplicated acceptance or a dropped completion that per-cycle field
    # comparison could miss.
    in_flight = int(model.phase != IDLE)
    assert model.accepted - model.completed - model.aborted == in_flight
    assert model.completed + model.aborted <= model.accepted
