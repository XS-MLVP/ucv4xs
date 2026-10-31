"""Deterministic MainBTB vectors and geometry."""

from __future__ import annotations

from dataclasses import dataclass


# DefaultConfig: four MainBTB ways plus one victim output per align bank.
NUM_WAYS = 4
SAME_PHYSICAL_SET_STRIDE = 1 << 15
PIPELINE_REQUESTS = 4


@dataclass(frozen=True, slots=True)
class BranchVector:
    pc: int
    target: int
    position: int
    branch_type: int
    # The RAS hint bits are part of the same attribute word as the branch
    # type. The default keeps every pre-existing vector at its old value.
    ras_action: int = 0


PC = 0x4000_0800
MISS_PC = PC + 0x200
# Pc.addr is halfword-addressed.  The first fetch starts in the last 16 bytes
# of a 4 KiB page; position 9 belongs to the next page's first align bank.
PAGE_END_PC = 0x4000_0FF0
NEXT_PAGE_PC = PAGE_END_PC + 16
NEXT_PAGE_BRANCH = BranchVector(
    PAGE_END_PC, 0x4000_4A00, 17, 2
)
VISIBLE_NEXT_PAGE_BRANCH = BranchVector(
    NEXT_PAGE_PC,
    NEXT_PAGE_BRANCH.target,
    1,
    NEXT_PAGE_BRANCH.branch_type,
)
LATE_START_PC = PC + 2
CONDITIONAL = BranchVector(PC, 0x4000_1234, 1, 1)
DIRECT = BranchVector(PC, 0x4000_2340, 5, 2)
INDIRECT = BranchVector(PC, 0x4000_3456, 9, 3)
BRANCH_TYPES = (CONDITIONAL, DIRECT, INDIRECT)


def coexistence_vectors() -> tuple[BranchVector, ...]:
    return BRANCH_TYPES


def conflict_vectors() -> tuple[BranchVector, ...]:
    base = 0x6000_0000
    return tuple(
        BranchVector(
            pc=base + index * SAME_PHYSICAL_SET_STRIDE,
            target=base + 0x1000 + index * 0x20,
            position=3,
            branch_type=2,
        )
        for index in range(NUM_WAYS + 1)
    )
