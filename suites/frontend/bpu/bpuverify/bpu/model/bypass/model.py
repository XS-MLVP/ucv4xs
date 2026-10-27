"""Reset-derived MicroTAGE shadow contract, independent of observed state.

Boundary: actual table training inputs and actual read index. This is NOT an
upstream MicroTAGE allocation-policy or SRAM-persistence reference. In
particular a newly enqueued dirty copy must survive same-slot retirement;
the known RTL overwrite defect is not copied into the expected behavior.
"""
from copy import deepcopy


def zero_cell():
    return dict(valid=0, index=0, payload_valid=0, data_valid=0, tag=0, position=0, counter=0)


def payload(cell):
    return {name: cell[name] for name in ('data_valid', 'tag', 'position', 'counter')}


def saturate(value, increase, maximum):
    return min(maximum, value + 1) if increase else max(0, value - 1)


class BypassReference:
    def __init__(self, table):
        if type(table) is not int or table not in (0, 1):
            raise ValueError('fixed RTL has tables 0 and 1')
        self.table = table
        self.reset()

    def reset(self):
        self.cells = [zero_cell() for _ in range(8)]
        self.status = [dict(valid=0, dirty=0) for _ in range(8)]
        self.useful = [0] * 512
        self.enq = self.deq = self.mask = self.force = 0
        self.hits = self.chosen = 0
        self.train_index = 0
        self.train_hit = False
        self.train_slot = None
        self.train_entry = None

    def select(self, index):
        hits = sum(1 << slot for slot, cell in enumerate(self.cells)
                   if cell['valid'] and cell['index'] == index)
        preferred = hits & self.mask
        selected = (preferred or hits).bit_length() - 1
        return hits, preferred, None if not hits else selected

    def state(self):
        return dict(cells=deepcopy(self.cells), status=deepcopy(self.status), useful=list(self.useful),
            enq=dict(flag=self.enq // 8, value=self.enq % 8),
            deq=dict(flag=self.deq // 8, value=self.deq % 8), mask=self.mask, force=self.force,
            hits=[(self.hits >> slot) & 1 for slot in range(8)], chosen=self.chosen,
            train_index=self.train_index, train_has_hit=int(self.train_hit))

    def outputs(self, inputs):
        selected = (self.chosen or self.hits).bit_length() - 1
        cell = None if not self.hits else self.cells[selected]
        result = dict(response=dict(hit=int(bool(cell and cell['payload_valid']))))
        if cell is not None:
            result['response'].update(payload(cell))
        _, _, train_slot = self.select(inputs['train_index'])
        train_cell = None if train_slot is None else self.cells[train_slot]
        result['train_read'] = dict(hit=int(bool(train_cell and train_cell['payload_valid'])),
            useful=self.useful[inputs['train_index']])
        if train_cell is not None:
            result['train_read']['position'] = train_cell['position']
        oldest = self.cells[self.deq % 8]
        status = self.status[self.deq % 8]
        write_valid = int(bool(status['valid'] and status['dirty']))
        force = int(bool(self.force and write_valid))
        result['write'] = dict(valid=write_valid, index=oldest['index'], force=force, **payload(oldest))
        # MicroTageTable.scala:108..110: bank conflict or forced write. The
        # request-valid port does not participate in this actual RTL equation.
        result['write_success'] = int(bool(write_valid and
            (inputs['read_index'] % 4 != oldest['index'] % 4 or force)))
        return result

    @staticmethod
    def validate(inputs):
        limits = dict(read_index=512, train_index=512, tag=256, allocate=2, allocate_taken=2,
            allocate_position=16, update=2, update_taken=2, update_position=16,
            update_counter=8, useful_valid=2, useful_increase=2, age=2)
        if set(inputs) != set(limits):
            raise ValueError('complete exact training/read boundary required')
        for name, limit in limits.items():
            if type(inputs[name]) is not int or inputs[name] not in range(limit):
                raise ValueError(f'invalid {name}: {inputs[name]!r}')
        if inputs['allocate'] and inputs['update']:
            raise ValueError('mutually exclusive upstream alloc/update contract violated')
        return inputs

    def advance(self, inputs, *, reset=False):
        inputs = self.validate(inputs)
        if reset:
            self.reset()
            return dict(kind='reset')
        old_enq, old_deq = self.enq, self.deq
        previous_useful = tuple(self.useful)
        old_slot = old_enq % 8
        hits, preferred, _ = self.select(inputs['read_index'])
        _, _, selected = self.select(inputs['train_index'])
        next_entry = None if selected is None else deepcopy(self.cells[selected])
        next_slot = selected
        write = bool(inputs['allocate'] or inputs['update'])
        witness = dict(kind='idle')
        new_cell = None
        if write:
            if inputs['allocate']:
                counter = 4 if inputs['allocate_taken'] else 3
                source = 'allocation'
            else:
                cached = self.train_entry
                resident = bool(self.train_hit and cached and cached['payload_valid'] and
                                cached['tag'] == inputs['tag'])
                previous = cached['counter'] if resident else inputs['update_counter']
                counter = saturate(previous, inputs['update_taken'], 7)
                source = 'resident' if resident else 'captured_counter'
            new_cell = dict(valid=1, index=self.train_index, payload_valid=1, data_valid=1,
                tag=inputs['tag'], position=inputs['allocate_position'] if inputs['allocate']
                    else inputs['update_position'], counter=counter)
            witness = dict(kind='write', source=source, slot=old_slot, index=self.train_index,
                prior_counter=None if inputs['allocate'] else previous,
                direction=inputs['allocate_taken'] if inputs['allocate'] else inputs['update_taken'],
                same_index_forward=int(self.train_index == inputs['train_index']),
                same_slot_retirement=int(bool(self.train_hit and self.train_slot == old_slot)),
                enq_wrap=int(old_slot == 7), **payload(new_cell))
        outputs = self.outputs(inputs)
        dirty = self.status[old_deq % 8]['dirty']
        if outputs['write_success'] or (not dirty and old_deq != old_enq):
            self.deq = (old_deq + 1) % 16
        if outputs['write_success']:
            self.status[old_deq % 8]['dirty'] = 0
        if write and self.train_hit and self.train_slot != old_slot:
            self.status[self.train_slot]['dirty'] = 0
        if write:
            self.cells[old_slot] = new_cell
            self.status[old_slot] = dict(valid=1, dirty=1)
            self.enq = (old_enq + 1) % 16
            self.mask = (1 << (old_slot + 1)) - 1
            if self.train_index == inputs['train_index']:
                next_slot, next_entry = old_slot, deepcopy(new_cell)
        if inputs['allocate'] or inputs['update'] and inputs['useful_valid']:
            self.useful[self.train_index] = (self.table + 1) if inputs['allocate'] else\
                saturate(self.useful[self.train_index], inputs['useful_increase'], 3)
        if inputs['age']:
            self.useful = [max(0, value - 1) if self.table == 0 else value // 2
                           for value in previous_useful]
            witness['aged'] = True
        self.force = int((old_enq - old_deq) % 16 > 6)
        self.hits, self.chosen = hits, preferred
        self.train_index = inputs['train_index']
        self.train_hit = next_slot is not None
        self.train_slot, self.train_entry = next_slot, next_entry
        witness.update(writeback=outputs['write_success'], force=outputs['write']['force'])
        return witness
