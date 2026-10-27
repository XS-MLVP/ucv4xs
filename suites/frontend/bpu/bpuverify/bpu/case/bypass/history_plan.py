"""Pure stimulus recipe against built RTL's (6,6)/(12,9) index folds."""
from bpuverify.bpu.model.phr.model import MASK
from bpuverify.bpu.model.phr.model import fold
from bpuverify.bpu.model.phr.model import path_hash


def read_indices(pc, normal_folds):
    return ((pc & 511) ^ normal_folds[0], (pc & 511) ^ normal_folds[1])


def concatenate(pc, bits):
    result = 0
    for bit in bits:
        result = (result << 1) | ((pc >> bit) & 1)
    return result


def full_tags(pc, folded):
    low = concatenate(pc, (12, 10, 8, 6, 4, 2)) ^ folded[2] ^ (folded[1] << 1)
    high = concatenate(pc, (11, 9, 8, 7, 5, 4, 3, 2, 1))
    low_upper = concatenate(pc, (10, 8, 6, 4, 2, 0)) ^ folded[8] ^ (folded[7] << 1)
    high_upper = concatenate(pc, (15, 13, 11, 10, 9, 8, 5, 3, 1))
    return (high << 6) | low, (high_upper << 6) | low_upper


def recurring_history(pc, position, count=30):
    history = 0
    for _ in range(count):
        history = ((history << 2) ^ path_hash((pc & ~7) + position, pc)) & MASK
    return history


def recipe(bank):
    if bank not in (2, 3):
        raise ValueError('this missing-bank recipe is only for physical banks 2/3')
    pc, position = (0x40010004, 8) if bank == 2 else (0x40010005, 7)
    fallback = position + 4
    histories = [recurring_history(pc, pos) for pos in (position, fallback)]
    indices = [read_indices(pc, (fold(h, 6, 6), fold(h, 12, 9))) for h in histories]
    assert indices[0][0] == indices[1][0] and indices[0][0] % 4 == bank
    assert indices[0][1] % 4 == bank
    return dict(bank=bank, pc=pc, position=position, fallback=fallback,
        conditional_history=histories[0], fallback_history=histories[1],
        expected_lower_index=indices[0][0], expected_conditional_upper_index=indices[0][1],
        expected_fallback_upper_index=indices[1][1],
        path_hashes=[path_hash((pc & ~7) + pos, pc) for pos in (position, fallback)])
