def expected_public_decisions(reference, pc, positions, providers, thresholds):
    """Zero-history five-table percsum, with invalid GHR/BW responses zeroed."""
    base = pc >> 3 & 127
    result = []
    for position, provider in zip(positions, providers, strict=True):
        way = position & 3 ^ position >> 2
        ctr = provider[2]
        bias = way * 4 + 2 * int(ctr in (3, 4)) + int(ctr >= 4)
        sums = []
        for table, lane in (('pathTable_0', way), ('globalTable_0', way), ('bwTable_0', way), ('imliTable', way), ('biasTable', bias)):
            encoded = 0 if table in ('globalTable_0', 'bwTable_0') else reference.memories[f'{table}_bank{pc & 1}'].get(base, [0] * (16 if table == 'biasTable' else 4))[lane]
            signed = encoded - 64 if encoded & 32 else encoded
            sums.append(2 * signed + 1)
        total = sum(sums)
        shift = 4 if ctr in (0, 7) else 6 if ctr in (3, 4) else 5
        above = int(abs(total) > thresholds[way] >> shift)
        result.append((int(total >= 0), above, above))
    return tuple(result)
