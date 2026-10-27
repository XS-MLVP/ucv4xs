"""Expected hash geometry of the generated MinimalConfig (histories6/12)."""
FOLD_LAYOUT = ((4, 4), (6, 5), (6, 6), (8, 6), (8, 7), (9, 7), (9, 9),
    (12, 5), (12, 6), (12, 9), (16, 6), (16, 7), (16, 8),
    (17, 7), (17, 12), (17, 13), (31, 7), (31, 12), (31, 13))


def fold_history(history, length, width):
    value, result = history & ((1 << length) - 1), 0
    while value:
        result ^= value & ((1 << width) - 1)
        value >>= width
    return result


def hash_indices(pc, history):
    return ((pc ^ fold_history(history, 6, 6)) & 511,
            (pc ^ fold_history(history, 12, 9)) & 511)


def _concatenate(pc, bits):
    result = 0
    for bit in bits:
        result = result << 1 | (pc >> bit) & 1
    return result


def prediction_tag(pc, history, table):
    if table == 0:
        concat, xor, length = (11, 9, 8, 7, 5, 4, 3, 2, 1), (12, 10, 8, 6, 4, 2), 6
    elif table == 1:
        concat, xor, length = (15, 13, 11, 10, 9, 8, 5, 3, 1), (10, 8, 6, 4, 2, 0), 12
    else:
        raise ValueError('MicroTAGE table must be0or1')
    low = (_concatenate(pc, xor) ^ fold_history(history, length, 6)
           ^ fold_history(history, length, 5) << 1) & 63
    return _concatenate(pc, concat) << 6 | low

