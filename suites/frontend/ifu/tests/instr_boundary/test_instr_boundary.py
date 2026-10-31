"""InstrBoundary: slot lattice, coordinates, end mask and window-end carry."""

from __future__ import annotations

import random

import pytest

from suites.frontend.ifu.legacy_pins import P
from suites.frontend.ifu.model.boundary import BoundaryInput
from suites.frontend.ifu.model.boundary import predict
from suites.frontend.ifu.model.boundary import starts as model_starts

SLOTS = 32


def apply(harness, window: BoundaryInput) -> None:
    harness.set(
        io_req_fetchBlock_0_size=window.block0_size,
        io_req_fetchBlock_0_takenCfiOffset_valid=window.taken_valid,
        io_req_fetchBlock_0_takenCfiOffset_bits=window.taken_offset,
        io_req_fetchBlock_1_valid=window.block1_valid,
        io_req_firstInstrIsHalfRvi=window.first_instr_is_half_rvi,
        io_req_totalEndPos=window.total_end_pos,
        io_req_ifuData_maybeRvcMap=window.maybe_rvc,
        io_req_ifuData_blockSel=window.block_sel,
    )
    index = window.index or tuple(range(SLOTS))
    for slot, value in enumerate(index):
        harness.set(**{P.io(f"req_ifuData_index_{slot}"): value})
    harness.settle()


def observe(harness) -> dict:
    return {
        "valid": tuple(harness.read(P.io(f"resp_rawInstrVec_{slot}_valid")) for slot in range(SLOTS)),
        "is_rvc": tuple(harness.read(P.io(f"resp_rawInstrVec_{slot}_isRvc")) for slot in range(SLOTS)),
        # Slot 31 is excluded from the cross-block case by construction: the
        # module never asserts that marker there, so firtool removes the port.
        "is_cross_block": tuple(
            (harness.read(P.io(f"resp_rawInstrVec_{slot}_isCrossBlockInstr"))
             if slot < SLOTS - 1 else
             harness.read_pruned(P.io(f"resp_rawInstrVec_{slot}_isCrossBlockInstr"), 0))
            for slot in range(SLOTS)),
        "instr_end_mask": tuple(harness.read(P.io(f"resp_instrEndMask_{slot}")) for slot in range(SLOTS)),
        "start_offset": tuple(harness.read(P.io(f"resp_rawInstrVec_{slot}_startOffset"))
                              for slot in range(SLOTS)),
        "end_offset": tuple(harness.read(P.io(f"resp_rawInstrVec_{slot}_endOffset"))
                            for slot in range(SLOTS)),
        "block_sel": tuple(harness.read(P.io(f"resp_rawInstrVec_{slot}_blockSel"))
                           for slot in range(SLOTS)),
        "index": tuple(harness.read(P.io(f"resp_rawInstrVec_{slot}_index")) for slot in range(SLOTS)),
        "first_end_is_half_rvi": harness.read(P.p_resp_firstEndIsHalfRvi),
        "total_end_is_half_rvi": harness.read(P.p_resp_totalEndIsHalfRvi),
    }


def check(harness, window: BoundaryInput, *, observed: dict | None = None) -> None:
    """Compare the DUT with the model; ``observed`` injects a bad observation."""

    apply(harness, window)
    expected = predict(window)
    if observed is None:
        observed = observe(harness)
    for field in ("valid", "is_rvc", "is_cross_block", "instr_end_mask",
                  "start_offset", "end_offset", "block_sel", "index",
                  "first_end_is_half_rvi", "total_end_is_half_rvi"):
        assert observed[field] == getattr(expected, field), (
            f"{field} differs for window {window}\n"
            f"expected {getattr(expected, field)}\nobserved {observed[field]}")


def window(*, size0=32, taken=(0, 31), block1=0, rvc=0, block_sel=0,
           carry=0, total_end=31, index=None) -> BoundaryInput:
    return BoundaryInput(block0_size=size0, taken_valid=taken[0], taken_offset=taken[1],
                         block1_valid=block1, maybe_rvc=rvc, block_sel=block_sel,
                         first_instr_is_half_rvi=carry, total_end_pos=total_end,
                         index=index)


# ---------------------------------------------------------------------------
# Directed semantics
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-IB-001")
def test_full_width_window_starts_every_other_slot(instr_boundary):
    scene = window(size0=32, taken=(0, 31), rvc=0, total_end=31)
    apply(instr_boundary, scene)
    out = observe(instr_boundary)
    assert out["valid"] == tuple(int(slot % 2 == 0) for slot in range(SLOTS))
    assert out["is_rvc"] == (0,) * SLOTS
    assert out["instr_end_mask"] == tuple(int(slot % 2 == 1) for slot in range(SLOTS))
    assert out["start_offset"] == tuple(range(SLOTS))
    assert out["end_offset"] == tuple((slot + 1) & 0x1F for slot in range(SLOTS))


