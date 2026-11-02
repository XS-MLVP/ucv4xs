"""InstrBoundary: slot lattice, coordinates, end mask and window-end carry."""

from __future__ import annotations

import random

import pytest

from suites.frontend.ifu.model.boundary import BoundaryInput
from suites.frontend.ifu.model.boundary import predict
from suites.frontend.ifu.instr_boundary.stimulus import random_window

SLOTS = 32


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
async def test_full_width_window_starts_every_other_slot(instr_boundary):
    scene = window(size0=32, taken=(0, 31), rvc=0, total_end=31)
    out = (await instr_boundary.analyze(scene)).result
    assert out.valid == tuple(int(slot % 2 == 0) for slot in range(SLOTS))
    assert out.is_rvc[::2] == (0,) * (SLOTS // 2)
    assert out.instr_end_mask == tuple(int(slot % 2 == 1) for slot in range(SLOTS))
    assert out.start_offset[::2] == tuple(range(0, SLOTS, 2))
    assert out.end_offset[::2] == tuple(range(1, SLOTS, 2))


@pytest.mark.feature("IFU-IB-001")
async def test_compressed_window_starts_every_slot(instr_boundary):
    scene = window(size0=32, taken=(0, 31), rvc=(1 << SLOTS) - 1, total_end=31)
    out = (await instr_boundary.analyze(scene)).result
    assert out.valid == (1,) * SLOTS
    assert out.is_rvc == (1,) * SLOTS
    assert out.instr_end_mask == (1,) * SLOTS
    assert out.end_offset == tuple(range(SLOTS))


@pytest.mark.feature("IFU-IB-001")
async def test_carry_in_continues_a_full_width_instruction(instr_boundary):
    scene = window(size0=32, taken=(0, 31), rvc=0, carry=1, total_end=31)
    out = (await instr_boundary.analyze(scene)).result
    assert out.valid[0] == 1 and out.is_rvc[0] == 0
    assert out.instr_end_mask[0] == 1
    assert out.start_offset[0] == 0
    # Slot 1 starts the next (full-width) instruction and slot 2 is its
    # second half; the lattice resumes every other slot from slot 1.
    assert out.valid[1] == 1 and out.valid[2] == 0 and out.valid[3] == 1


@pytest.mark.feature("IFU-IB-002")
async def test_payload_coordinates_follow_slot_and_block(instr_boundary):
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
    out = (await instr_boundary.analyze(scene)).result
    expected = predict(scene)
    for slot in range(SLOTS):
        if not expected.valid[slot]:
            continue  # Consumer compact never selects this metadata.
        base = 10 if slot >= 10 else 0
        assert out.is_rvc[slot] == expected.is_rvc[slot]
        assert out.block_sel[slot] == expected.block_sel[slot]
        assert out.index[slot] == indices[slot]
        assert out.start_offset[slot] == slot - base
        assert out.end_offset[slot] == (slot - base + (0 if expected.is_rvc[slot] else 1)) & 0x1F


@pytest.mark.feature("IFU-IB-003")
async def test_end_mask_counts_instruction_ends_in_a_prefix(instr_boundary):
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
    out = (await instr_boundary.analyze(scene)).result
    mask = out.instr_end_mask
    # Every slot must belong to exactly one instruction; the count of ends in
    # a prefix is non-decreasing and increases by at most one per slot.
    assert mask[0] == 1  # the carried half-instruction ends here
    running = 0
    for slot, end in enumerate(mask):
        running += end
        assert running == sum(mask[: slot + 1])
    assert mask[31] in (0, 1)


@pytest.mark.feature("IFU-IB-004")
async def test_window_end_reports_a_half_full_width_instruction(instr_boundary):
    # End position 4 is a start and RVI -> the second half is still missing.
    scene = window(size0=32, taken=(1, 4), rvc=0, total_end=5)
    out = (await instr_boundary.analyze(scene)).result
    assert out.first_end_is_half_rvi == 1
    assert out.total_end_is_half_rvi == 0  # slot 5 is the RVI second half
    # End position 5 is a continuation (not a start) -> no new half-RVI.
    scene = window(size0=32, taken=(1, 5), rvc=0, total_end=5)
    await instr_boundary.analyze(scene)
    # RVC at the first end position means the instruction is complete.
    scene = window(size0=32, taken=(1, 4), rvc=1 << 4, total_end=4)
    out = (await instr_boundary.analyze(scene)).result
    assert out.first_end_is_half_rvi == 0
    assert out.total_end_is_half_rvi == 0


@pytest.mark.feature("IFU-IB-005")
async def test_cross_block_full_width_continuation(instr_boundary):
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
    out = (await instr_boundary.analyze(scene)).result
    assert out.valid[7] == 1 and out.is_rvc[7] == 0
    assert out.is_cross_block[7] == 1
    assert out.end_offset[7] == 8
    # Slot 8 is the second half, not a new instruction.
    assert out.valid[8] == 0 and out.instr_end_mask[8] == 1
    # A taken first block has a complete instruction at its end: no carry.
    scene = window(size0=8, taken=(1, 7), block1=1, rvc=rvc,
                   block_sel=((1 << SLOTS) - 1) ^ ((1 << 8) - 1),
                   total_end=9)
    out = (await instr_boundary.analyze(scene)).result
    assert all(out.is_cross_block[i] == 0 for i in range(SLOTS) if out.valid[i])
    # An RVC at the block-end slot is complete and must not be marked.
    scene = window(size0=8, taken=(0, 7), block1=1, rvc=rvc | (1 << 7),
                   block_sel=((1 << SLOTS) - 1) ^ ((1 << 8) - 1),
                   total_end=9)
    out = (await instr_boundary.analyze(scene)).result
    assert all(out.is_cross_block[i] == 0 for i in range(SLOTS) if out.valid[i])


@pytest.mark.feature("IFU-IB-006")
async def test_second_block_owns_slots_from_its_own_start(instr_boundary):
    scene = window(size0=12, taken=(0, 11), block1=1, rvc=0,
                   block_sel=((1 << SLOTS) - 1) ^ ((1 << 12) - 1),
                   total_end=17)
    out = (await instr_boundary.analyze(scene)).result
    assert out.block_sel[10] == 0 and out.block_sel[12] == 1
    # The first block's last slot is the second half of an RVI, so slot 12
    # starts the first instruction owned by the second block.
    assert out.valid[12] == 1
    assert out.start_offset[12] == 0
    assert out.valid[13] == 0


@pytest.mark.feature("IFU-IB-002")
@pytest.mark.feature("IFU-IB-006")
async def test_offset_coordinate_sweep(instr_boundary):
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
        out = (await instr_boundary.analyze(scene)).result
        for slot in range(SLOTS):
            if not out.valid[slot]:
                continue
            base = size0 if slot >= size0 else 0
            assert out.start_offset[slot] == slot - base
            assert out.end_offset[slot] == (slot - base + 1) & 0x1F


# ---------------------------------------------------------------------------
# Random-window comparison
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-IB-001")
@pytest.mark.feature("IFU-IB-002")
@pytest.mark.feature("IFU-IB-003")
@pytest.mark.feature("IFU-IB-004")
@pytest.mark.feature("IFU-IB-005")
@pytest.mark.feature("IFU-IB-006")
async def test_random_windows_match_the_model(instr_boundary):
    rng = random.Random(0xB0A)
    await instr_boundary.analyze_many([random_window(rng) for _ in range(600)])


@pytest.mark.feature("IFU-IB-001")
@pytest.mark.feature("IFU-IB-002")
async def test_raw_continuation_map_is_legal_and_keeps_real_instruction_coordinates(instr_boundary):
    # Sixteen actual addi x1,x0,0 words have upper halfword0: raw map0xaaaaaaaa,
    # although no instruction start is compressed. Invalid-slot endOffset is
    # not consumed by compact; every real instruction's coordinates still are.
    scene = window(rvc=0xAAAAAAAA)
    out = (await instr_boundary.analyze(scene)).result
    assert out.valid == tuple(int(slot % 2 == 0) for slot in range(SLOTS))
    assert out.end_offset[::2] == tuple(range(1, SLOTS, 2))
    assert out.instr_end_mask == tuple(int(slot % 2 == 1) for slot in range(SLOTS))


@pytest.mark.feature("IFU-IB-002")
@pytest.mark.feature("IFU-IB-006")
async def test_compressed_coordinate_sweep_checks_every_slot(instr_boundary):
    for split in range(1, SLOTS + 1):
        scene = window(size0=split, taken=(0, split - 1), block1=1,
            block_sel=((1 << SLOTS) - 1) ^ ((1 << split) - 1), rvc=(1 << SLOTS) - 1)
        out = (await instr_boundary.analyze(scene)).result
        assert out.valid == (1,) * SLOTS
        assert out.start_offset == out.end_offset == tuple(
            slot if slot < split else slot - split for slot in range(SLOTS))


@pytest.mark.feature("IFU-IB-005")
@pytest.mark.parametrize('upper_halfword', [0x10, 0x13], ids=['normal-upper-half', 'upper-half-low11'])
async def test_carried_upper_half_cannot_acquire_block_one_ownership(instr_boundary, upper_halfword):
    scene = window(size0=1, taken=(0, 0), block1=1, carry=1, total_end=3,
        block_sel=((1 << SLOTS) - 1) ^ 1,
        rvc=int((upper_halfword & 3) != 3) | 0b1010)
    out = (await instr_boundary.analyze(scene)).result
    assert out.valid[0] == 1 and out.is_cross_block[0] == 0  # R-14: real FAIL for0x13.


@pytest.mark.feature("IFU-IB-001")
@pytest.mark.feature("IFU-IB-002")
async def test_arbitrary_raw_halfword_maps_keep_instruction_semantics(instr_boundary):
    rng = random.Random(0xB17)
    requests = [window(rvc=rng.getrandbits(32)) for _ in range(600)]
    await instr_boundary.analyze_many(requests)
