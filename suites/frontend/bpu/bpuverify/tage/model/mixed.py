"""Bounded four-table MiniConfig expectations for an NT hit plus allocation.

This is not a complete TAGE allocator or write-buffer reference. The scenario
protects every cell except the other highest-table way, uses zero folded
history, and resolves an earlier NT branch plus a later cold taken branch.
"""
from bpuverify.common.model.configuration import *


def expected_tage_mixed_writes(pc, position, way, counter, *, qualified=True, allocation=True):
    if not isinstance(pc, int) or pc < 0:
        raise ValueError('pc must be a nonnegative pruned address')
    if way not in (0, 1) or counter not in (0, 1, 2):
        raise ValueError('mixed scenario needs way 0/1 and counter 0/1/2')
    if not isinstance(position, int) or not 0 <= position < (2 * TAGE_TABLES + 1):
        raise ValueError('the prepared resident position must precede cold position 9')
    ports = [None, None]
    bank, index, raw_tag = pc & 3, (pc >> 2) & (TAGE_ROWS - 1), (pc >> 11) & 8191

    def entry(cfi, count, taken):
        return {'set_idx': index, 'tag': raw_tag ^ cfi, 'counter': count,
                'entry_valid': 1, 'taken': taken}

    if qualified and counter > 0:
        ports[way] = entry(position, counter - 1, 0)
    if allocation:
        ports[1 - way] = entry((2 * TAGE_TABLES + 1), 4, 1)
    if not any(port is not None for port in ports):
        return {'beats': 0}
    banks = tuple(tuple(ports) if i == bank else (None, None) for i in range(4))
    # t0 -> t1 -> t2 -> t3, then the table's registered write request:
    # four cycles, two reactor ticks per cycle, after accepted feedback.
    return {'beats': 1, 'banks': banks, 'latency_ticks': 8}