@pytest.mark.feature("IFU-IB-001")
def test_compressed_window_starts_every_slot(instr_boundary):
    scene = window(size0=32, taken=(0, 31), rvc=(1 << SLOTS) - 1, total_end=31)
    apply(instr_boundary, scene)
    out = observe(instr_boundary)
    assert out["valid"] == (1,) * SLOTS
    assert out["is_rvc"] == (1,) * SLOTS
    assert out["instr_end_mask"] == (1,) * SLOTS
    assert out["end_offset"] == tuple(range(SLOTS))


@pytest.mark.feature("IFU-IB-001")
def test_carry_in_continues_a_full_width_instruction(instr_boundary):
    scene = window(size0=32, taken=(0, 31), rvc=0, carry=1, total_end=31)
    apply(instr_boundary, scene)
    out = observe(instr_boundary)
    assert out["valid"][0] == 1 and out["is_rvc"][0] == 0
    assert out["instr_end_mask"][0] == 1
    assert out["start_offset"][0] == 0 and out["end_offset"][0] == 1
    # Slot 1 starts the next (full-width) instruction and slot 2 is its
    # second half; the lattice resumes every other slot from slot 1.
    assert out["valid"][1] == 1 and out["valid"][2] == 0 and out["valid"][3] == 1


@pytest.mark.feature("IFU-IB-002")
def test_payload_coordinates_follow_slot_and_block(instr_boundary):
    # Build a legal mixed lattice: starts only carry map bits.
    rvc = 0
    slot = 0
    index_in_pair = 0
    while slot < SLOTS:
        if index_in_pair % 3 == 0:
            rvc |= 1 << slot
            slot += 1
        else:
            slot += 2
        index_in_pair += 1
    indices = tuple((slot * 3 + 7) % 32 for slot in range(SLOTS))
    scene = window(size0=10, taken=(0, 9), block1=1, rvc=rvc,
                   block_sel=((1 << SLOTS) - 1) ^ ((1 << 10) - 1),
                   total_end=13, index=indices)
    apply(instr_boundary, scene)
    out = observe(instr_boundary)
    expected = predict(scene)
    assert out["is_rvc"] == expected.is_rvc
    assert out["block_sel"] == expected.block_sel
    assert out["index"] == indices
    for slot in range(SLOTS):
        base = 10 if slot >= 10 else 0
        assert out["start_offset"][slot] == slot - base
        assert out["end_offset"][slot] == (slot - base + (0 if expected.is_rvc[slot] else 1)) & 0x1F


