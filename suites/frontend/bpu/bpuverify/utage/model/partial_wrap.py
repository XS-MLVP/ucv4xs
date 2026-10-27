"""bpuverify.utage.model.partial_wrap components."""

from copy import deepcopy
from bpuverify.utage.model.model import UtageUsefulReference


class UtagePartialWrapReference:
    def __init__(self, cells):
        cells = deepcopy(tuple(cells))
        if len(cells) != 8 or any(set(cell) != {'valid', 'index', 'data_valid',
                'tag', 'position', 'counter'} for cell in cells):
            raise ValueError('partial wrap requires eight complete golden cells')
        if any(cell['valid'] != 1 or cell['data_valid'] != 1 or cell['counter'] != 3
                or cell['index'] not in range(512) or cell['tag'] not in range(256)
                for cell in cells):
            raise ValueError('partial wrap starts with eight weak-negative upper providers')
        if len({cell['index'] for cell in cells}) != 8:
            raise ValueError('partial wrap starts with eight distinct indices')
        self.cells = list(cells)
        self.enq, self.mask = 0, 255
        self.last_tick = None
        self.accepted = 0
        self._writes = {}

    @property
    def pending(self):
        return len(self._writes)

    def validate(self, payload):
        payload = UtageUsefulReference.validate(payload)
        slot = next(slot for slot in payload['meta']['abtbResult'] if slot['valid'])
        if (slot['hit'], slot['tableId'], slot['predTaken'], payload['branch']['taken']) != (1, 1, 0, 0):
            raise ValueError('partial wrap requires genuine correct upper-provider feedback')
        index = payload['meta']['readIndex'][1]
        if not any(cell['index'] == index and cell['position'] == payload['branch']['position']
                for cell in self.cells):
            raise ValueError('feedback must address an already resident golden provider')
        return payload

    def advance(self, tick, payload=None):
        if type(tick) is not int or tick < 0 or (self.last_tick is not None and tick != self.last_tick + 2):
            raise ValueError('partial wrap must observe consecutive complete cycles')
        validated = None if payload is None else self.validate(payload)
        if validated is not None and self.accepted == 2:
            raise ValueError('partial-wrap scope is exactly two feedback writes')
        write = self._writes.pop(tick, None)
        if write is not None:
            index, position = write['meta']['readIndex'][1], write['branch']['position']
            hits = sum(1 << slot for slot, cell in enumerate(self.cells)
                if cell['valid'] and cell['index'] == index and cell['position'] == position)
            selected = ((hits & self.mask) or hits).bit_length() - 1
            cell = dict(self.cells[selected])
            cell['counter'] = max(0, cell['counter'] - 1)
            self.cells[self.enq] = cell
            self.mask = 1 if self.enq == 0 else self.mask | (1 << self.enq)
            self.enq = (self.enq + 1) % 8
        if validated is not None:
            self._writes[tick + 6] = validated
            self.accepted += 1
        self.last_tick = tick
