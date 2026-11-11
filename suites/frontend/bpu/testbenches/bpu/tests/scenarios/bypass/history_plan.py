"""Pure stimulus recipe against built RTL's (5,5)/(9,9) index folds."""
from suites.frontend.bpu.testbenches.bpu.model.configuration import PHR_STORAGE_BITS
from suites.frontend.bpu.testbenches.bpu.model.bypass.index import read_indices
from suites.frontend.bpu.testbenches.bpu.model.bypass.index import concatenate
from suites.frontend.bpu.testbenches.bpu.model.bypass.index import full_tags
from suites.frontend.bpu.testbenches.bpu.model.phr.model import MASK
from suites.frontend.bpu.testbenches.bpu.model.phr.model import fold
from suites.frontend.bpu.testbenches.bpu.model.phr.model import path_hash


def recurring_history(pc, position, count=30):
    history = 0
    for _ in range(max(count,(PHR_STORAGE_BITS+1)//2+2)):
        history = ((history << 2) ^ path_hash((pc & ~15) + position, pc)) & MASK
    return history


def recipe(bank):
    if bank not in (2, 3):
        raise ValueError('this missing-bank recipe is only for physical banks 2/3')
    pc, position = (0x40010004, 8) if bank == 2 else (0x40010005, 7)
    fallback = position + 4
    histories = [recurring_history(pc, pos) for pos in (position, fallback)]
    indices = [read_indices(pc, (fold(h, 5, 5), fold(h, 9, 9))) for h in histories]
    assert indices[0][0] == indices[1][0] and indices[0][0] % 4 == bank
    assert indices[0][1] % 4 == bank
    return dict(bank=bank, pc=pc, position=position, fallback=fallback,
        conditional_history=histories[0], fallback_history=histories[1],
        expected_lower_index=indices[0][0], expected_conditional_upper_index=indices[0][1],
        expected_fallback_upper_index=indices[1][1],
        path_hashes=[path_hash((pc & ~15) + pos, pc) for pos in (position, fallback)])
