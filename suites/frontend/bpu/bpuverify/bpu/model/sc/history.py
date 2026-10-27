"""bpuverify.bpu.model.sc.history components."""
from bpuverify.common.model.configuration import *


from copy import deepcopy
from bpuverify.bpu.model.sc.model import ScReference
from bpuverify.bpu.model.sc.model import width


def history_indices(pc, common):
    if common['valid'] not in (0, 1):
        raise ValueError('common history valid must be one bit')
    if not 0 <= common['ghr'] < 1 << 16 or not 0 <= common['bw'] < 1 << 8:
        raise ValueError('common history exceeds DefaultConfig GHR/BW widths')
    def folded(value, length):
        return sum((sum((value >> j) & 1 for j in range(i, length, 7)) % 2) << i for i in range(7))
    base = (pc // ALIGN_HALFWORDS) & 127
    return {**{f'globalTable_{i}': base ^ folded(common['ghr'], n) for i, n in enumerate((8, 16))},
            **{f'bwTable_{i}': base ^ folded(common['bw'], n) for i, n in enumerate((4, 8))}}


def history_requests(transaction, memories):
    pc, meta = transaction['pc'], transaction['resolve_meta']
    common, sc, bank = meta['commonHR'], meta['sc'], pc & 1
    common_indices = history_indices(pc, common)
    owners = [entry for row in meta['mbtb_entries'] for entry in row]
    updates = []
    for branch in transaction['branches']:
        if branch is None:
            continue
        if branch['branch_type'] != 1:
            raise ValueError('only qualified conditional feedback admitted')
        hits = [index for index, entry in enumerate(owners)
                if entry['rawHit'] and entry['position'] == branch['position']]
        if len(hits) != 1:
            raise ValueError('feedback must have exactly one captured MainBTB owner')
        index, = hits
        if not sc['tagePredValid'][index]:
            raise ValueError('feedback must have a real captured TAGE provider')
        if sc['useScPred'][index]:
            raise ValueError('SC-used metadata outside this qualified setup')
        taken = branch['taken']
        if sc['scPred'][index] != taken or not sc['sumAboveThres'][index]:
            way = (branch['position'] % SC_WAYS) ^ (branch['position'] // SC_WAYS)
            updates.append((way, way * 4 + sc['scBiasLowerBits'][index], 1 if taken else -1))
    debug = sc['debug']
    indices = dict(pathTable_0=debug['predPathIdx'][0], pathTable_1=debug['predPathIdx'][1],
        imliTable=debug['predImliIdx'], biasTable=debug['predBiasIdx'])
    if common['valid']:
        for table, field, index in ((f'{family}_{i}', field, i) for family, field in (('globalTable', 'predGlobalIdx'), ('bwTable', 'predBWIdx')) for i in range(2)):
            if debug[field][index] != common_indices[table]:
                raise ValueError(f'captured {table} index disagrees with actual PC/history')
        indices.update(common_indices)
    requests = {}
    for table, set_index in indices.items():
        name = f'{table}_bank{bank}'
        old = memories[name].get(set_index, [0] * width(name))
        data, masks, deltas = list(old), [0] * width(name), [0] * width(name)
        for way, bias, delta in updates:
            deltas[bias if table == 'biasTable' else way] += delta
        for way, delta in enumerate(deltas):
            signed = old[way] - 64 if old[way] & 32 else old[way]
            data[way] = max(-32, min(31, signed + delta)) & 63
            masks[way] = int(data[way] != old[way])
        if any(masks):
            requests[name] = dict(set_index=set_index, masks=masks, data=data)
    return requests


class HistoryScReference(ScReference):
    def accept(self, tick, transaction):
        if tick + 2 in self.pending:
            raise ValueError('more than one feedback accepted in a cycle')
        requests = history_requests(transaction, self.memories)
        self.pending[tick + 2] = requests
        return deepcopy(requests)
