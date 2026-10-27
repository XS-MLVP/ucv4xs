"""Independent percsum from reset-derived five-table SRAM and planned history."""
from bpuverify.common.model.configuration import *

from bpuverify.bpu.model.sc.history import history_indices

def expected_public_decisions(reference, pc, positions, providers, thresholds, common):
    if common != dict(valid=1, ghr=1, bw=common['bw'], imli=0) or common['bw'] not in (0, 1):
        raise ValueError('one genuine prefix conditional and zero PHR/IMLI required')
    base = pc // ALIGN_HALFWORDS & 127
    indices = dict(pathTable_0=base, pathTable_1=base, imliTable=base, biasTable=base, **history_indices(pc, common))
    result = []
    for position, provider in zip(positions, providers, strict=True):
        way, counter = (position % SC_WAYS ^ position // SC_WAYS, provider[2])
        bias = way * 4 + 2 * int(counter in (3, 4)) + int(counter >= 4)
        total = 0
        for table, index in indices.items():
            lane = bias if table == 'biasTable' else way
            row = reference.memories[f'{table}_bank{pc & 1}'].get(index, [0] * (4*SC_WAYS if table == 'biasTable' else SC_WAYS))
            encoded = row[lane]
            signed = encoded - 64 if encoded & 32 else encoded
            total += 2 * signed + 1
        shift = 4 if counter in (0, 7) else 6 if counter in (3, 4) else 5
        above = int(abs(total) > thresholds[way] >> shift)
        result.append((int(total >= 0), above, above))
    return tuple(result)
