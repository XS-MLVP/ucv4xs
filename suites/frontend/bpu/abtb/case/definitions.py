"""Deterministic AheadBTB vectors and geometry."""

from __future__ import annotations

from dataclasses import dataclass


NUM_WAYS = 4
SAME_SET_BANK_STRIDE = 1 << 9
MAX_SET_PC = 0x4000_187E
INTERIOR_SET_PC = 0x4000_0820
HASH_SET_PC = 0x4000_0800


@dataclass(frozen=True, slots=True)
class BranchVector:
    pc: int
    target: int
    position: int
    branch_type: int


CONDITIONAL = BranchVector(0x4000_0800, 0x4000_1234, 3, 1)
CONDITIONAL_NEIGHBOR = BranchVector(
    CONDITIONAL.pc + 2,
    CONDITIONAL.target + 0x20,
    CONDITIONAL.position + 1,
    CONDITIONAL.branch_type,
)
DIRECT = BranchVector(0x4000_1800, 0x4000_2340, 9, 2)
INDIRECT = BranchVector(0x4000_2800, 0x4000_3456, 15, 3)
TRAINING_VECTORS = (CONDITIONAL, DIRECT, INDIRECT)
NOT_TAKEN = BranchVector(0x4000_3800, 0x4000_3802, 1, 1)


def hash_bank_vectors() -> tuple[tuple[int, BranchVector], ...]:
    """One PC and set, with history alone selecting each of four banks."""

    return tuple(
        (
            path_hash,
            BranchVector(
                pc=0x4000_4800,
                target=0x4001_5000 + path_hash * 0x20,
                position=6,
                branch_type=1,
            ),
        )
        for path_hash in range(4)
    )


def hash_set_vectors() -> tuple[tuple[int, BranchVector], ...]:
    """One PC and bank, with upper hash bits selecting four different sets."""

    return tuple(
        (
            path_hash,
            BranchVector(
                pc=HASH_SET_PC,
                target=0x4004_1000 + set_index * 0x100,
                position=4,
                branch_type=1,
            ),
        )
        for set_index, path_hash in enumerate((3, 7, 11, 15))
    )


def hash_selected_set_vectors(count: int = 2 * NUM_WAYS) -> tuple[BranchVector, ...]:
    """Conflicting conditional tags in bank 3/set 1 under path hash 7."""

    return tuple(
        BranchVector(
            pc=HASH_SET_PC + index * SAME_SET_BANK_STRIDE,
            target=0x4005_0000 + index * 0x40,
            position=index,
            branch_type=1,
        )
        for index in range(count)
    )


def conflict_vectors() -> tuple[BranchVector, ...]:
    base = 0x5000_0000
    return tuple(
        BranchVector(
            pc=base + index * SAME_SET_BANK_STRIDE,
            target=base + 0x10000 + index * 0x20,
            position=index,
            branch_type=1 + index % 3,
        )
        for index in range(NUM_WAYS + 1)
    )


def conditional_way_vectors() -> tuple[BranchVector, ...]:
    """Four conditional tags sharing one bank/set but occupying separate ways."""

    base = 0x4000_0838  # With path_hash=0xB: bank 3, set 30.
    return tuple(
        BranchVector(
            pc=base + index * SAME_SET_BANK_STRIDE,
            target=0x4001_2000 + index * 0x20,
            position=1 + index * 2,
            branch_type=1,
        )
        for index in range(NUM_WAYS)
    )


def highest_set_vectors(bank: int, count: int = NUM_WAYS) -> tuple[BranchVector, ...]:
    """Conditional tags in the last physical set of one history-selected bank."""

    if not 0 <= bank < 4:
        raise ValueError(f"AheadBTB bank index must be in [0, 4): {bank}")
    return tuple(
        BranchVector(
            pc=MAX_SET_PC + index * SAME_SET_BANK_STRIDE,
            target=0x4002_0000 + bank * 0x100 + index * 0x20,
            position=index,
            branch_type=1,
        )
        for index in range(count)
    )


def wrapped_zero_set_vectors(bank: int, count: int = NUM_WAYS) -> tuple[BranchVector, ...]:
    """Four tags immediately after the physical set-63-to-0 PC boundary."""

    if not 0 <= bank < 4:
        raise ValueError(f"AheadBTB bank index must be in [0, 4): {bank}")
    return tuple(
        BranchVector(
            pc=MAX_SET_PC + 2 + index * SAME_SET_BANK_STRIDE,
            target=0x4007_0000 + bank * 0x100 + index * 0x20,
            position=1 + index * 2,
            branch_type=1,
        )
        for index in range(count)
    )


def same_pc_position_vectors(
    bank: int, set_index: int, count: int = NUM_WAYS + 1
) -> tuple[BranchVector, ...]:
    """Ordered conditional branches sharing one tag, bank, and physical set."""

    if not 0 <= bank < 4:
        raise ValueError(f"AheadBTB bank index must be in [0, 4): {bank}")
    if not 0 <= set_index < 64:
        raise ValueError(f"AheadBTB physical set index must be in [0, 64): {set_index}")
    pc = interior_set_vectors(bank, set_index, 1)[0].pc
    return tuple(
        BranchVector(
            pc=pc,
            target=0x4008_0000 + bank * 0x100 + index * 0x20,
            position=1 + index * 2,
            branch_type=1,
        )
        for index in range(count)
    )


def interior_set_vectors(
    bank: int, set_index: int = 16, count: int = NUM_WAYS
) -> tuple[BranchVector, ...]:
    """Conditional tags in one physical set of a history-selected bank."""

    if not 0 <= bank < 4:
        raise ValueError(f"AheadBTB bank index must be in [0, 4): {bank}")
    if not 0 <= set_index < 64:
        raise ValueError(f"AheadBTB physical set index must be in [0, 64): {set_index}")
    return tuple(
        BranchVector(
            pc=INTERIOR_SET_PC + (set_index - 16) * 2 + index * SAME_SET_BANK_STRIDE,
            target=0x4003_1000 + bank * 0x100 + set_index * 0x10 + index * 0x20,
            position=1 + index * 2,
            branch_type=1,
        )
        for index in range(count)
    )


def three_set_neighborhood_vectors(
    bank: int, set_index: int, count: int = NUM_WAYS, *, center_set: int = 3
) -> tuple[BranchVector, ...]:
    """Distinct targets for a three-set interior neighborhood."""

    if not 1 <= center_set <= 62:
        raise ValueError("three-set neighborhood center must be an interior set")
    if set_index not in (center_set - 1, center_set, center_set + 1):
        raise ValueError("set must be the center or one of its two neighbors")
    return tuple(
        BranchVector(
            pc=vector.pc,
            target=0x4010_0000 + (bank << 16) + (set_index << 8) + (way << 4),
            position=vector.position,
            branch_type=vector.branch_type,
        )
        for way, vector in enumerate(interior_set_vectors(bank, set_index, count))
    )


def middle_boundary_vectors(set_index: int, bank: int) -> tuple[BranchVector, ...]:
    """Four tags at one bank on either side of physical set bit 5."""

    if set_index not in (31, 32) or bank not in range(4):
        raise ValueError("middle-boundary matrix uses sets 31/32 and banks 0..3")
    base = HASH_SET_PC + 2 * set_index
    return tuple(
        BranchVector(
            pc=base + way * SAME_SET_BANK_STRIDE,
            target=0x4006_0000 + set_index * 0x100 + bank * 0x20 + way * 2,
            position=way,
            branch_type=1,
        )
        for way in range(NUM_WAYS)
    )
