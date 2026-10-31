
from suites.frontend.bpu.models.configuration import *
def expected_public_decisions(reference, pc, positions, providers, thresholds):
    """Zero-history five-table percsum, with invalid GHR/BW responses zeroed."""
    base = pc // ALIGN_HALFWORDS & 127
    result = []
    for position, provider in zip(positions, providers, strict=True):
        way = position % SC_WAYS ^ position // SC_WAYS
        ctr = provider[2]
        bias = way * 4 + 2 * int(ctr in (3, 4)) + int(ctr >= 4)
        sums = []
        for table, lane in tuple((table, bias if table == 'biasTable' else way) for table in ('pathTable_0', 'pathTable_1', 'globalTable_0', 'globalTable_1', 'bwTable_0', 'bwTable_1', 'imliTable', 'biasTable')):
            encoded = 0 if table.startswith(('globalTable_', 'bwTable_')) else reference.memories[f'{table}_bank{pc & 1}'].get(base, [0] * (4*SC_WAYS if table == 'biasTable' else SC_WAYS))[lane]
            signed = encoded - 64 if encoded & 32 else encoded
            sums.append(2 * signed + 1)
        total = sum(sums)
        shift = 4 if ctr in (0, 7) else 6 if ctr in (3, 4) else 5
        above = int(abs(total) > thresholds[way] >> shift)
        result.append((int(total >= 0), above, above))
    return tuple(result)
