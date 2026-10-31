"""Reset-derived SC shadows including non-backpressured full-dirty misses.

SC has one write port per buffer and no tag/flush/counter field. The generated
WriteBuffer_30/38 RTL touches its four-way PLRU on misses only. Drains use old
dirty state; a simultaneous write overrides the drain's dirty clear, but the
SRAM still receives the complete OLD drain payload.
"""
from copy import deepcopy
from suites.frontend.bpu.abtb.model.state.replacer import touch
from suites.frontend.bpu.abtb.model.state.replacer import victim
from suites.frontend.bpu.bpu.model.sc.model import NAMES
from suites.frontend.bpu.bpu.model.sc.model import advance
from suites.frontend.bpu.bpu.model.sc.model import width
from suites.frontend.bpu.bpu.model.sc.used import UsedScReference, uint

def validate_payload(payload, ways):
    if set(payload) != {'set_index', 'masks', 'data'}:
        raise ValueError('complete SC payload required')
    uint(payload['set_index'], 7, 'set_index')
    if len(payload['masks']) != ways or len(payload['data']) != ways:
        raise ValueError('complete SC mask/data row required')
    for value in payload['masks']:
        uint(value, 1, 'mask')
    for value in payload['data']:
        uint(value, 6, 'data')

def full_advance(slots, *, plru, ready, write):
    """Return new full state, new PLRU, old drain payload and write witness."""
    uint(plru, 3, 'plru')
    uint(ready, 1, 'ready')
    if len(slots) != 4:
        raise ValueError('all four physical SC slots required')
    ways = len(slots[0]['payload']['masks'])
    if ways not in (8, 32):
        raise ValueError('elaborated SC data width must be eight or thirty-two')
    for entry in slots:
        if set(entry) != {'valid', 'dirty', 'payload'}:
            raise ValueError('complete SC slot required')
        uint(entry['valid'], 1, 'valid')
        uint(entry['dirty'], 1, 'dirty')
        if entry['dirty'] and (not entry['valid']):
            raise ValueError('dirty SC slot must be valid')
        validate_payload(entry['payload'], ways)
    keys = [entry['payload']['set_index'] for entry in slots if entry['valid']]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate SC shadow key')
    if write is not None:
        validate_payload(write, ways)
    dirty = [index for index, entry in enumerate(slots) if entry['dirty']]
    hits = [] if write is None else [index for index, entry in enumerate(slots) if entry['valid'] and entry['payload']['set_index'] == write['set_index']]
    full_miss = write is not None and (not hits) and (len(dirty) == 4)
    if full_miss:
        new = deepcopy(slots)
        drained = deepcopy(slots[dirty[0]]['payload']) if ready else None
        if ready:
            new[dirty[0]]['dirty'] = 0
        slot, kind = (victim(plru), 'full_overwrite')
        new[slot] = dict(valid=1, dirty=1, payload=deepcopy(write))
    else:
        new, drained, kind = advance(slots, ready=ready, write=write)
        slot = hits[0] if hits else next((i for i, item in enumerate(slots) if not item['dirty']), None) if write is not None else None
    if write is None:
        return (new, plru, drained, None)
    next_plru = plru if hits else touch(plru, slot)
    drain_same = bool(ready and dirty and (dirty[0] == slot))
    action = dict(kind=kind, slot=slot, before=deepcopy(slots[slot]), payload=deepcopy(new[slot]['payload']), full_before=int(len(dirty) == 4), plru_before=plru, plru_after=next_plru, drain_same_slot=drain_same, overwritten_pending=bool(full_miss and (not drain_same)))
    return (new, next_plru, drained, action)

class FullScReference(UsedScReference):
    """All sixteen buffers, four full slots, SRAM persistence and PLRU from reset."""

    def reset(self):
        super().reset()
        self.plru = dict.fromkeys(NAMES, 0)

    def step(self, requests, ready):
        if set(ready) != set(NAMES) or not set(requests) <= set(NAMES):
            raise ValueError('all sixteen readiness inputs and known SC requests required')
        transitions = {name: full_advance(self.slots[name], plru=self.plru[name], ready=ready[name], write=requests.get(name)) for name in NAMES}
        drains, actions = ([], [])
        for name, (slots, plru, drained, action) in transitions.items():
            self.slots[name], self.plru[name] = (slots, plru)
            if drained is not None:
                old = self.memories[name].setdefault(drained['set_index'], [0] * width(name))
                for way, mask in enumerate(drained['masks']):
                    if mask:
                        old[way] = drained['data'][way]
                drains.append(dict(buffer=name, payload=deepcopy(drained)))
            if action is not None:
                actions.append(dict(buffer=name, **action))
        return (drains, actions)
