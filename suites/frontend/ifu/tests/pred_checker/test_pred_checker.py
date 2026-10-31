"""PredChecker: prediction contract, truncation, redirect meaning and timing."""

from __future__ import annotations

import random

import pytest

from suites.frontend.ifu.legacy_pins import P
from suites.frontend.ifu.model.pred_checker import CONDITIONAL
from suites.frontend.ifu.model.pred_checker import DIRECT
from suites.frontend.ifu.model.pred_checker import INDIRECT
from suites.frontend.ifu.model.pred_checker import Instr
from suites.frontend.ifu.model.pred_checker import NONE
from suites.frontend.ifu.model.pred_checker import POP
from suites.frontend.ifu.model.pred_checker import PUSH
from suites.frontend.ifu.model.pred_checker import Request
from suites.frontend.ifu.model.pred_checker import SLOTS
from suites.frontend.ifu.model.pred_checker import predict

LANES = 35  # the last of the 36 enqueue lanes is tied off by the IFU
_PC35 = random.Random(0x35)


def drive(harness, request: Request, *, step: bool = True) -> None:
    harness.reset_once()
    harness.set(io_req_valid=request.valid)
    for lane in range(LANES):
        instruction = request.instrs[lane]
        harness.set(**{
            P.io(f"req_bits_instrVec_{lane}_valid"): instruction.valid,
            P.io(f"req_bits_instrVec_{lane}_isRvc"): instruction.is_rvc,
            P.io(f"req_bits_instrVec_{lane}_isPredTaken"): instruction.is_pred_taken,
            P.io(f"req_bits_instrVec_{lane}_invalidTaken"): instruction.invalid_taken,
            P.io(f"req_bits_instrVec_{lane}_blockSel"): instruction.block_sel,
            P.io(f"req_bits_instrVec_{lane}_endOffset"): instruction.end_offset,
            P.io(f"req_bits_pdInfoVec_{lane}_isRVC"): instruction.is_rvc,
            P.io(f"req_bits_pdInfoVec_{lane}_brAttribute_branchType"): instruction.branch_type,
            P.io(f"req_bits_pdInfoVec_{lane}_brAttribute_rasAction"): instruction.ras_action,
            # GuardedPc/PrunedAddr ports carry PC and displacement in
            # halfword units (the low zero bit is implicit).
            P.io(f"req_bits_instrPcVec_{lane}_addr"): instruction.pc >> 1,
            P.io(f"req_bits_jumpOffsetVec_{lane}_addr"):
                (instruction.jump_offset >> 1) & ((1 << 50) - 1),
        })
    # The tied-off lane 35 has a PC port but no instruction/valid port.  It
    # can never fault, yet its target adder is still built; alternate the PC
    # so those datapath bits are exercised rather than left at one constant.
    harness.set(io_req_bits_instrPcVec_35_addr=_PC35.getrandbits(50) & ~1)
    harness.set(**{
        P.io(f"req_bits_instrVec_{lane}_isCrossBlockInstr"): request.instrs[lane].is_cross_block
        for lane in range(LANES - 1)
    })
    if step:
        harness.step(1)


def observe(harness) -> tuple[tuple[int, ...], dict]:
    stage1 = tuple(harness.read(P.io(f"resp_stage1Out_fixedInstrValid_{lane}"))
                   for lane in range(LANES))
    stage2 = {
        "valid": harness.read(P.p_resp_stage2Out_checkerRedirect_valid),
        "target": harness.read(P.p_resp_stage2Out_checkerRedirect_bits_target_addr),
        "taken": harness.read(P.p_resp_stage2Out_checkerRedirect_bits_taken),
        "invalid_taken": harness.read(P.p_resp_stage2Out_checkerRedirect_bits_invalidTaken),
        "not_cfi_taken": harness.read(P.p_resp_stage2Out_checkerRedirect_bits_notCfiTaken),
        "is_rvc": harness.read(P.p_resp_stage2Out_checkerRedirect_bits_isRVC),
        "block_sel": harness.read(P.p_resp_stage2Out_checkerRedirect_bits_blockSel),
        "branch_type": harness.read(P.p_resp_stage2Out_checkerRedirect_bits_attribute_branchType),
        "ras_action": harness.read(P.p_resp_stage2Out_checkerRedirect_bits_attribute_rasAction),
        "end_offset": harness.read(P.p_resp_stage2Out_checkerRedirect_bits_endOffset),
        "is_cross_block": harness.read(P.p_resp_stage2Out_checkerRedirect_bits_isCrossBlockInstr),
    }
    return stage1, stage2


