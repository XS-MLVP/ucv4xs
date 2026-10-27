"""Public encoded-PC vectors for the installed AheadBTB geometry."""
from dataclasses import dataclass

NUM_WAYS = 4
SAME_SET_BANK_STRIDE = 1 << 9
INTERIOR_SET_PC = 0x4000_0820


@dataclass(frozen=True, slots=True)
class BranchVector:
    pc: int
    target: int
    position: int
    branch_type: int


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
