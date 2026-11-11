"""Semantic window generators. Index permutations exercise the leaf port domain.

The historical lattice generator is retained exactly; raw-map functional cases
also cover continuation halfword bits, which are legal producer inputs.
"""
from suites.frontend.ifu.testbenches.instr_boundary.model.boundary import BoundaryInput
from suites.frontend.ifu.testbenches.instr_boundary.model.boundary import SLOTS


def random_window(rng):
    carry = int(rng.random() < 0.25)
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
