"""Distinct index with representable upper tag and complete zero PHR path."""
from suites.frontend.bpu.bpu.model.phr.model import path_hash
from suites.frontend.bpu.bpu.case.bypass.lower_plan import lower_full_tag
from suites.frontend.bpu.bpu.case.bypass.lower_plan import recipe


def upper_full_tag(pc):
    high = 0
    for bit in (15, 13, 11, 10, 9, 8, 5, 3, 1):
        high = high << 1 | ((pc >> bit) & 1)
    low = 0
    for bit in (10, 8, 6, 4, 2, 0):
        low = low << 1 | ((pc >> bit) & 1)
    return high << 6 | low


def second_key():
    # These are the existing agent's PrunedAddr.addr values. The old
    # position1 self-loop had full upper tag2336 and could never be resident.
    a, b, c, position, fallback = 0x40011080, 0x400110a0, 0x40011480, 4, 5
    edges = ((a, position, a), (a, fallback, b), (b, position, c), (c, position, a))
    assert all(path_hash((pc & ~7) + pos, target) == 0 for pc, pos, target in edges)
    assert a & 511 == 128 and lower_full_tag(a) == 2080
    assert upper_full_tag(a) == 0
    assert all((pc & 511) % 4 == 0 for pc in (a, b, c))
    assert recipe()['a'] & 511 != a & 511
    return dict(a=a, b=b, c=c, position=position, fallback=fallback, edges=edges,
        expected_index=128, expected_bank=0, expected_lower_full_tag=lower_full_tag(a),
        expected_upper_full_tag=upper_full_tag(a))