def check(harness, request: Request, *, observed=None) -> None:
    """Compare the DUT with the model; ``observed`` injects a bad snapshot."""

    drive(harness, request)
    if observed is None:
        stage1, stage2 = observe(harness)
    else:
        stage1, stage2 = observed
    expected = predict(request)
    assert stage1 == expected.fixed_instr_valid[:LANES], (
        f"fixed valid differs, fault {expected.fault_class}@{expected.fault_index}\n"
        f"expected {expected.fixed_instr_valid[:LANES]}\nobserved {stage1}")
    redirect = expected.redirect
    assert stage2["valid"] == redirect.valid
    if redirect.valid:
        assert stage2["target"] == redirect.target >> 1
        assert stage2["taken"] == redirect.taken
        assert stage2["invalid_taken"] == redirect.invalid_taken
        assert stage2["not_cfi_taken"] == redirect.not_cfi_taken
        assert stage2["is_rvc"] == redirect.is_rvc
        assert stage2["block_sel"] == redirect.block_sel
        assert stage2["branch_type"] == redirect.branch_type
        assert stage2["ras_action"] == redirect.ras_action
        assert stage2["end_offset"] == redirect.end_offset
        assert stage2["is_cross_block"] == redirect.is_cross_block


def request(*instructions: Instr) -> Request:
    lanes = list(instructions) + [Instr() for _ in range(SLOTS - len(instructions))]
    return Request(valid=1, instrs=lanes)


def base_instruction(index: int, pc: int, **kwargs) -> Instr:
    kwargs.setdefault("end_offset", index & 0x1F)
    return Instr(valid=1, pc=pc, **kwargs)


# ---------------------------------------------------------------------------
# Directed contract scenarios
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-PC-001")
@pytest.mark.feature("IFU-PC-002")
def test_legal_predictions_enqueue_everything(pred_checker):
    lanes = [
        base_instruction(0, 0x1000, branch_type=DIRECT, is_pred_taken=1, jump_offset=0x40),
        base_instruction(1, 0x1004, branch_type=CONDITIONAL, is_pred_taken=1, jump_offset=-8),
        base_instruction(2, 0x1008, branch_type=CONDITIONAL, is_pred_taken=0),
        base_instruction(3, 0x100C),
        base_instruction(4, 0x100E, is_rvc=1, branch_type=INDIRECT, is_pred_taken=1,
                         ras_action=POP),
        base_instruction(5, 0x1010, branch_type=INDIRECT, is_pred_taken=1),
    ]
    scene = request(*lanes)
    check(pred_checker, scene)
    # No redirect at all, and every valid lane remains visible.
    drive(pred_checker, scene)
    stage1, stage2 = observe(pred_checker)
    assert stage2["valid"] == 0
    assert stage1[: len(lanes)] == (1,) * len(lanes)


@pytest.mark.feature("IFU-PC-001")
@pytest.mark.feature("IFU-PC-004")
def test_unpredicted_direct_jump_redirects_to_its_target(pred_checker):
    scene = request(
        base_instruction(0, 0x2000),
        base_instruction(1, 0x2004),
        base_instruction(2, 0x2008, branch_type=DIRECT, is_pred_taken=0, jump_offset=0x80),
        base_instruction(3, 0x200C),
        base_instruction(4, 0x2010),
    )
    check(pred_checker, scene)
    _, stage2 = observe(pred_checker)
    assert stage2["valid"] == 1 and stage2["target"] == 0x2088 >> 1
    assert stage2["taken"] == 1 and stage2["branch_type"] == DIRECT


@pytest.mark.feature("IFU-PC-001")
@pytest.mark.feature("IFU-PC-004")
def test_indirect_and_return_faults_redirect_sequentially(pred_checker):
    for ras_action, label in ((0, "jalr"), (POP, "ret")):
        scene = request(
            base_instruction(0, 0x3000),
            base_instruction(1, 0x3004, branch_type=INDIRECT, ras_action=ras_action,
                             is_pred_taken=0, jump_offset=0x1234),
            base_instruction(2, 0x3008),
        )
        check(pred_checker, scene)
        _, stage2 = observe(pred_checker)
        assert stage2["target"] == 0x3008 >> 1, label
        assert stage2["taken"] == 1 and stage2["branch_type"] == INDIRECT
        assert stage2["ras_action"] == ras_action


