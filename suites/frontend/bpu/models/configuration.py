"""Reviewed 893e1580b DefaultConfig geometry, independent of sampled DUT state.

Values come from top/Configs.scala and frontend BPU parameter declarations.
The source hashes and effective baseline are recorded in the ucv build receipt.
SPDX-License-Identifier: MPL-2.0
"""
FETCH_BYTES = 64
ALIGN_BYTES = FETCH_BYTES // 2
ALIGN_HALFWORDS = ALIGN_BYTES // 2
POSITIONS = FETCH_BYTES // 2
MAIN_WAYS = 4
MAIN_BANKS = 4
MAIN_ROWS = 8192 // MAIN_WAYS // MAIN_BANKS // 2
MAIN_RETAINED = 4
RESULT_SLOTS = (MAIN_WAYS + 1) * 2
TAGE_HISTORIES = (4, 9, 17, 29, 56, 109, 211, 397)
TAGE_TABLES = len(TAGE_HISTORIES)
TAGE_ROWS = 512
TAGE_TAG_BITS = 13
ITTAGE_HISTORIES = (4, 8, 13, 16, 32)
ITTAGE_ROWS = (128, 128, 256, 256, 256)
ITTAGE_TAG_BITS = 9
MICRO_HISTORIES = (5, 9)
MICRO_HISTORY_TAG_BITS = (5, 8)
MICRO_TAG_BITS = 8
RAS_GROUPS = 16
RAS_SPEC_ENTRIES = 32
RAS_POINTER_MODULUS = 2 * RAS_SPEC_ENTRIES
SC_WAYS = 8
SC_PATH_HISTORIES = (8, 16)
SC_GLOBAL_HISTORIES = (8, 16)
SC_BACKWARD_HISTORIES = (4, 8)
SC_TABLES = 8
SC_MIN_THRESHOLD = (SC_TABLES + 5) << 6
SC_MAX_THRESHOLD = min((SC_TABLES * 63) << 4, 8191)
PHR_BITS = max(TAGE_HISTORIES)
FTQ_SIZE = 64
PHR_STORAGE_BITS = ((PHR_BITS + 2 * FTQ_SIZE + 4 + 3) // 4) * 4

def _folds():
    result=set()
    for length in TAGE_HISTORIES:
        result.update((length,min(length,width)) for width in (9,13,12))
    for length,rows in zip(ITTAGE_HISTORIES,ITTAGE_ROWS,strict=True):
        result.update((length,min(length,width)) for width in (rows.bit_length()-1,9,8))
    for length,bits in zip(MICRO_HISTORIES,MICRO_HISTORY_TAG_BITS,strict=True):
        result.update((length,min(length,width)) for width in (9,bits,bits-1))
    result.update((length,min(length,7)) for length in SC_PATH_HISTORIES)
    return tuple(sorted(result))

PHR_FOLDS = _folds()

# Exact maximum cyclic gap between low-eight-bit masks 0x80 in the 15-bit
# allocation LFSR is 1822; include the initial forecast opportunity.
TAGE_ALLOCATION_WAIT = 1823

# One complete nonzero period of the independently forecast 15-bit allocator.
# Five-table cold allocation can exceed the former 128-query observation budget.
ITTAGE_ALLOCATION_WAIT = (1 << 15) - 1
