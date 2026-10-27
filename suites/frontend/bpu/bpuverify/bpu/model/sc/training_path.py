"""Pure projection and SC request derivation from the actual public inputs."""

SC_FIELDS = ('scBiasLowerBits', 'scPred', 'tagePred', 'tageCtr',
             'tagePredValid', 'useScPred', 'sumAboveThres')
DEBUG_VECTORS = ('scPathTakenVec', 'scGlobalTakenVec', 'scBWTakenVec',
                 'scImliTakenVec', 'scBiasTakenVec')


def project_inputs(bits):
    meta = bits['meta']
    sc = meta['sc']
    return dict(pc=bits['start_pcs'][0][0]['addr'] & ((1 << 49) - 1),
        branches=[dict(valid=branch['valid'], bits=dict(taken=branch['bits']['taken'],
            cfiPosition=branch['bits']['cfiPosition'],
            branchType=branch['bits']['attribute']['branchType'])) for branch in bits['branches']],
        mbtb_entries=[[dict(rawHit=entry['rawHit'], position=entry['position'])
                       for entry in bank] for bank in meta['mbtb_entries']],
        commonHR=meta['commonHR'], sc={name: sc[name] for name in SC_FIELDS},
        debug={name: sc['debug'][name] for name in DEBUG_VECTORS} | dict(
            predPathIdx=sc['debug']['predPathIdx'][0],
            predGlobalIdx=sc['debug']['predGlobalIdx'][0],
            predBWIdx=sc['debug']['predBWIdx'][0],
            predImliIdx=sc['debug']['predImliIdx'], predBiasIdx=sc['debug']['predBiasIdx']))


def train_need_write(bits):
    """Read eligibility is not the same thing as a non-saturated write mask."""
    meta, owners = bits['meta'], [entry for bank in bits['meta']['mbtb_entries'] for entry in bank]
    sc = meta['sc']
    for branch in bits['branches']:
        if not branch['valid'] or branch['bits']['attribute']['branchType'] != 1:
            continue
        hits = [index for index, entry in enumerate(owners)
                if entry['rawHit'] and entry['position'] == branch['bits']['cfiPosition']]
        if not hits:
            continue
        index = min(hits)
        taken = branch['bits']['taken']
        if sc['tagePredValid'][index] and (
            not (sc['useScPred'][index] and sc['scPred'][index] == taken)
            or not (sc['useScPred'][index] and sc['tagePredValid'][index]
                    and sc['scPred'][index] == sc['tagePred'][index])):
            return 1
    return 0


def training_indices(pc, folded_path, common):
    base = (pc >> 3) & 127
    fold = lambda value: (value & 127) ^ (value >> 7)
    return dict(pathTable_0=base ^ folded_path,
        globalTable_0=base ^ fold(common['ghr']), bwTable_0=base ^ common['bw'],
        imliTable=base ^ fold(common['imli']), biasTable=base)

