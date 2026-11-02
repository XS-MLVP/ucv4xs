"""PredChecker: prediction contract, truncation, redirect meaning and timing."""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from suites.frontend.ifu.model.pred_checker import CONDITIONAL
from suites.frontend.ifu.model.pred_checker import DIRECT
from suites.frontend.ifu.model.pred_checker import INDIRECT
from suites.frontend.ifu.model.pred_checker import Instr
from suites.frontend.ifu.model.pred_checker import LANES
from suites.frontend.ifu.model.pred_checker import NONE
from suites.frontend.ifu.model.pred_checker import POP
from suites.frontend.ifu.model.pred_checker import PUSH
from suites.frontend.ifu.model.pred_checker import PC_MASK
from suites.frontend.ifu.model.pred_checker import Request
from suites.frontend.ifu.model.pred_checker import SLOTS


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
async def test_legal_predictions_enqueue_everything(pred_checker):
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
    await pred_checker.cycle(scene)
    # No redirect at all, and every valid lane remains visible.
    observed = await pred_checker.cycle(scene)
    assert observed.redirect.valid == 0
    assert observed.fixed_instr_valid[:len(lanes)] == (1,) * len(lanes)


@pytest.mark.feature("IFU-PC-001")
@pytest.mark.feature("IFU-PC-004")
async def test_unpredicted_direct_jump_redirects_to_its_target(pred_checker):
    scene = request(
        base_instruction(0, 0x2000),
        base_instruction(1, 0x2004),
        base_instruction(2, 0x2008, branch_type=DIRECT, is_pred_taken=0, jump_offset=0x80),
        base_instruction(3, 0x200C),
        base_instruction(4, 0x2010),
    )
    observed = await pred_checker.cycle(scene)
    assert observed.redirect.valid == 1 and observed.redirect.target == 0x2088
    assert observed.redirect.taken == 1 and observed.redirect.branch_type == DIRECT


@pytest.mark.feature("IFU-PC-001")
@pytest.mark.feature("IFU-PC-004")
async def test_indirect_and_return_faults_redirect_sequentially(pred_checker):
    for ras_action, label in ((0, "jalr"), (POP, "ret")):
        scene = request(
            base_instruction(0, 0x3000),
            base_instruction(1, 0x3004, branch_type=INDIRECT, ras_action=ras_action,
                             is_pred_taken=0, jump_offset=0x1234),
            base_instruction(2, 0x3008),
        )
        observed = await pred_checker.cycle(scene)
        assert observed.redirect.target == 0x3008, label
        assert observed.redirect.taken == 1 and observed.redirect.branch_type == INDIRECT
        assert observed.redirect.ras_action == ras_action


@pytest.mark.feature("IFU-PC-001")
@pytest.mark.feature("IFU-PC-005")
async def test_non_cfi_taken_redirects_to_the_fall_through(pred_checker):
    scene = request(
        base_instruction(0, 0x4000),
        base_instruction(1, 0x4004, branch_type=NONE, is_pred_taken=1),
        base_instruction(2, 0x4008),
    )
    observed = await pred_checker.cycle(scene)
    assert observed.redirect.valid == 1 and observed.redirect.target == 0x4008
    assert observed.redirect.taken == 0
    assert observed.redirect.not_cfi_taken == 1
    assert observed.redirect.branch_type == NONE and observed.redirect.ras_action == 0


@pytest.mark.feature("IFU-PC-005")
async def test_invalid_taken_is_a_fault_without_an_instruction_class(pred_checker):
    # The prediction points at a lane the fetch stream marked invalid; its
    # compressed flag still decides the sequential PC width.
    scene = request(
        base_instruction(0, 0x5000),
        Instr(valid=0, is_rvc=1, invalid_taken=1, pc=0x5002, end_offset=1),
        base_instruction(2, 0x5004),
        base_instruction(3, 0x5008),
    )
    observed = await pred_checker.cycle(scene)
    stage1, stage2 = observed.fixed_instr_valid, observed.redirect
    assert stage1[0] == 1 and stage1[1] == 0 and stage1[2] == 0
    assert stage2.valid == 1 and stage2.target == 0x5004
    assert stage2.taken == 0 and stage2.invalid_taken == 1
    assert stage2.branch_type == NONE and stage2.ras_action == 0


