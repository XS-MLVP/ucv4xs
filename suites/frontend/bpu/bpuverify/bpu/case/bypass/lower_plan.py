"""Complete neutral position0 path; all targets derived from actual PHR hash."""
from bpuverify.bpu.model.phr.model import path_hash


def lower_full_tag(pc):
    high = ((pc >> 11) & 1) << 8 | ((pc >> 7) & 7) << 5 | ((pc >> 1) & 31)
    low = sum(((pc >> bit) & 1) << (5 - offset)
              for offset, bit in enumerate((12, 10, 8, 6, 4, 2)))
    return (high << 6) | low


def recipe():
    a, b, c = 0x40010000, 0x400100e0, 0x40011c00
    edges = ((a, 0, a), (a, 7, b), (b, 0, c), (c, 0, a))
    assert all(path_hash((pc & ~7) + position, target) == 0 for pc, position, target in edges)
    assert lower_full_tag(a) < 256
    return dict(a=a, b=b, c=c, positions={a: 0, b: 0, c: 0}, fallback_position=7,
        edges=edges, conditional_position=0, expected_utage_index=0)
