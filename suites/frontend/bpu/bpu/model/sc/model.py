"""Bounded SC reference: real reset, accepted input, independent SRAM/shadows.

Common-history invalid, no full-row overwrite and no flush are intentional
scope restrictions. Arbitration ready is an observed input, not predicted.
"""
from suites.frontend.bpu.models.configuration import *

from copy import deepcopy

TABLES = ('pathTable_0', 'pathTable_1', 'globalTable_0', 'globalTable_1', 'bwTable_0', 'bwTable_1', 'imliTable', 'biasTable')
NAMES = tuple(f'{table}_bank{bank}' for table in TABLES for bank in range(2))


def canonical(value):
    if isinstance(value, dict):
        return {name: canonical(item) for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    return value


def width(name):
    return 4 * SC_WAYS if name.startswith('biasTable') else SC_WAYS


def zero_slots(ways):
    return [dict(valid=0, dirty=0, payload=dict(set_index=0, masks=[0] * ways, data=[0] * ways))
            for _ in range(4)]


def encoded_payload(transaction, capacity=8):
    if not 1 <= len(transaction['branches']) <= capacity:
        raise ValueError('invalid feedback slot count')
    branches = transaction['branches'] + [None] * (capacity - len(transaction['branches']))
    return dict(meta=deepcopy(transaction['resolve_meta']),
        # Independent byte geometry, not the driver's halfword bit mask.
        start_pcs=[[dict(addr=transaction['pc']),
                    dict(addr=((transaction['pc'] // ALIGN_HALFWORDS) + 1) * ALIGN_HALFWORDS)]
                   for _ in range(3)],
        branches=[dict(valid=int(branch is not None), bits=dict(
            target_addr=0 if branch is None else branch['target'], taken=0 if branch is None else branch['taken'],
            cfiPosition=0 if branch is None else branch['position'],
            attribute=dict(branchType=0 if branch is None else branch['branch_type'],
                           rasAction=0 if branch is None else branch['ras_action']),
            mispredict=0 if branch is None else branch['mispredict'])) for branch in branches])


def sc_requests(transaction, memories):
    """Derive full table payloads from the accepted metadata and reference SRAM."""
    pc, meta = transaction['pc'], transaction['resolve_meta']
    if meta['commonHR']['valid']:
        raise ValueError('common-history valid is outside this SC masked reference')
    sc, bank = meta['sc'], pc & 1
    mbtb = [entry for row in meta['mbtb_entries'] for entry in row]
    updates = []
    for branch in transaction['branches']:
        if branch is None:
            continue
        if branch['branch_type'] != 1:
            raise ValueError('only qualified conditional feedback admitted')
        hits = [index for index, entry in enumerate(mbtb)
                if entry['rawHit'] and entry['position'] == branch['position']]
        if len(hits) != 1:
            raise ValueError('feedback must have exactly one captured MainBTB owner')
        index, = hits
        taken = branch['taken']
        if not sc['tagePredValid'][index]:
            raise ValueError('feedback must have a real captured TAGE provider')
        if sc['useScPred'][index]:
            raise ValueError('SC-used metadata outside qualified masked setup')
        if sc['scPred'][index] != taken or not sc['sumAboveThres'][index]:
            way = (branch['position'] % SC_WAYS) ^ (branch['position'] // SC_WAYS)
            updates.append((way, way * 4 + sc['scBiasLowerBits'][index], 1 if taken else -1))
    debug = sc['debug']
    indices = {'pathTable_0': debug['predPathIdx'][0], 'pathTable_1': debug['predPathIdx'][1],
               'imliTable': debug['predImliIdx'], 'biasTable': debug['predBiasIdx']}
    requests = {}
    for table, set_index in indices.items():
        name = f'{table}_bank{bank}'
        old = memories[name].get(set_index, [0] * width(name))
        data, masks = list(old), [0] * width(name)
        deltas = [0] * width(name)
        for way, bias, delta in updates:
            deltas[bias if table == 'biasTable' else way] += delta
        for way, delta in enumerate(deltas):
            signed = old[way] - 64 if old[way] & 32 else old[way]
            data[way] = max(-32, min(31, signed + delta)) & 63
            masks[way] = int(data[way] != old[way])
        if any(masks):
            requests[name] = dict(set_index=set_index, masks=masks, data=data)
    return requests


def advance(slots, *, ready, write):
    """Use prior predicted state, never DUT old slots, for merge and drain."""
    new, action, drained = deepcopy(slots), None, None
    dirty = [index for index, entry in enumerate(slots) if entry['dirty']]
    if dirty and ready:
        drained = deepcopy(slots[dirty[0]]['payload'])
        new[dirty[0]]['dirty'] = 0
    if write is not None:
        hits = [index for index, entry in enumerate(slots)
                if entry['valid'] and entry['payload']['set_index'] == write['set_index']]
        if len(hits) > 1:
            raise ValueError('duplicate SC shadow key')
        if hits:
            slot, = hits
            old = slots[slot]
            merged = deepcopy(old['payload'])
            merged['masks'] = [a | b for a, b in zip(merged['masks'], write['masks'], strict=True)]
            merged['data'] = [b if mask else a for a, b, mask
                in zip(merged['data'], write['data'], write['masks'], strict=True)]
            action = 'dirty_merge' if old['dirty'] else 'clean_reactivate' if merged != old['payload'] else 'clean_same'
            if old['dirty'] or merged != old['payload']:
                new[slot] = dict(valid=1, dirty=1, payload=merged)
        else:
            clean = [index for index, entry in enumerate(slots) if not entry['dirty']]
            if not clean:
                raise ValueError('full dirty overwrite outside bounded SC reference')
            slot, action = clean[0], 'miss'
            new[slot] = dict(valid=1, dirty=1, payload=deepcopy(write))
    return new, drained, action


class ScReference:
    def __init__(self):
        self.reset()

    def reset(self):
        self.slots = {name: zero_slots(width(name)) for name in NAMES}
        self.memories = {name: {} for name in NAMES}
        self.pending = {}

    def accept(self, tick, transaction):
        if tick + 2 in self.pending:
            raise ValueError('more than one feedback accepted in a cycle')
        requests = sc_requests(transaction, self.memories)
        self.pending[tick + 2] = requests
        return deepcopy(requests)

    def step(self, requests, ready):
        drains, actions = [], []
        for name in NAMES:
            slots, drained, action = advance(self.slots[name], ready=ready[name], write=requests.get(name))
            self.slots[name] = slots
            if drained is not None:
                old = self.memories[name].setdefault(drained['set_index'], [0] * width(name))
                for way, mask in enumerate(drained['masks']):
                    if mask:
                        old[way] = drained['data'][way]
                drains.append(dict(buffer=name, payload=drained))
            if action:
                actions.append(dict(buffer=name, kind=action))
        return drains, actions