@pytest.mark.feature("IFU-PC-001")
@pytest.mark.feature("IFU-PC-005")
def test_non_cfi_taken_redirects_to_the_fall_through(pred_checker):
    scene = request(
        base_instruction(0, 0x4000),
        base_instruction(1, 0x4004, branch_type=NONE, is_pred_taken=1),
        base_instruction(2, 0x4008),
    )
    check(pred_checker, scene)
    _, stage2 = observe(pred_checker)
    assert stage2["valid"] == 1 and stage2["target"] == 0x4008 >> 1
    assert stage2["taken"] == 0
    assert stage2["not_cfi_taken"] == 1
    assert stage2["branch_type"] == NONE and stage2["ras_action"] == 0


@pytest.mark.feature("IFU-PC-005")
def test_invalid_taken_is_a_fault_without_an_instruction_class(pred_checker):
    # The prediction points at a lane the fetch stream marked invalid; its
    # compressed flag still decides the sequential PC width.
    scene = request(
        base_instruction(0, 0x5000),
        Instr(valid=0, is_rvc=1, invalid_taken=1, pc=0x5002, end_offset=1),
        base_instruction(2, 0x5004),
        base_instruction(3, 0x5008),
    )
    check(pred_checker, scene)
    stage1, stage2 = observe(pred_checker)
    assert stage1[0] == 1 and stage1[1] == 0 and stage1[2] == 0
    assert stage2["valid"] == 1 and stage2["target"] == 0x5004 >> 1
    assert stage2["taken"] == 0 and stage2["invalid_taken"] == 1
    assert stage2["branch_type"] == NONE and stage2["ras_action"] == 0


@pytest.mark.feature("IFU-PC-003")
@pytest.mark.feature("IFU-PC-006")
def test_earliest_fault_wins_and_truncates_later_lanes(pred_checker):
    scene = request(
        base_instruction(0, 0x6000),
        base_instruction(1, 0x6004),
        base_instruction(2, 0x6008),
        base_instruction(3, 0x600C, branch_type=DIRECT, is_pred_taken=0, jump_offset=0x20),
        base_instruction(4, 0x6010),
        base_instruction(5, 0x6014, branch_type=NONE, is_pred_taken=1),
        base_instruction(6, 0x6018, branch_type=DIRECT, is_pred_taken=0, jump_offset=0x40),
    )
    check(pred_checker, scene)
    stage1, stage2 = observe(pred_checker)
    assert stage1[:5] == (1, 1, 1, 1, 0)
    assert stage2["target"] == 0x602C >> 1  # lane 3 direct target, not the later faults
    assert stage2["branch_type"] == DIRECT


@pytest.mark.feature("IFU-PC-005")
def test_redirect_carries_fault_lane_coordinates(pred_checker):
    scene = request(
        base_instruction(0, 0x7000),
        base_instruction(1, 0x7002, is_rvc=1, branch_type=DIRECT, is_pred_taken=0,
                         block_sel=1, end_offset=7, is_cross_block=1, jump_offset=6),
    )
    check(pred_checker, scene)
    _, stage2 = observe(pred_checker)
    assert stage2["target"] == 0x7008 >> 1
    assert stage2["is_rvc"] == 1 and stage2["block_sel"] == 1
    assert stage2["end_offset"] == 7 and stage2["is_cross_block"] == 1


@pytest.mark.feature("IFU-PC-007")
def test_redirect_follows_requests_and_never_persists(pred_checker):
    fault_a = request(
        base_instruction(0, 0x8000),
        base_instruction(1, 0x8004, branch_type=DIRECT, is_pred_taken=0, jump_offset=0x10),
    )
    fault_b = request(
        base_instruction(0, 0x9000),
        base_instruction(1, 0x9004, branch_type=NONE, is_pred_taken=1),
    )
    drive(pred_checker, fault_a)
    _, first = observe(pred_checker)
    assert first["valid"] == 1 and first["target"] == 0x8014 >> 1
    drive(pred_checker, fault_b)
    _, second = observe(pred_checker)
    assert second["valid"] == 1 and second["target"] == 0x9008 >> 1
    # A clean request after a fault clears the captured fault-valid bit.
    clean = request(base_instruction(0, 0xA000), base_instruction(1, 0xA004))
    drive(pred_checker, clean)
    _, cleared = observe(pred_checker)
    assert cleared["valid"] == 0
    # Withdraw the request: the redirect must drop even though the captured
    # fault registers still hold their old payload.
    drive(pred_checker, Request(valid=0, instrs=[Instr() for _ in range(SLOTS)]))
    _, idle = observe(pred_checker)
    assert idle["valid"] == 0