@pytest.mark.feature("IFU-PC-003")
@pytest.mark.feature("IFU-PC-006")
async def test_earliest_fault_wins_and_truncates_later_lanes(pred_checker):
    scene = request(
        base_instruction(0, 0x6000),
        base_instruction(1, 0x6004),
        base_instruction(2, 0x6008),
        base_instruction(3, 0x600C, branch_type=DIRECT, is_pred_taken=0, jump_offset=0x20),
        base_instruction(4, 0x6010),
        base_instruction(5, 0x6014, branch_type=NONE, is_pred_taken=1),
        base_instruction(6, 0x6018, branch_type=DIRECT, is_pred_taken=0, jump_offset=0x40),
    )
    observed = await pred_checker.cycle(scene)
    stage1, stage2 = observed.fixed_instr_valid, observed.redirect
    assert stage1[:5] == (1, 1, 1, 1, 0)
    assert stage2.target == 0x602C  # lane 3 direct target, not the later faults
    assert stage2.branch_type == DIRECT


@pytest.mark.feature("IFU-PC-005")
async def test_redirect_carries_fault_lane_coordinates(pred_checker):
    scene = request(
        base_instruction(0, 0x7000),
        base_instruction(1, 0x7002, is_rvc=1, branch_type=DIRECT, is_pred_taken=0,
                         block_sel=1, end_offset=7, is_cross_block=1, jump_offset=6),
    )
    observed = await pred_checker.cycle(scene)
    assert observed.redirect.target == 0x7008
    assert observed.redirect.is_rvc == 1 and observed.redirect.block_sel == 1
    assert observed.redirect.end_offset == 7 and observed.redirect.is_cross_block == 1


@pytest.mark.feature("IFU-PC-007")
async def test_redirect_follows_requests_and_never_persists(pred_checker):
    fault_a = request(
        base_instruction(0, 0x8000),
        base_instruction(1, 0x8004, branch_type=DIRECT, is_pred_taken=0, jump_offset=0x10),
    )
    fault_b = request(
        base_instruction(0, 0x9000),
        base_instruction(1, 0x9004, branch_type=NONE, is_pred_taken=1),
    )
    first = await pred_checker.cycle(fault_a)
    assert first.redirect.valid == 1 and first.redirect.target == 0x8014
    second = await pred_checker.cycle(fault_b)
    assert second.redirect.valid == 1 and second.redirect.target == 0x9008
    assert second.previous_redirect == first.redirect
    assert second.registered_tick == first.registered_tick + 2
    # A clean request after a fault clears the captured fault-valid bit.
    clean = request(base_instruction(0, 0xA000), base_instruction(1, 0xA004))
    cleared = await pred_checker.cycle(clean)
    assert cleared.redirect.valid == 0
    # Withdraw the request: the redirect must drop even though the captured
    # fault registers still hold their old payload.
    idle = await pred_checker.cycle(Request(valid=0))
    assert idle.redirect.valid == 0


@pytest.mark.feature("IFU-PC-003")
@pytest.mark.feature("IFU-PC-007")
async def test_inactive_payload_is_combinational_but_cannot_redirect(pred_checker):
    scene = request(base_instruction(0, 0xA000, branch_type=DIRECT, jump_offset=0x80),
                    base_instruction(1, 0xA004))
    fault = await pred_checker.cycle(scene)
    withdrawn = await pred_checker.cycle(replace(scene, valid=0))
    assert fault.redirect.valid == 1 and fault.redirect.target == 0xA080
    # stage1 has no request-valid qualifier. The same payload must still be
    # truncated combinationally while the registered redirect becomes invalid.
    assert withdrawn.fixed_instr_valid[:2] == (1, 0)
    assert withdrawn.previous_redirect == fault.redirect
    assert withdrawn.redirect.valid == 0
    empty = await pred_checker.cycle()
    assert not any(empty.fixed_instr_valid) and empty.redirect.valid == 0


