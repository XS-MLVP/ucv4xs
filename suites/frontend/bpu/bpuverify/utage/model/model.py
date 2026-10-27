"""Independent public-feedback useful model with explicit read/write stages."""
from copy import deepcopy
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UsefulControl:
    index: int
    allocate: int = 0
    update: int = 0
    useful_valid: int = 0
    increase: int = 0

    @property
    def active(self):
        return bool(self.allocate or (self.update and self.useful_valid))


@dataclass(frozen=True, slots=True)
class UsefulEffect:
    table: int
    index: int
    role: str
    before: int
    after: int


@dataclass(frozen=True, slots=True)
class UsefulCycle:
    controls: tuple[UsefulControl, ...] | None
    effects: tuple[UsefulEffect, ...]
    sampled: bool


class UtageUsefulReference:
    """Two512-row tables; no actual state or internal qualifiers as inputs.

    Public acceptance -> useful eligibility read one cycle later -> training
    qualifier two cycles later -> visible counter update three cycles later.
    Allocation uses the earlier read; arithmetic uses current useful state.
    """
    def __init__(self, *, cycle_ticks=2):
        if type(cycle_ticks) is not int or cycle_ticks <= 0:
            raise ValueError('cycle_ticks must be a positive integer')
        self.cycle_ticks = cycle_ticks
        self.values = [0] * 1024
        self.failed_allocations = 0
        self.last_tick = None
        self._reads, self._qualifiers, self._writes = {}, {}, {}
        self._was_active = False

    @property
    def pending(self):
        return len(self._reads) + len(self._qualifiers) + len(self._writes)

    @staticmethod
    def validate(request):
        if not isinstance(request, dict):
            raise TypeError('feedback is a canonical public payload mapping')
        expected_fields = {'start_pc', 'meta', 'branch'}
        if set(request) != expected_fields:
            raise ValueError('feedback must contain start_pc, meta and branch')
        branch, meta = request['branch'], request['meta']
        if branch['branch_type'] != 1 or branch['ras_action'] != 0:
            raise ValueError('useful reference scope is conditional feedback without RAS action')
        if branch['taken'] not in (0, 1):
            raise ValueError('feedback direction must be0or1')
        slots = [entry for entry in meta['abtbResult'] if entry['valid']]
        if len(slots) != 1 or slots[0]['cfiPosition'] != branch['position']:
            raise ValueError('useful reference scope is one valid matching-position slot')
        indices = meta['readIndex']
        if len(indices) != 2 or any(type(index) is not int or index not in range(512) for index in indices):
            raise ValueError('useful reference requires two9-bit physical indices')
        slot = slots[0]
        if slot['hit'] not in (0, 1) or slot['tableId'] not in (0, 1):
            raise ValueError('invalid provider hit/table metadata')
        if slot['baseTaken'] not in (0, 1) or slot['predTaken'] not in (0, 1):
            raise ValueError('invalid base/provider prediction direction')
        return deepcopy(request)

    def _select(self, request):
        meta, branch = request['meta'], request['branch']
        slot = next(entry for entry in meta['abtbResult'] if entry['valid'])
        provider = slot['tableId'] if slot['hit'] else -1
        predicted = slot['predTaken'] if slot['hit'] else slot['baseTaken']
        incorrect = predicted != branch['taken']
        available = [table for table in range(provider + 1, 2)
                     if self.values[table * 512 + meta['readIndex'][table]] == 0]
        allocate = available[0] if incorrect and available else None
        if incorrect and allocate is None:
            self.failed_allocations += 1
        if self.failed_allocations >= 128:
            raise ValueError('global aging requires a separate reference scope; reset the context before128failed allocations')
        return tuple(UsefulControl(index=meta['readIndex'][table], allocate=int(allocate == table),
            update=int(provider == table),
            useful_valid=int(incorrect or predicted != slot['baseTaken']) if provider == table else 0,
            increase=int(not incorrect and predicted != slot['baseTaken']) if provider == table else 0)
            for table in range(2))

    def _write(self, controls):
        effects = []
        for table, control in enumerate(controls):
            address = table * 512 + control.index
            old = self.values[address]
            if control.allocate:
                new, role = table + 1, 'allocate'
            elif control.update and control.useful_valid:
                if control.increase:
                    new, role = min(3, old + 1), 'increase_hold' if old == 3 else 'increase'
                else:
                    new, role = max(0, old - 1), 'decrease_hold' if old == 0 else 'decrease'
            else:
                continue
            self.values[address] = new
            effects.append(UsefulEffect(table, control.index, role, old, new))
        return tuple(effects)

    def advance(self, tick, request=None):
        if type(tick) is not int or tick < 0:
            raise ValueError('tick must be a nonnegative integer')
        if self.last_tick is not None and tick != self.last_tick + self.cycle_ticks:
            raise ValueError('useful reference must observe every clock cycle in order')
        validated = None if request is None else self.validate(request)
        first = self.last_tick is None
        effects = self._write(self._writes.pop(tick, ()))
        if validated is not None:
            self._reads[tick + self.cycle_ticks] = validated
        if tick in self._reads:
            controls = self._select(self._reads.pop(tick))
            self._qualifiers[tick + self.cycle_ticks] = controls
            self._writes[tick + 2 * self.cycle_ticks] = controls
        controls = self._qualifiers.pop(tick, None)
        active = controls is not None and any(control.active for control in controls)
        sampled = first or active or self._was_active
        self._was_active = active
        self.last_tick = tick
        return UsefulCycle(controls, effects, sampled)

