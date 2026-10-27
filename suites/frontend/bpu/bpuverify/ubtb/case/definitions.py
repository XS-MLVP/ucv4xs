"""Deterministic MicroBTB vectors and architectural constants."""

from __future__ import annotations

from dataclasses import dataclass
import random


NUM_ENTRIES = 32
TAG_WIDTH = 22
TARGET_WIDTH = 22
INST_OFFSET_BITS = 1
PARTIAL_TAG_SPAN = 1 << (TAG_WIDTH + INST_OFFSET_BITS)
# TargetWidth counts stored halfword bits; the byte region includes bit0.
PARTIAL_TARGET_SPAN = 1 << (TARGET_WIDTH + INST_OFFSET_BITS)
RANDOM_SEED = 0xB0A
RANDOM_ENTRY_COUNT = 12


@dataclass(frozen=True, slots=True)
class BranchVector:
    pc: int
    target: int
    position: int
    branch_type: int


DIRECT = BranchVector(0x8000_1000, 0x8000_2340, 3, 2)
CONDITIONAL = BranchVector(0x8000_3000, 0x8000_3450, 1, 1)
INDIRECT = BranchVector(0x8000_5000, 0x8000_5670, 7, 3)
NOT_TAKEN = BranchVector(0x8000_7000, 0x8000_7004, 1, 1)


def capacity_vectors() -> tuple[BranchVector, ...]:
    base = 0xA000_0000
    return tuple(
        BranchVector(
            pc=base + index * 0x20,
            target=base + 0x4000 + index * 0x20,
            position=index % 16,
            branch_type=1 + index % 3,
        )
        for index in range(NUM_ENTRIES + 1)
    )


def boundary_vectors() -> tuple[BranchVector, ...]:
    region = 0xB000_0000
    return (
        BranchVector(region, region + 2, 0, 1),
        BranchVector(
            region + 0x20,
            region + PARTIAL_TARGET_SPAN - 2,
            15,
            3,
        ),
    )


def random_training_vectors() -> tuple[BranchVector, ...]:
    rng = random.Random(RANDOM_SEED)
    vectors = []
    for index in range(RANDOM_ENTRY_COUNT):
        pc = 0x9000_0000 + index * 0x40
        region_base = pc & ~(PARTIAL_TARGET_SPAN - 1)
        target = region_base | (rng.randrange(0, PARTIAL_TARGET_SPAN) & ~1)
        vectors.append(
            BranchVector(pc, target, rng.randrange(0, 16), 1 + index % 3)
        )
    return tuple(vectors)