@pytest.mark.feature("IFU-PC-007")
async def test_identical_adjacent_requests_have_distinct_response_slots(pred_checker):
    scene = request(base_instruction(0, 0xB000, branch_type=DIRECT, jump_offset=-8))
    first = await pred_checker.cycle(scene)
    second = await pred_checker.cycle(scene)
    assert first.redirect.valid == 1 and first.redirect.target == 0xAFF8
    assert first.redirect == second.redirect == second.previous_redirect
    assert second.sequence == first.sequence + 1
    assert second.registered_tick == first.registered_tick + 2


@pytest.mark.feature("IFU-PC-007")
async def test_reset_clears_redirect_before_a_new_fault(pred_checker):
    old = await pred_checker.cycle(request(
        base_instruction(0, 0xC000, branch_type=DIRECT, jump_offset=0x10)))
    assert old.redirect.valid == 1
    await pred_checker.reset()
    new = await pred_checker.cycle(request(
        base_instruction(0, 0xD000, branch_type=NONE, is_pred_taken=1)))
    assert new.previous_redirect.valid == 0
    assert new.redirect.valid == 1 and new.redirect.target == 0xD004
    assert new.sequence > old.sequence


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
async def test_fault_position_sweep_covers_the_whole_window(pred_checker):
    """A fault at every lane, including the highest, must win over later lanes.

    The priority encoder and target mux are physically split; exercising only
    early faults would leave the high-lane selection unverified even though
    the enqueue window is 35 lanes wide.
    """

    for lane in range(LANES):
        lanes = [base_instruction(index, 0x10000 + index * 4) for index in range(LANES)]
        lanes[lane] = base_instruction(lane, 0x10000 + lane * 4, branch_type=DIRECT,
                                       is_pred_taken=0, jump_offset=0x20)
        await pred_checker.cycle(Request(valid=1, instrs=lanes + [Instr()]))


@pytest.mark.feature("IFU-PC-001")
@pytest.mark.feature("IFU-PC-005")
async def test_fault_classes_at_the_window_tail(pred_checker):
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
            await pred_checker.cycle(Request(valid=1, instrs=lanes + [Instr()]))


@pytest.mark.feature("IFU-PC-004")
async def test_target_arithmetic_spans_the_full_guarded_pc(pred_checker):
    cases = [
        ((1 << 50), 2),
        ((1 << 51) - 2, 2),
        ((1 << 51) - 2, 4),
        # These two legacy XLEN constants used to be silently truncated by
        # XData. Express their actual GuardedPc values explicitly, retaining
        # the original target-adder bit patterns and distinct displacements.
        (0x7FFFFFFFFFFFFE & PC_MASK, 0x10),
        (0x3FFFFFFFFFFFFE & PC_MASK, 0x100),
        (0x2, (1 << 51) - 6),
    ]
    for pc, offset in cases:
        lanes = [base_instruction(index, 0x4000 + index * 4) for index in range(LANES)]
        lanes[5] = base_instruction(5, pc, branch_type=DIRECT, is_pred_taken=0,
                                    jump_offset=offset)
        await pred_checker.cycle(Request(valid=1, instrs=lanes + [Instr()]))


@pytest.mark.feature("IFU-PC-001")
@pytest.mark.feature("IFU-PC-003")
@pytest.mark.feature("IFU-PC-004")
@pytest.mark.feature("IFU-PC-005")
@pytest.mark.feature("IFU-PC-006")
async def test_random_requests_match_the_model(pred_checker):
    rng = random.Random(0xC0DE)
    for _ in range(400):
        lanes = [random_instr(rng, lane) for lane in range(SLOTS)]
        lanes[35] = Instr()  # the tied-off lane cannot be driven through the DUT port list
        lanes[34] = replace(lanes[34], is_cross_block=0)
        await pred_checker.cycle(Request(valid=1, instrs=lanes))
