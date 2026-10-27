"""Expected hash geometry of the 893e1580b DefaultConfig (histories 5/9)."""
from bpuverify.common.model.configuration import PHR_FOLDS, MICRO_HISTORIES, MICRO_HISTORY_TAG_BITS
FOLD_LAYOUT = PHR_FOLDS


def fold_history(history, length, width):
    value, result = history & ((1 << length) - 1), 0
    while value:
        result ^= value & ((1 << width) - 1)
        value >>= width
    return result


def hash_indices(pc, history):
    return tuple((pc ^ fold_history(history, length, min(length, 9))) & 511
                 for length in MICRO_HISTORIES)


def _concatenate(pc, bits):
    result = 0
    for bit in bits:
        result = result << 1 | (pc >> bit) & 1
    return result


def prediction_tag(pc, history, table):
    if table == 0:
        concat, xor = (3, 2, 1), (10, 8, 6, 4, 2)
    elif table == 1:
        concat, xor = (), (14, 12, 10, 8, 6, 4, 2, 0)
    else:
        raise ValueError('MicroTAGE table must be 0 or 1')
    length, width = MICRO_HISTORIES[table], MICRO_HISTORY_TAG_BITS[table]
    low = (_concatenate(pc, xor) ^ fold_history(history, length, width)
           ^ fold_history(history, length, width - 1) << 1) & ((1 << width) - 1)
    return _concatenate(pc, concat) << width | low
