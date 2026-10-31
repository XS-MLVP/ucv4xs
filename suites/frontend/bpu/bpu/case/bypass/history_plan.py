"""Pure stimulus recipe against built RTL's (5,5)/(9,9) index folds."""
from suites.frontend.bpu.models.configuration import PHR_FOLDS, PHR_STORAGE_BITS
from suites.frontend.bpu.bpu.model.phr.model import MASK
from suites.frontend.bpu.bpu.model.phr.model import fold
from suites.frontend.bpu.bpu.model.phr.model import path_hash


def read_indices(pc, normal_folds):
    return ((pc & 511) ^ normal_folds[0], (pc & 511) ^ normal_folds[1])


def concatenate(pc, bits):
    result = 0
    for bit in bits:
        result = (result << 1) | ((pc >> bit) & 1)
    return result


def full_tags(pc, folded):
    f=lambda length,width: folded[PHR_FOLDS.index((length,width))]
    low = (concatenate(pc, (10,8,6,4,2)) ^ f(5,5) ^ (f(5,4)<<1)) & 31
    long = (concatenate(pc, (14,12,10,8,6,4,2,0)) ^ f(9,8) ^ (f(9,7)<<1)) & 255
    return (concatenate(pc,(3,2,1))<<5)|low, long


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