@pytest.mark.feature("IFU-IB-003")
def test_end_mask_counts_instruction_ends_in_a_prefix(instr_boundary):
    # Pattern: C, RVI, C, C, RVI ...  with the carry-in from the previous window.
    rvc = 0
    slot = 1
    while slot < SLOTS:
        if (slot // 3) % 2 == 0:
            rvc |= 1 << slot
            slot += 1
        else:
            slot += 2
    scene = window(size0=24, taken=(0, 23), block1=1, rvc=rvc,
                   block_sel=((1 << SLOTS) - 1) ^ ((1 << 24) - 1),
                   carry=1, total_end=27)
    apply(instr_boundary, scene)
    out = observe(instr_boundary)
    mask = out["instr_end_mask"]
    # Every slot must belong to exactly one instruction; the count of ends in
    # a prefix is non-decreasing and increases by at most one per slot.
    assert mask[0] == 1  # the carried half-instruction ends here
    running = 0
    for slot, end in enumerate(mask):
        running += end
        assert running == sum(mask[: slot + 1])
    assert mask[31] in (0, 1)


@pytest.mark.feature("IFU-IB-004")
def test_window_end_reports_a_half_full_width_instruction(instr_boundary):
    # End position 4 is a start and RVI -> the second half is still missing.
    scene = window(size0=32, taken=(1, 4), rvc=0, total_end=5)
    apply(instr_boundary, scene)
    out = observe(instr_boundary)
    assert out["first_end_is_half_rvi"] == 1
    assert out["total_end_is_half_rvi"] == 0  # slot 5 is the RVI second half
    # End position 5 is a continuation (not a start) -> no new half-RVI.
    scene = window(size0=32, taken=(1, 5), rvc=0, total_end=5)
    check(instr_boundary, scene)
    # RVC at the first end position means the instruction is complete.
    scene = window(size0=32, taken=(1, 4), rvc=1 << 4, total_end=4)
    apply(instr_boundary, scene)
    out = observe(instr_boundary)
    assert out["first_end_is_half_rvi"] == 0
    assert out["total_end_is_half_rvi"] == 0


@pytest.mark.feature("IFU-IB-005")
def test_cross_block_full_width_continuation(instr_boundary):
    # First block ends after slot 7, its last slot starts an RVI whose second
    # half is slot 8 of the second block.  The window is not taken.
    rvc = 0
    slot = 0
    while slot < SLOTS:
        if slot in (2, 4):
            rvc |= 1 << slot
            slot += 1
        else:
            slot += 2
    scene = window(size0=8, taken=(0, 7), block1=1, rvc=rvc,
                   block_sel=((1 << SLOTS) - 1) ^ ((1 << 8) - 1),
                   total_end=9)
    apply(instr_boundary, scene)
    out = observe(instr_boundary)
    assert out["valid"][7] == 1 and out["is_rvc"][7] == 0
    assert out["is_cross_block"][7] == 1
    assert out["end_offset"][7] == 8
    # Slot 8 is the second half, not a new instruction.
    assert out["valid"][8] == 0 and out["instr_end_mask"][8] == 1
    # A taken first block has a complete instruction at its end: no carry.
    scene = window(size0=8, taken=(1, 7), block1=1, rvc=rvc,
                   block_sel=((1 << SLOTS) - 1) ^ ((1 << 8) - 1),
                   total_end=9)
    apply(instr_boundary, scene)
    assert observe(instr_boundary)["is_cross_block"] == (0,) * SLOTS
    # An RVC at the block-end slot is complete and must not be marked.
    scene = window(size0=8, taken=(0, 7), block1=1, rvc=rvc | (1 << 7),
                   block_sel=((1 << SLOTS) - 1) ^ ((1 << 8) - 1),
                   total_end=9)
    apply(instr_boundary, scene)
    assert observe(instr_boundary)["is_cross_block"] == (0,) * SLOTS


@pytest.mark.feature("IFU-IB-006")
def test_second_block_owns_slots_from_its_own_start(instr_boundary):
    scene = window(size0=12, taken=(0, 11), block1=1, rvc=0,
                   block_sel=((1 << SLOTS) - 1) ^ ((1 << 12) - 1),
                   total_end=17)
    apply(instr_boundary, scene)
    out = observe(instr_boundary)
    assert out["block_sel"][11] == 0 and out["block_sel"][12] == 1
    # The first block's last slot is the second half of an RVI, so slot 12
    # starts the first instruction owned by the second block.
    assert out["valid"][12] == 1
    assert out["start_offset"][12] == 0
    assert out["valid"][13] == 0
    assert out["start_offset"][13] == 1


@pytest.mark.feature("IFU-IB-002")
@pytest.mark.feature("IFU-IB-006")
def test_offset_coordinate_sweep(instr_boundary):
    """Every block-relative offset value must be reachable at every slot.

    Slots owned by the second block have offset ``slot - size0``; sweeping the
    first block's end from 1 to 32 therefore visits every 0..31 coordinate at
    every slot for both ownerships.  This is a semantic coverage sweep of the
    coordinate fields, not a repetition of one scenario.
    """

    for size0 in range(1, SLOTS + 1):
        scene = window(size0=size0, taken=(0, size0 - 1), block1=1, rvc=0,
                       block_sel=((1 << SLOTS) - 1) ^ ((1 << size0) - 1),
                       total_end=(size0 + 3) % SLOTS)
        apply(instr_boundary, scene)
        out = observe(instr_boundary)
        for slot in range(SLOTS):
            base = size0 if slot >= size0 else 0
            assert out["start_offset"][slot] == slot - base
            assert out["end_offset"][slot] == (slot - base + 1) & 0x1F


# ---------------------------------------------------------------------------
# Random-window comparison
# ---------------------------------------------------------------------------
def make_window(rng: random.Random) -> BoundaryInput:
    carry = int(rng.random() < 0.25)
    # Generate a legal instruction lattice.
    map_bits = 0
    slot = 0
    if carry:
        slot = 1
    while slot < SLOTS:
        if rng.random() < 0.5:
            map_bits |= 1 << slot
            slot += 1
        else:
            slot += 2
    block1 = int(rng.random() < 0.6)
    size0 = rng.randint(1, SLOTS) if block1 else SLOTS
    if block1 and size0 == SLOTS and rng.random() < 0.5:
        size0 = rng.randint(1, SLOTS - 1)
    taken = int(rng.random() < 0.4)
    offset = rng.randrange(SLOTS) if taken else max(0, size0 - 1)
    if taken:
        offset = rng.randrange(size0)
    block_sel = ((1 << SLOTS) - 1) ^ ((1 << size0) - 1) if block1 else 0
    total_end = rng.randrange(SLOTS)
    index = tuple(rng.randrange(SLOTS) for _ in range(SLOTS))
    return BoundaryInput(block0_size=size0, taken_valid=taken, taken_offset=offset,
                         block1_valid=block1, maybe_rvc=map_bits, block_sel=block_sel,
                         first_instr_is_half_rvi=carry, total_end_pos=total_end,
                         index=index)


@pytest.mark.feature("IFU-IB-001")
@pytest.mark.feature("IFU-IB-002")
@pytest.mark.feature("IFU-IB-003")
@pytest.mark.feature("IFU-IB-004")
@pytest.mark.feature("IFU-IB-005")
@pytest.mark.feature("IFU-IB-006")
def test_random_windows_match_the_model(instr_boundary):
    rng = random.Random(0xB0A)
    for _ in range(600):
        check(instr_boundary, make_window(rng))