# ---------------------------------------------------------------------------
# Random comparison
# ---------------------------------------------------------------------------
def random_instr(rng: random.Random, lane: int) -> Instr:
    branch_type = rng.choice([NONE, NONE, NONE, CONDITIONAL, DIRECT, INDIRECT])
    ras_action = 0
    if branch_type == INDIRECT:
        ras_action = rng.choice([0, POP, PUSH, POP | PUSH])
    if branch_type == DIRECT:
        ras_action = rng.choice([0, PUSH])
    instruction = Instr(
        valid=int(rng.random() < 0.8),
        is_rvc=int(rng.random() < 0.4),
        is_pred_taken=int(rng.random() < 0.5),
        invalid_taken=int(rng.random() < 0.06),
        block_sel=int(rng.random() < 0.4),
        end_offset=rng.randrange(32),
        is_cross_block=int(rng.random() < 0.1),
        branch_type=branch_type,
        ras_action=ras_action,
        pc=rng.getrandbits(51) & ~1,
        jump_offset=rng.getrandbits(51) & ~1,
    )
    return instruction


@pytest.mark.feature("IFU-PC-003")
@pytest.mark.feature("IFU-PC-006")
def test_fault_position_sweep_covers_the_whole_window(pred_checker):
    """A fault at every lane, including the highest, must win over later lanes.

    The priority encoder and target mux are physically split; exercising only
    early faults would leave the high-lane selection unverified even though
    the enqueue window is 35 lanes wide.
    """

    for lane in range(LANES):
        lanes = [base_instruction(index, 0x10000 + index * 4) for index in range(LANES)]
        lanes[lane] = base_instruction(lane, 0x10000 + lane * 4, branch_type=DIRECT,
                                       is_pred_taken=0, jump_offset=0x20)
        check(pred_checker, Request(valid=1, instrs=lanes + [Instr()]))


@pytest.mark.feature("IFU-PC-001")
@pytest.mark.feature("IFU-PC-005")
def test_fault_classes_at_the_window_tail(pred_checker):
    for lane in (27, 31, 33, 34):
        for kwargs in (
            {"branch_type": DIRECT, "is_pred_taken": 0, "jump_offset": 0x10},
            {"branch_type": INDIRECT, "is_pred_taken": 0},
            {"branch_type": INDIRECT, "is_pred_taken": 0, "ras_action": POP},
            {"branch_type": NONE, "is_pred_taken": 1},
            {"invalid_taken": 1, "is_rvc": 1},
        ):
            lanes = [base_instruction(index, 0x20000 + index * 4) for index in range(LANES)]
            lanes[lane] = base_instruction(lane, 0x20000 + lane * 4, **kwargs)
            check(pred_checker, Request(valid=1, instrs=lanes + [Instr()]))


@pytest.mark.feature("IFU-PC-004")
def test_target_arithmetic_spans_the_full_guarded_pc(pred_checker):
    cases = [
        ((1 << 50), 2),
        ((1 << 51) - 2, 2),
        ((1 << 51) - 2, 4),
        (0x7FFFFFFFFFFFFE, 0x10),
        (0x3FFFFFFFFFFFFE, 0x100),
        (0x2, (1 << 51) - 6),
    ]
    for pc, offset in cases:
        lanes = [base_instruction(index, 0x4000 + index * 4) for index in range(LANES)]
        lanes[5] = base_instruction(5, pc, branch_type=DIRECT, is_pred_taken=0,
                                    jump_offset=offset)
        check(pred_checker, Request(valid=1, instrs=lanes + [Instr()]))


@pytest.mark.feature("IFU-PC-001")
@pytest.mark.feature("IFU-PC-003")
@pytest.mark.feature("IFU-PC-004")
@pytest.mark.feature("IFU-PC-005")
@pytest.mark.feature("IFU-PC-006")
def test_random_requests_match_the_model(pred_checker):
    rng = random.Random(0xC0DE)
    for _ in range(400):
        lanes = [random_instr(rng, lane) for lane in range(SLOTS)]
        lanes[35] = Instr()  # the tied-off lane cannot be driven through the DUT port list
        lanes[34] = Instr(**{**lanes[34].__dict__, "is_cross_block": 0})
        check(pred_checker, Request(valid=1, instrs=lanes))
