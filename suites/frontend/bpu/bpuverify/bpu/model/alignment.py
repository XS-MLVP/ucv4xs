"""Fetch geometry in bytes, independent of the driver's halfword arithmetic."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AlignmentCase:
    first_align: int
    offset: int
    position: int

    def __post_init__(self):
        assert type(self.first_align) is int and self.first_align in (0, 1)
        assert type(self.offset) is int and 0 <= self.offset < 8
        assert type(self.position) is int and self.offset <= self.position < 16

    @property
    def pc(self):
        return 0x40020000 + self.first_align * 8 + self.offset

    @property
    def label(self):
        return f'align{self.first_align}.offset{self.offset}.position{self.position}'

    @property
    def target(self):
        return 0x40022000 + self.position * 32

    @property
    def logical_start_pcs(self):
        byte_pc = self.pc * 2
        return (self.pc, ((byte_pc + 16) // 16 * 16) // 2)

    @property
    def physical_start_pcs(self):
        logical = self.logical_start_pcs
        return tuple(logical[(bank - self.first_align) % 2] for bank in range(2))


ALL_CASES = tuple(AlignmentCase(align, offset, position)
    for align in (0, 1) for offset in range(8) for position in range(offset, 16))

# Complete conditional allocation, increments/decrements and both saturations.
PHASES = (
    ('allocate_weak_positive', 1, 2),
    ('inc2_3', 1, 3),
    ('dec3_2', 0, 2),
    ('dec2_1', 0, 1),
    ('dec1_0', 0, 0),
    ('dec0_0', 0, 0),
    ('inc0_1', 1, 1),
    ('inc1_2', 1, 2),
    ('inc2_3_again', 1, 3),
    ('inc3_3', 1, 3),
)
