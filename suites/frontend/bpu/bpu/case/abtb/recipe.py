"""A conditional self-loop plus neutral three-block fallback; all path hashes are zero."""
from suites.frontend.bpu.bpu.model.phr.model import path_hash


def recipe(bank):
    if bank not in (0, 1):
        raise ValueError('PC bank must be 0 or 1')
    a, b, c = (0x40010000 + low + bank for low in (0x1080, 0x10e0, 0x1c80))
    edges = ((a, 4, a), (a, 7, b), (b, 4, c), (c, 4, a))
    assert all(path_hash((pc & ~15) + position, target) == 0 for pc, position, target in edges)
    return dict(pc_bank=bank, a=a, b=b, c=c, conditional_position=4,
        fallback_position=7, edges=edges, target_abtb_bank=2 * bank, target_abtb_set=0)
