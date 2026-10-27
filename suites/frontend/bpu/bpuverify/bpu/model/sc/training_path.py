"""Pure projection and SC request derivation from the actual public inputs."""
from bpuverify.common.model.configuration import *


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
            predPathIdx=tuple(sc['debug']['predPathIdx']),
            predGlobalIdx=tuple(sc['debug']['predGlobalIdx']),
            predBWIdx=tuple(sc['debug']['predBWIdx']),
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
    from bpuverify.bpu.model.sc.history import history_indices
    base = (pc // ALIGN_HALFWORDS) & 127
    if folded_path == 0:
        folded_path = (0, 0)
    if not isinstance(folded_path, (tuple, list)) or len(folded_path) != 2:
        raise ValueError('DefaultConfig needs the independent 8/16-bit path folds')
    loop = (common['imli'] & 127) ^ (common['imli'] >> 7)
    return dict(pathTable_0=base ^ folded_path[0], pathTable_1=base ^ folded_path[1],
        **history_indices(pc, common), imliTable=base ^ loop, biasTable=base)
