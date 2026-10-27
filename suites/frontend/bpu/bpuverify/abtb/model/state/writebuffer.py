"""Bounded ABTB WriteBuffer reference; no observed state is used as expected state."""
from copy import deepcopy
from bpuverify.abtb.model.state.counter import CounterReference
from bpuverify.abtb.model.state.counter import touch
from bpuverify.abtb.model.state.counter import victim

FIELDS = ('need_reset', 'set_index', 'way', 'valid', 'tag', 'position', 'branch_type', 'ras_action', 'target_low')
zero = lambda: dict.fromkeys(FIELDS, 0)


class WriteBufferReference:
    def __init__(self):
        self.reset()

    def reset(self):
        self.slots = [dict(shadow_valid=0, dirty=0, payload=zero()) for _ in range(4)]
        self.plru = 0

    def advance(self, *, reset, write, ready):
        if reset:
            self.reset()
            return None, None
        old = deepcopy(self.slots)
        dirty = [i for i, slot in enumerate(old) if slot['dirty']]
        drain = None
        if ready and dirty:
            slot = dirty[0]
            drain = dict(slot=slot, payload=deepcopy(old[slot]['payload']))
            self.slots[slot]['dirty'] = 0
        action = None
        if write is not None:
            if set(write) != set(FIELDS):
                raise ValueError('full bounded WriteBuffer payload required')
            hits = [i for i, slot in enumerate(old) if slot['shadow_valid'] and
                    (slot['payload']['set_index'], slot['payload']['tag']) == (write['set_index'], write['tag'])]
            if len(hits) > 1:
                raise ValueError('duplicate shadow key is outside this reference scope')
            if hits:
                slot = hits[0]
                role = 'dirty_hit' if old[slot]['dirty'] else 'clean_changed' if old[slot]['payload'] != write else 'clean_same'
                if role != 'clean_same':
                    self.slots[slot] = dict(shadow_valid=1, dirty=1, payload=deepcopy(write))
                # Actual generated WriteBuffer.sv has a miss-only PLRU enable.
            else:
                same_set = [i for i, item in enumerate(old)
                            if item['shadow_valid'] and item['payload']['set_index'] == write['set_index']]
                clean = [i for i, item in enumerate(old) if not item['dirty']]
                slot = same_set[0] if same_set else clean[0] if clean else victim(self.plru)
                role = 'same_set_replace' if same_set else 'free_slot' if clean else 'full_overwrite'
                self.slots[slot] = dict(shadow_valid=1, dirty=1, payload=deepcopy(write))
                self.plru = touch(self.plru, slot)
            action = dict(slot=slot, role=role, old=old[slot], payload=deepcopy(write),
                          drain_same_slot=drain is not None and drain['slot'] == slot)
        return drain, action


def allocation(tx, counter):
    if tx is None or not tx['taken']:
        return [None] * 4
    meta = tx['meta']
    matching = [i for i, entry in enumerate(meta['entries']) if entry['hit']
        and entry['position'] == tx['position']
        and entry['attribute'] == dict(branchType=tx['branch_type'], rasAction=tx['ras_action'])]
    if matching:
        raise ValueError('this capacity reference accepts captured-cold allocations only')
    return [dict(need_reset=1, set_index=meta['setIdx'], way=victim(counter.plru[bank][meta['setIdx']]),
        valid=1, tag=tx['pc'] & ((1 << 24) - 1), position=tx['position'],
        branch_type=tx['branch_type'], ras_action=tx['ras_action'], target_low=tx['target'] & ((1 << 22) - 1))
        if meta['bankMask'] & (1 << bank) else None for bank in range(4)]


class CapacityReference:
    def __init__(self):
        self.reset()

    def reset(self):
        self.counter = CounterReference()
        self.buffers = [WriteBufferReference() for _ in range(4)]
        self.request2 = [None] * 4
        self.sram = [[[zero() for _ in range(4)] for _ in range(64)] for _ in range(4)]

    def advance(self, *, reset, accepted, ready):
        if reset:
            self.reset()
            return [], []
        next_requests = allocation(self.counter.pending1, self.counter)
        writes, events, drains = [], [], []
        for bank, buffer in enumerate(self.buffers):
            drain, action = buffer.advance(reset=0, write=self.request2[bank], ready=ready[bank])
            if drain is not None:
                payload = drain['payload']
                self.sram[bank][payload['set_index']][payload['way']] = deepcopy(payload)
                writes.append(dict(bank=bank, set_index=payload['set_index'], way=payload['way'],
                                   reset_counter=payload['need_reset']))
                drains.append(dict(bank=bank, **drain))
            if action is not None:
                events.append(dict(bank=bank, **action))
        self.counter.advance(reset=0, accepted=accepted, writes=writes)
        self.request2 = next_requests
        return drains, events
